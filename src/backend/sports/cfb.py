"""
College football live scanner: label versus substance.

The market tends to price teams on the label (rank, record, spread, brand) long after
the game state says otherwise. This scanner compares each live game's Polymarket
moneyline price with ESPN's live win probability and flags the team whose price lags
the game state by at least ``threshold`` points. Every flag is written to the binary
prediction ledger so the pattern can be scored once games settle.

Covers FBS (ESPN group 80) and FCS (group 81).
"""

import json
import time
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import Market, Prediction

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
LEAGUES = {
    "cfb": {"espn": ESPN_BASE, "groups": ("80", "81"), "prefix": "cfb-", "sport": "CFB"},
    "nfl": {"espn": "https://site.api.espn.com/apis/site/v2/sports/football/nfl", "groups": (None,), "prefix": "nfl-", "sport": "NFL"},
}
GAMMA_MARKETS = "https://gamma-api.polymarket.com/markets"
GROUPS = ("80", "81")  # FBS, FCS
PREDICTOR = "cfb_scanner"
DEFAULT_THRESHOLD = 0.08  # flag when ESPN win prob exceeds market price by 8 points
UNRANKED = 99


@dataclass
class TeamState:
    name: str
    abbr: str
    score: int
    rank: Optional[int]
    wins: int
    losses: int
    team_id: str = ""

    @property
    def win_pct(self) -> float:
        games = self.wins + self.losses
        return self.wins / games if games else 0.5


@dataclass
class LiveGame:
    event_id: str
    start: Optional[datetime]
    detail: str
    home: TeamState
    away: TeamState
    period: int = 0
    seconds_left: Optional[float] = None  # in the current period
    possession: Optional[str] = None  # name of the team with the ball, when ESPN says

    def team(self, name: str) -> TeamState:
        return self.home if self.home.name == name else self.away


@dataclass
class Signal:
    game: LiveGame
    team: str
    espn_win_prob: float
    market_price: float
    gap: float
    label_favorite: Optional[str]
    label_basis: str
    market_slug: str
    league: str = "cfb"

    @property
    def margin(self) -> int:
        """Points the team is ahead (negative when behind)."""
        mine = self.game.team(self.team)
        other = self.game.away if mine is self.game.home else self.game.home
        return mine.score - other.score

    @property
    def leading(self) -> bool:
        return self.margin > 0

    @property
    def is_label_underdog(self) -> bool:
        return self.label_favorite is not None and self.label_favorite != self.team


@dataclass
class FirstScore:
    """A ranked team was scored on first by an unranked team (a likely early price dip)."""

    game: LiveGame
    ranked: TeamState
    scorer: TeamState
    play: str
    ranked_price: Optional[float]
    espn_win_prob: Optional[float]
    market_slug: str
    league: str = "cfb"


@dataclass
class RushEdge:
    """One team is averaging 5+ yards a carry and the other is not (the ground game is deciding it)."""

    game: LiveGame
    team: TeamState
    other: TeamState
    ypc: float
    carries: int
    other_ypc: float
    price: Optional[float]
    espn_win_prob: Optional[float]
    market_slug: str
    league: str = "cfb"


@dataclass
class RushAnomaly:
    """An offense is running far better on a defense than that defense normally allows."""

    game: LiveGame
    team: TeamState  # the offense
    defense: TeamState
    ypc: float
    carries: int
    allowed_ypc: float
    allowed_games: int
    price: Optional[float]
    espn_win_prob: Optional[float]
    market_slug: str
    league: str = "cfb"


ANOMALY_GAP = 2.0  # yards a carry above what the defense normally allows
RUSH_MIN_CARRIES = 15  # fewer carries than this is too small a sample
RUSH_YPC = 5.0


def live_rushing(summary: dict) -> dict[str, tuple[int, float]]:
    """{"home"/"away": (carries, yards)} from a live box score."""
    out: dict[str, tuple[int, float]] = {}
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        st = {s.get("name"): s.get("displayValue") for s in t.get("statistics") or []}
        try:
            out[t.get("homeAway")] = (int(st["rushingAttempts"]), float(st["rushingYards"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def rush_anomalies(client: httpx.AsyncClient, game: LiveGame, summary: dict, prices: dict[str, float],
                         home_wp: Optional[float], slug: str, league: str = "cfb") -> list[RushAnomaly]:
    """Offenses running at least ANOMALY_GAP yards a carry above what the defense across from them usually allows."""
    from src.backend.sports.defense_baseline import ypc_allowed

    found = []
    live = live_rushing(summary)
    for side, off, dfn in (("home", game.home, game.away), ("away", game.away, game.home)):
        carries, yards = live.get(side, (0, 0.0))
        if carries < RUSH_MIN_CARRIES or yards / carries < RUSH_YPC or not dfn.team_id:
            continue  # only look up a defense once its opponent is already running well
        base = await ypc_allowed(client, LEAGUES[league]["espn"], dfn.team_id)
        if not base or base[1] < 3 or yards / carries - base[0] < ANOMALY_GAP:
            continue
        price = next((v for k, v in prices.items() if norm(k) in norm(off.name) or norm(off.name) in norm(k)), None)
        wp = None if home_wp is None else (home_wp if off is game.home else 1 - home_wp)
        found.append(RushAnomaly(game, off, dfn, yards / carries, carries, base[0], base[1], price, wp, slug, league))
    return found


def rush_edge(game: LiveGame, summary: dict, prices: dict[str, float], home_wp: Optional[float], slug: str,
              league: str = "cfb") -> Optional[RushEdge]:
    """A team at 5.0+ yards a carry (15+ carries) while the opponent is under 5.0. None when both or neither."""
    stats: dict[str, tuple[int, float]] = {}  # "home"/"away" -> (carries, yards)
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        st = {s.get("name"): s.get("displayValue") for s in t.get("statistics") or []}
        try:
            stats[t.get("homeAway")] = (int(st["rushingAttempts"]), float(st["rushingYards"]))
        except (KeyError, TypeError, ValueError):
            continue
    if "home" not in stats or "away" not in stats:
        return None
    ypc = {k: (y / n if n else 0.0) for k, (n, y) in stats.items()}
    hot = [k for k in ("home", "away") if stats[k][0] >= RUSH_MIN_CARRIES and ypc[k] >= RUSH_YPC]
    if len(hot) != 1:
        return None
    side = hot[0]
    team, other = (game.home, game.away) if side == "home" else (game.away, game.home)
    price = next((v for k, v in prices.items() if norm(k) in norm(team.name) or norm(team.name) in norm(k)), None)
    wp = None if home_wp is None else (home_wp if team is game.home else 1 - home_wp)
    return RushEdge(game, team, other, ypc[side], stats[side][0], ypc["home" if side == "away" else "away"], price, wp, slug, league)


def norm(name: str) -> str:
    """Lowercase, strip punctuation, and expand 'St' so ESPN and Polymarket names compare."""
    s = re.sub(r"[^a-z0-9 ]", "", name.lower().replace("&", " and "))
    s = re.sub(r"\bst\b", "state", s)
    return re.sub(r"\s+", " ", s).strip()


def _record(team: dict) -> tuple[int, int]:
    for rec in team.get("records") or []:
        if rec.get("type") == "total":
            m = re.match(r"(\d+)-(\d+)", rec.get("summary", ""))
            if m:
                return int(m.group(1)), int(m.group(2))
    return 0, 0


def _team_state(comp: dict) -> TeamState:
    rank = (comp.get("curatedRank") or {}).get("current")
    wins, losses = _record(comp)
    return TeamState(
        name=comp["team"]["location"],
        abbr=comp["team"].get("abbreviation", ""),
        score=int(comp.get("score") or 0),
        rank=rank if rank and rank != UNRANKED else None,
        wins=wins,
        losses=losses,
        team_id=str(comp["team"].get("id", "")),
    )


def parse_scoreboard(payload: dict, state: str = "in") -> list[LiveGame]:
    """Extract games in the given ESPN state ('in' = live) from a scoreboard payload."""
    games = []
    for event in payload.get("events", []):
        comp = event["competitions"][0]
        if comp["status"]["type"]["state"] != state:
            continue
        by_side = {c["homeAway"]: c for c in comp["competitors"]}
        if "home" not in by_side or "away" not in by_side:
            continue
        ids = {c["id"]: c["team"]["location"] for c in comp["competitors"] if c.get("id")}
        status = comp["status"]
        start = None
        if event.get("date"):
            start = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
        games.append(
            LiveGame(
                event_id=event["id"],
                start=start,
                detail=comp["status"]["type"].get("shortDetail", ""),
                home=_team_state(by_side["home"]),
                away=_team_state(by_side["away"]),
                period=int(status.get("period") or 0),
                seconds_left=status.get("clock"),
                possession=ids.get(str((comp.get("situation") or {}).get("possession"))),
            )
        )
    return games


def parse_summary(summary: dict) -> tuple[Optional[float], Optional[str]]:
    """Return (latest home win probability 0-1, pregame spread text like 'MICH -6.5')."""
    wp = summary.get("winprobability") or []
    home_wp = wp[-1]["homeWinPercentage"] if wp else None
    pick = summary.get("pickcenter") or []
    spread = pick[0].get("details") if pick else None
    return home_wp, spread


def label_favorite(game: LiveGame, spread: Optional[str]) -> tuple[Optional[str], str]:
    """Who the market's label says is the favorite, and what that is based on."""
    if spread:
        m = re.match(r"([A-Za-z&.\-]+)\s+(-\d+(?:\.\d+)?)", spread)
        if m:
            for team in (game.home, game.away):
                if team.abbr.upper() == m.group(1).upper():
                    return team.name, f"spread {spread}"
    h, a = game.home, game.away
    if h.rank or a.rank:
        if h.rank and a.rank:
            return (h.name if h.rank < a.rank else a.name), "rank"
        return (h.name if h.rank else a.name), "rank"
    if abs(h.win_pct - a.win_pct) >= 0.2:
        return (h.name if h.win_pct > a.win_pct else a.name), "record"
    return None, "none"


def match_market(game: LiveGame, markets: list[dict]) -> Optional[dict]:
    """Find the moneyline market whose two outcomes are this game's two teams."""
    want = {norm(game.home.name), norm(game.away.name)}
    for m in markets:
        outcomes = m.get("outcomes")
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if outcomes and {norm(o) for o in outcomes} == want:
            return m
    return None


def outcome_prices(market: dict) -> dict[str, float]:
    """Map team name -> live price (0-1) from a gamma market payload."""
    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")
    outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
    prices = json.loads(prices) if isinstance(prices, str) else prices
    return {o: float(p) for o, p in zip(outcomes or [], prices or [])}


def evaluate(
    game: LiveGame,
    home_wp: float,
    prices: dict[str, float],
    spread: Optional[str],
    slug: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[Signal]:
    """Flag teams whose market price trails ESPN's win probability by >= threshold."""
    favorite, basis = label_favorite(game, spread)
    by_norm = {norm(k): v for k, v in prices.items()}
    signals = []
    for team, wp in ((game.home, home_wp), (game.away, 1 - home_wp)):
        price = by_norm.get(norm(team.name))
        if price is None:
            continue
        gap = wp - price
        if gap >= threshold:
            signals.append(
                Signal(game, team.name, wp, price, gap, favorite, basis, slug)
            )
    return signals


def first_score_event(
    game: LiveGame, summary: dict, prices: dict[str, float], home_wp: Optional[float], slug: str,
    league: str = "cfb",
) -> Optional[FirstScore]:
    """The ranked team was scored on first by an UNRANKED team, and the game is still in the 1st or 2nd quarter.

    If the first scorer is also ranked, or the ranked team scored first, nothing qualifies. Uses the
    first entry of ESPN's scoring plays so a quick answering score does not hide the event.
    """
    plays = summary.get("scoringPlays") or []
    if not plays or not re.search(r"\b(1st|2nd)\b", game.detail or ""):
        return None
    scorer_name = norm((plays[0].get("team") or {}).get("displayName", ""))
    scorer = next((t for t in (game.home, game.away) if norm(t.name) and norm(t.name) in scorer_name), None)
    if scorer is None:
        return None
    ranked = game.away if scorer is game.home else game.home
    if ranked.rank is None or ranked.rank > 25 or scorer.rank is not None:
        return None
    price = next((v for k, v in prices.items() if norm(k) in norm(ranked.name) or norm(ranked.name) in norm(k)), None)
    wp = None if home_wp is None else (home_wp if ranked is game.home else 1 - home_wp)
    p = plays[0]
    text = f"Q{(p.get('period') or {}).get('number', '?')} {(p.get('clock') or {}).get('displayValue', '')}: {p.get('text', '')}".strip()
    return FirstScore(game, ranked, scorer, text, price, wp, slug, league)


async def _get_json(client: httpx.AsyncClient, url: str, **params: Any) -> Any:
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_live_games(client: httpx.AsyncClient, league: str = "cfb") -> list[LiveGame]:
    games: dict[str, LiveGame] = {}
    cfg = LEAGUES[league]
    for group in cfg["groups"]:
        params = {"limit": 200, **({"groups": group} if group else {})}
        payload = await _get_json(client, f"{cfg['espn']}/scoreboard", **params)
        for g in parse_scoreboard(payload):
            games[g.event_id] = g
    return list(games.values())


async def _cfb_moneyline_markets(league: str = "cfb") -> list[tuple[str, str]]:
    """(slug, title) of cached CFB moneyline markets (titles like 'A vs. B', not spreads/totals)."""
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Market.slug, Market.title).where(
                Market.slug.like(f"{LEAGUES[league]['prefix']}%"), Market.is_active.is_(True)
            )
        )
    return [
        (slug, title) for slug, title in rows
        if " vs. " in title and ":" not in title and "-spread-" not in slug and "-total-" not in slug
    ]


def candidate_slugs(game: LiveGame, markets: list[tuple[str, str]]) -> list[str]:
    """Slugs whose cached title names both teams, newest date first (cheap pre-filter)."""
    home, away = norm(game.home.name), norm(game.away.name)
    hits = []
    for slug, title in markets:
        parts = [norm(p) for p in title.split(" vs. ")]
        if set(parts) == {home, away}:
            hits.append(slug)
    return sorted(hits, reverse=True)


async def scan_live(threshold: float = DEFAULT_THRESHOLD, league: str = "cfb", all_signals: bool = False,
                    events: Optional[list] = None) -> list[Signal]:
    """Scan live CFB games and return mispricing signals (also persists them)."""
    signals: list[Signal] = []
    markets = await _cfb_moneyline_markets(league)
    async with httpx.AsyncClient(timeout=20.0) as client:
        games = await fetch_live_games(client, league)
        for game in games:
            try:
                market = None
                for slug in candidate_slugs(game, markets)[:2]:
                    data = await _get_json(client, GAMMA_MARKETS, slug=slug, _=int(time.time() * 1000))  # defeat the 5 min CDN cache
                    if data and match_market(game, data):
                        market = data[0]
                        break
                if market is None:
                    continue  # no market, so skip the ESPN summary call
                summary = await _get_json(client, f"{LEAGUES[league]['espn']}/summary", event=game.event_id)
                home_wp, spread = parse_summary(summary)
                if home_wp is None:
                    continue
                if events is not None:
                    events.extend(await rush_anomalies(client, game, summary, outcome_prices(market), home_wp, market["slug"], league))
                    edge = rush_edge(game, summary, outcome_prices(market), home_wp, market["slug"], league)
                    if edge:
                        events.append(edge)
                if events is not None and league == "cfb":
                    ev = first_score_event(game, summary, outcome_prices(market), home_wp, market["slug"], league)
                    if ev:
                        events.append(ev)
                found = evaluate(game, home_wp, outcome_prices(market), spread, market["slug"], -1.0 if all_signals else threshold)
                for sig in found:
                    sig.league = league
                signals += found
            except Exception as e:  # one bad game must not stop the scan
                logger.warning(f"CFB scan skipped game {game.event_id}: {e}")
    # The ledger keeps only real price-vs-game gaps, even when the caller asked for every team
    await persist([x for x in signals if x.gap >= threshold])
    return signals


async def persist(signals: list[Signal]) -> int:
    """Write first-seen signals to the prediction ledger (one row per game and team)."""
    saved = 0
    async with async_session_factory() as session:
        for s in signals:
            question = f"{s.team} wins"
            exists = await session.scalar(
                select(Prediction.id).where(
                    Prediction.predictor == (PREDICTOR if s.league == "cfb" else f"{s.league}_scanner"),
                    Prediction.game_id == s.game.event_id,
                    Prediction.question == question,
                )
            )
            if exists:
                continue
            session.add(
                Prediction(
                    sport=LEAGUES[s.league]["sport"],
                    game_id=s.game.event_id,
                    question=question,
                    predictor=PREDICTOR if s.league == "cfb" else f"{s.league}_scanner",
                    probability=s.espn_win_prob,
                    market_price=s.market_price,
                    market_id=s.market_slug,
                    game_time=s.game.start.astimezone(timezone.utc).replace(tzinfo=None)
                    if s.game.start else None,
                )
            )
            saved += 1
        await session.commit()
    return saved

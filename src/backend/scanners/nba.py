"""
NBA Recency Momentum Scanner.

Same recency-vs-record mispricing idea as the MLB/NFL scanners: rolling
scoring margin over the last 5 games vs. season point differential and
streak, surfacing teams retail markets are still pricing off a stale
record. NBA's 82-game season means recency signal is noisier per-game
than NFL but the last 5 games still meaningfully lead a stale record.
"""

import time
from typing import Any, Dict, List

from src.backend.scanners.espn_common import fetch_standings, fetch_recency_for_teams

SPORT = "basketball"
LEAGUE = "nba"

_CACHE: Dict[str, Any] = {}
_CACHE_TIMESTAMP: float = 0
CACHE_TTL_SECONDS = 300


async def fetch_nba_standings() -> List[Dict[str, Any]]:
    return await fetch_standings(SPORT, LEAGUE)


async def fetch_team_recency(team_id: int) -> Dict[str, Any]:
    games = (await fetch_recency_for_teams(SPORT, LEAGUE, [team_id], limit=5))[team_id]
    return _summarize_recency(games)


def _summarize_recency(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(games)
    margin_avg = round(sum(g["margin"] for g in games) / n, 1) if n else 0.0
    wins = sum(1 for g in games if g["won"])
    points_for_avg = round(sum(g["team_score"] for g in games) / n, 1) if n else 0.0
    return {
        "games_analyzed": n,
        "recent_wins": wins,
        "recent_margin_avg": margin_avg,
        "recent_points_for_avg": points_for_avg,
        "recent_game_log": games,
    }


def compute_momentum_intelligence(team: Dict[str, Any], recency: Dict[str, Any]) -> Dict[str, Any]:
    """
    Underdog = sub-.400 win pct; contender = .600+ (NBA standings compress
    less dramatically than NFL over an 82-game season).
    """
    win_pct = team.get("win_pct", 0.5)
    margin_avg = recency.get("recent_margin_avg", 0.0)
    recent_wins = recency.get("recent_wins", 0)
    games_analyzed = recency.get("games_analyzed", 0)
    streak_type = team.get("streak_type", "")
    streak_num = team.get("streak_num", 0)
    season_margin = (team.get("points_for", 0) - team.get("points_against", 0)) / max(
        team.get("wins", 0) + team.get("losses", 0), 1
    )

    margin_delta = (margin_avg - season_margin) * 1.2
    streak_pts = 0
    if streak_type == "wins":
        streak_pts = min(streak_num * 5, 25)
    elif streak_type == "losses":
        streak_pts = max(-streak_num * 4, -25)

    momentum_score = int(max(5, min(99, 50 + margin_delta + streak_pts)))

    is_underdog = win_pct <= 0.400
    is_contender = win_pct >= 0.600

    regime = "BALANCED FORM"
    edge_detected = False
    headline = ""
    psychology_notes = ""
    prewire_action = ""

    if is_underdog and games_analyzed >= 3 and (recent_wins >= 3 or margin_avg >= 4):
        regime = "UNDERDOG SURGE 🔥"
        edge_detected = True
        headline = (
            f"{team['name']} is {recent_wins}-{games_analyzed - recent_wins} in its last "
            f"{games_analyzed} with a +{margin_avg} scoring margin despite a {int(win_pct*100)}% season record"
        )
        psychology_notes = (
            "Retail markets are still anchored on the season-long record; a rotation or lineup "
            "change is producing form well above the win total, creating value entry points "
            "before the market re-prices."
        )
        prewire_action = "Enter early on the moneyline/spread before public perception catches up to the trend."
    elif is_contender and games_analyzed >= 3 and (margin_avg <= -4 or (streak_type == "losses" and streak_num >= 2)):
        regime = "COASTING FAVORITE ⚠️"
        edge_detected = True
        headline = f"{team['name']} is outscoring opponents by only {margin_avg} over its last {games_analyzed} despite a {int(win_pct*100)}% record"
        psychology_notes = (
            "Public is still betting the season record and name recognition; recent form (rest, "
            "load management, injuries) has softened, offering negative-EV prices as a favorite."
        )
        prewire_action = "Fade as a large favorite or take the opposing underdog against the spread."
    elif is_contender and momentum_score >= 70:
        regime = "PEAK CONTENDER ⚡"
        headline = f"{team['name']} is playing at or above its season form (+{margin_avg} L{games_analyzed})"
        psychology_notes = "Fairly priced by the market; no exploitable recency gap."
        prewire_action = "Use only as a fair-value parlay anchor leg."
    elif is_underdog and momentum_score <= 30:
        regime = "COLD CELLAR ❄️"
        headline = f"{team['name']} showing no recent form improvement to offset a weak record"
        psychology_notes = "No recency edge detected; season record and recent play agree."
        prewire_action = "Avoid backing until form data improves."

    return {
        "regime": regime,
        "momentum_score": momentum_score,
        "edge_detected": edge_detected,
        "headline": headline,
        "psychology_notes": psychology_notes,
        "prewire_action": prewire_action,
        "implied_market_price_cents": int(win_pct * 100),
        "true_recency_fair_cents": int((momentum_score / 100) * 100),
        "discrepancy_cents": int(((momentum_score / 100) - win_pct) * 100),
    }


async def get_nba_momentum_board() -> Dict[str, Any]:
    global _CACHE, _CACHE_TIMESTAMP
    now = time.time()
    if "board" in _CACHE and (now - _CACHE_TIMESTAMP) < CACHE_TTL_SECONDS:
        return _CACHE["board"]

    standings = await fetch_nba_standings()
    if not standings:
        return {"total_teams": 0, "teams": [], "underdog_surges": [], "coasting_traps": []}

    recency_by_team = await fetch_recency_for_teams(
        SPORT, LEAGUE, [t["team_id"] for t in standings], limit=5
    )

    enriched: List[Dict[str, Any]] = []
    surges: List[Dict[str, Any]] = []
    traps: List[Dict[str, Any]] = []

    for team in standings:
        recency = _summarize_recency(recency_by_team.get(team["team_id"], []))
        intel = compute_momentum_intelligence(team, recency)
        combined = {**team, **recency, **intel}
        enriched.append(combined)
        if "UNDERDOG SURGE" in intel["regime"]:
            surges.append(combined)
        elif "COASTING FAVORITE" in intel["regime"]:
            traps.append(combined)

    surges.sort(key=lambda x: x["discrepancy_cents"], reverse=True)
    enriched.sort(key=lambda x: x["momentum_score"], reverse=True)

    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total_teams": len(enriched),
        "underdog_surges_count": len(surges),
        "coasting_traps_count": len(traps),
        "underdog_surges": surges,
        "coasting_traps": traps,
        "all_teams": enriched,
    }
    _CACHE["board"] = result
    _CACHE_TIMESTAMP = now
    return result


async def get_team_momentum_deep_dive(team_id: int) -> Dict[str, Any]:
    standings = await fetch_nba_standings()
    team = next((t for t in standings if t["team_id"] == team_id), None)
    if not team:
        return {"error": f"NBA team {team_id} not found"}

    recency = await fetch_team_recency(team_id)
    intel = compute_momentum_intelligence(team, recency)
    return {"team": team, "recency": recency, "intelligence": intel}

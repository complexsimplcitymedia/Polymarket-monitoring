"""
Stat tables for college football (by conference) and the NFL.

One row per team: record and recent form, home and road splits, record against ranked and
winning teams, offense, defense and turnovers (each with its rank among the league), the AP
rank, and the next game. Built from ESPN's public schedule, statistics, standings and
rankings endpoints. ESPN does not publish team yards allowed, so defense is points allowed
plus sacks and takeaways.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

SITE = "https://site.api.espn.com/apis/site/v2/sports/football"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/football"
UNRANKED = 99
RANKED_CUT = 25
CACHE_SECONDS = 1800
# Conference ids in ESPN's college football standings
CFB_CONFERENCES = {1: "ACC", 4: "Big 12", 5: "Big Ten", 8: "SEC", 9: "Pac-12", 12: "Conference USA",
                   15: "MAC", 17: "Mountain West", 18: "Independents", 37: "Sun Belt", 151: "American"}


@dataclass(frozen=True)
class FGame:
    date: str
    opp_id: str
    opp_name: str
    home: Optional[bool]  # None on a neutral field
    pf: int
    pa: int
    opp_rank: Optional[int]

    @property
    def won(self) -> bool:
        return self.pf > self.pa


def _score(competitor: dict[str, Any]) -> int:
    s = competitor.get("score")
    if isinstance(s, dict):
        return int(float(s.get("value", 0)))
    return int(float(s or 0))


def parse_schedule(payload: dict[str, Any], team_id: str) -> tuple[list[FGame], Optional[dict[str, Any]]]:
    """Completed games, plus the next game if there is one."""
    games: list[FGame] = []
    upcoming: Optional[dict[str, Any]] = None
    for ev in payload.get("events", []):
        comp = ev["competitions"][0]
        mine = next((c for c in comp["competitors"] if str(c["team"]["id"]) == str(team_id)), None)
        other = next((c for c in comp["competitors"] if str(c["team"]["id"]) != str(team_id)), None)
        if not mine or not other:
            continue
        home = None if comp.get("neutralSite") else mine["homeAway"] == "home"
        if comp["status"]["type"]["completed"]:
            rank = (other.get("curatedRank") or {}).get("current")
            games.append(FGame(
                date=ev["date"], opp_id=str(other["team"]["id"]), opp_name=other["team"]["displayName"],
                home=home, pf=_score(mine), pa=_score(other),
                opp_rank=rank if rank and rank != UNRANKED else None,
            ))
        elif upcoming is None:
            upcoming = {"date": ev["date"], "opponent": other["team"]["displayName"], "home": home,
                        "opp_rank": (other.get("curatedRank") or {}).get("current")}
    return sorted(games, key=lambda g: g.date), upcoming


def parse_stats(payload: dict[str, Any]) -> dict[str, float]:
    """Flatten ESPN's category lists into 'category.stat' -> value."""
    flat: dict[str, float] = {}
    for cat in ((payload.get("results") or {}).get("stats") or {}).get("categories", []):
        for s in cat.get("stats", []):
            if s.get("value") is not None:
                flat.setdefault(f"{cat['name']}.{s['name']}", float(s["value"]))
    return flat


def per_game(flat: dict[str, float]) -> dict[str, Optional[float]]:
    """Offense, defense and turnover columns per game from the flattened season stats."""
    gp = flat.get("rushing.teamGamesPlayed") or flat.get("general.gamesPlayed") or 0
    if not gp:
        return {k: None for k in ("yds", "pass_yds", "rush_yds", "third_pct", "sacks", "takeaways", "giveaways", "turnover_margin")}
    takeaways = flat.get("defensiveInterceptions.interceptions", 0) + flat.get("general.fumblesRecovered", 0)
    giveaways = (flat.get("passing.interceptions", 0) + flat.get("rushing.rushingFumblesLost", 0)
                 + flat.get("receiving.receivingFumblesLost", 0))
    return {
        "yds": flat.get("rushing.totalYards", 0) / gp,
        "pass_yds": flat.get("passing.netPassingYardsPerGame"),
        "rush_yds": flat.get("rushing.rushingYardsPerGame"),
        "third_pct": flat.get("miscellaneous.thirdDownConvPct"),
        "sacks": flat.get("defensive.sacks", 0) / gp,
        "takeaways": takeaways / gp,
        "giveaways": giveaways / gp,
        "turnover_margin": (takeaways - giveaways) / gp,
    }


def wl(games: list[FGame]) -> list[int]:
    wins = sum(1 for g in games if g.won)
    return [wins, len(games) - wins]


def rank_values(values: dict[str, float], higher_is_better: bool) -> dict[str, int]:
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_better)
    ranks, last_value, last_rank = {}, None, 0
    for position, (key, value) in enumerate(ordered, start=1):
        if value != last_value:
            last_rank, last_value = position, value
        ranks[key] = last_rank
    return ranks


# column -> (higher is better)
OFFENSE = {"ppg": True, "yds": True, "pass_yds": True, "rush_yds": True, "third_pct": True}
DEFENSE = {"papg": False, "sacks": True, "takeaways": True, "giveaways": False, "turnover_margin": True}


def build_rows(
    teams: dict[str, dict[str, Any]], games: dict[str, list[FGame]], stats: dict[str, dict[str, Optional[float]]],
    upcoming: dict[str, Optional[dict[str, Any]]], polls: dict[str, int],
) -> list[dict[str, Any]]:
    """One row per team with ranks among all given teams. Pure: network data is passed in."""
    pct = {tid: (wl(g)[0] / len(g)) for tid, g in games.items() if g}
    values: dict[str, dict[str, float]] = {}
    for tid, g in games.items():
        if not g:
            continue
        s = stats.get(tid, {})
        v = {"ppg": sum(x.pf for x in g) / len(g), "papg": sum(x.pa for x in g) / len(g)}
        v.update({k: s[k] for k in ("yds", "pass_yds", "rush_yds", "third_pct", "sacks", "takeaways", "giveaways", "turnover_margin")
                  if s.get(k) is not None})
        v["win_pct"] = pct[tid]
        v["diff"] = v["ppg"] - v["papg"]
        values[tid] = v
    ranks: dict[str, dict[str, int]] = {}
    for key, hi in {**OFFENSE, **DEFENSE, "win_pct": True, "diff": True}.items():
        ranks[key] = rank_values({t: v[key] for t, v in values.items() if key in v}, hi)

    rows = []
    for tid, meta in teams.items():
        g = games.get(tid) or []
        if not g:
            continue
        v = values[tid]
        known = [x for x in g if x.opp_id in pct]
        vs_ranked = [x for x in g if x.opp_rank is not None]
        vs_winning = [x for x in known if pct[x.opp_id] >= 0.5]
        cell = lambda key: {"value": v[key], "rank": ranks[key].get(tid)} if key in v else None  # noqa: E731
        rows.append({
            "team": meta["name"], "id": tid, "conference": meta["group"], "ap_rank": polls.get(tid),
            "record": {"wins": wl(g)[0], "losses": wl(g)[1], "pct": v["win_pct"], "rank": ranks["win_pct"][tid]},
            "diff": cell("diff"),
            "form": {"last_3": wl(g[-3:]), "last_5": wl(g[-5:])},
            "splits": {"home": wl([x for x in g if x.home is True]), "road": wl([x for x in g if x.home is False]),
                       "neutral": wl([x for x in g if x.home is None])},
            "quality": {"vs_ranked": wl(vs_ranked), "vs_winning": wl(vs_winning),
                        "avg_opp_pct": (sum(pct[x.opp_id] for x in known) / len(known)) if known else None,
                        "outside_league": wl([x for x in g if x.opp_id not in pct]),
                        "known_games": len(known)},
            "offense": {k: cell(k) for k in OFFENSE},
            "defense": {k: cell(k) for k in DEFENSE},
            "next_game": upcoming.get(tid),
        })
    return rows


def _leaf_entries(node: dict[str, Any], label: str, out: dict[str, dict[str, Any]]) -> None:
    for e in ((node.get("standings") or {}).get("entries") or []):
        out[str(e["team"]["id"])] = {"name": e["team"]["displayName"], "group": label}
    for child in node.get("children") or []:
        _leaf_entries(child, child.get("name") or label, out)


async def _directory(client: httpx.AsyncClient, league: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if league == "cfb":
        async def one(group_id: int, label: str) -> None:
            r = await client.get(f"{STANDINGS}/college-football/standings", params={"group": group_id, "season": 2026})
            if r.status_code == 200:
                _leaf_entries(r.json(), label, {})  # validates shape
                found: dict[str, dict[str, Any]] = {}
                _leaf_entries(r.json(), label, found)
                for tid, meta in found.items():
                    out[tid] = {"name": meta["name"], "group": label}
        await asyncio.gather(*[one(i, n) for i, n in CFB_CONFERENCES.items()])
    else:
        r = await client.get(f"{STANDINGS}/nfl/standings", params={"season": 2026, "level": 3})
        r.raise_for_status()
        _leaf_entries(r.json(), "NFL", out)
    return out


_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = asyncio.Lock()


async def football_table(league: str, refresh: bool = False) -> dict[str, Any]:
    """The table for ``league`` ('cfb' or 'nfl'), cached for 30 minutes."""
    espn = {"cfb": "college-football", "nfl": "nfl"}[league]
    async with _lock:
        hit = _cache.get(league)
        if not refresh and hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
        async with httpx.AsyncClient(timeout=40.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            teams = await _directory(client, league)
            sem = asyncio.Semaphore(10)

            async def fetch(tid: str) -> tuple[str, list[FGame], Optional[dict[str, Any]], dict[str, Optional[float]]]:
                async with sem:
                    sched = await client.get(f"{SITE}/{espn}/teams/{tid}/schedule", params={"season": 2026})
                    stat = await client.get(f"{SITE}/{espn}/teams/{tid}/statistics")
                games, nxt = parse_schedule(sched.json(), tid) if sched.status_code == 200 else ([], None)
                flat = parse_stats(stat.json()) if stat.status_code == 200 else {}
                return tid, games, nxt, per_game(flat)

            results = await asyncio.gather(*[fetch(t) for t in teams], return_exceptions=True)
            games, stats, upcoming = {}, {}, {}
            for r in results:
                if isinstance(r, Exception):
                    continue
                tid, g, nxt, st = r
                games[tid], upcoming[tid], stats[tid] = g, nxt, st
            polls: dict[str, int] = {}
            if league == "cfb":
                poll = await client.get(f"{SITE}/college-football/rankings")
                if poll.status_code == 200:
                    ap = next((p for p in poll.json().get("rankings", []) if p.get("name") == "AP Top 25"), None)
                    for rk in (ap or {}).get("ranks", []):
                        polls[str(rk["team"]["id"])] = rk["current"]
        rows = build_rows(teams, games, stats, upcoming, polls)
        result = {"league": league, "as_of": time.time(), "league_size": len(rows),
                  "groups": sorted({r["conference"] for r in rows}), "teams": rows}
        _cache[league] = (time.monotonic(), result)
        return result

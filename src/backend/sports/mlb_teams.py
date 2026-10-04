"""
Stat table for the MLB teams still in the postseason.

One row per team with every column we have used to review picks: record and recent form,
record against good and bad teams, offense, pitching and defense (season and September),
each with its rank among all 30 teams, plus the next game and starting pitchers.
"""

import asyncio
import time
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from src.backend.sports.mlb_context import (
    MLB_API,
    Game,
    fetch_pitcher_era,
    fetch_season_games,
    team_form,
)

SEASON = 2026
SEASON_START = "2026-03-01"
SEPT_START = "2026-09-01"
REGULAR_SEASON_END = "2026-09-28"
CALIFORNIA = ("Angels", "Dodgers", "Padres", "Giants", "Athletics")
CACHE_SECONDS = 1800
FAR_FUTURE = "2100-01-01"


def rank_map(values: dict[str, float], higher_is_better: bool) -> dict[str, int]:
    """1 = best. Ties share the better rank."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_better)
    ranks: dict[str, int] = {}
    last_value, last_rank = None, 0
    for position, (team, value) in enumerate(ordered, start=1):
        if value != last_value:
            last_rank, last_value = position, value
        ranks[team] = last_rank
    return ranks


def win_pcts(games: list[Game]) -> dict[str, float]:
    wins: dict[str, int] = {}
    played: dict[str, int] = {}
    for g in games:
        for team in (g.away, g.home):
            played[team] = played.get(team, 0) + 1
        wins[g.winner] = wins.get(g.winner, 0) + 1
    return {t: wins.get(t, 0) / n for t, n in played.items()}


def quality_split(games: list[Game], team: str, pct: dict[str, float], top: set[str], bottom: set[str]) -> dict[str, Any]:
    """Record against .500+ teams, the top group and the bottom group, plus schedule strength."""
    buckets = {"above_500": [0, 0], "top": [0, 0], "bottom": [0, 0]}
    opp_pcts: list[float] = []
    for g in games:
        if team not in (g.away, g.home):
            continue
        opp = g.home if g.away == team else g.away
        opp_pcts.append(pct[opp])
        slot = 0 if g.winner == team else 1
        if pct[opp] >= 0.5:
            buckets["above_500"][slot] += 1
        if opp in top:
            buckets["top"][slot] += 1
        if opp in bottom:
            buckets["bottom"][slot] += 1
    return {
        "vs_above_500": buckets["above_500"],
        "vs_top_12": buckets["top"],
        "vs_bottom_10": buckets["bottom"],
        "avg_opponent_pct": sum(opp_pcts) / len(opp_pcts) if opp_pcts else None,
    }


def biggest_swing(games: list[Game], team: str, window: int = 40) -> Optional[dict[str, Any]]:
    """Best and worst stretch of ``window`` games: how far form has moved around the season record."""
    mine = sorted((g for g in games if team in (g.away, g.home)), key=lambda g: g.day)
    results = [1 if g.winner == team else 0 for g in mine]
    if len(results) < window:
        return None
    sums = [sum(results[i:i + window]) for i in range(len(results) - window + 1)]
    best, worst = max(range(len(sums)), key=sums.__getitem__), min(range(len(sums)), key=sums.__getitem__)
    return {
        "window": window,
        "best": [sums[best], window - sums[best]],
        "worst": [sums[worst], window - sums[worst]],
    }


def _stat(split: dict[str, Any]) -> dict[str, float]:
    h, p, f = split["hitting"], split["pitching"], split["fielding"]
    games = int(h["gamesPlayed"]) or 1
    return {
        "rpg": int(h["runs"]) / games,
        "ops": float(h["ops"]),
        "avg": float(h["avg"]),
        "era": float(p["era"]),
        "whip": float(p["whip"]),
        "fld": float(f["fielding"]),
        "errors_pg": int(f["errors"]) / games,
    }


STAT_DIRECTION = {  # True = higher is better
    "rpg": True, "ops": True, "avg": True, "era": False, "whip": False, "fld": True, "errors_pg": False,
}


async def _team_stats(client: httpx.AsyncClient, sem: asyncio.Semaphore, team_id: int, window: dict[str, Any]) -> dict[str, float]:
    async def one(group: str) -> dict[str, Any]:
        async with sem:
            resp = await client.get(f"{MLB_API}/teams/{team_id}/stats", params={"group": group, **window})
            resp.raise_for_status()
            return resp.json()["stats"][0]["splits"][0]["stat"]

    hitting, pitching, fielding = await asyncio.gather(one("hitting"), one("pitching"), one("fielding"))
    return _stat({"hitting": hitting, "pitching": pitching, "fielding": fielding})


async def _remaining_teams(client: httpx.AsyncClient) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Teams scheduled in a postseason series from yesterday onward, with each one's next game."""
    start = (date.today() - timedelta(days=1)).isoformat()
    end = (date.today() + timedelta(days=10)).isoformat()
    teams: dict[str, dict[str, Any]] = {}
    nxt: dict[str, dict[str, Any]] = {}
    for game_type in ("D", "L", "W"):
        resp = await client.get(
            f"{MLB_API}/schedule",
            params={"sportId": 1, "startDate": start, "endDate": end, "gameType": game_type,
                    "hydrate": "team,probablePitcher,seriesStatus"},
        )
        resp.raise_for_status()
        for d in resp.json().get("dates", []):
            for g in d["games"]:
                away, home = g["teams"]["away"], g["teams"]["home"]
                for side, other in ((away, home), (home, away)):
                    name = side["team"]["name"]
                    teams[name] = {"id": side["team"]["id"], "round": g.get("seriesDescription", "")}
                    if g["status"]["abstractGameState"] == "Final" or name in nxt:
                        continue
                    def starter(t: dict[str, Any]) -> Optional[dict[str, Any]]:
                        p = t.get("probablePitcher")
                        return {"id": p["id"], "name": p["fullName"]} if p else None
                    nxt[name] = {
                        "date": d["date"], "time": g["gameDate"], "opponent": other["team"]["name"],
                        "home": side is home, "game": g.get("seriesGameNumber"), "round": g.get("seriesDescription", ""),
                        "series": (g.get("seriesStatus") or {}).get("result", ""),
                        "own_starter": starter(side), "opp_starter": starter(other),
                    }
    return teams, nxt


def build_rows(
    games: list[Game], remaining: list[str], names_to_id: dict[str, int],
    season: dict[str, dict[str, float]], sept: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Assemble one row per remaining team. Pure: all network data comes in as arguments."""
    pct = win_pcts(games)
    ordered = sorted(pct, key=pct.get, reverse=True)
    top, bottom = set(ordered[:12]), set(ordered[-10:])
    season_ranks = {k: rank_map({t: s[k] for t, s in season.items()}, hi) for k, hi in STAT_DIRECTION.items()}
    sept_ranks = {k: rank_map({t: s[k] for t, s in sept.items()}, hi) for k, hi in STAT_DIRECTION.items()}
    win_rank = rank_map(pct, True)

    rows = []
    for team in remaining:
        if team not in pct or team not in season or team not in sept:
            continue
        form = {n: team_form(games, team, FAR_FUTURE, n) for n in (10, 20, 50)}
        overall = team_form(games, team, FAR_FUTURE, 200)
        sept_games = [g for g in games if g.day >= SEPT_START and team in (g.away, g.home)]
        sept_wins = sum(1 for g in sept_games if g.winner == team)

        def block(stats: dict[str, dict[str, float]], ranks: dict[str, dict[str, int]]) -> dict[str, Any]:
            return {k: {"value": stats[team][k], "rank": ranks[k][team]} for k in STAT_DIRECTION}

        rows.append({
            "team": team,
            "id": names_to_id.get(team),
            "california": any(c in team for c in CALIFORNIA),
            "record": {
                "wins": overall.wins, "losses": overall.losses, "pct": pct[team], "rank": win_rank[team],
                "run_diff_per_game": overall.runs_for - overall.runs_against,
            },
            "form": {
                f"last_{n}": {"wins": f.wins, "losses": f.losses, "rf": f.runs_for, "ra": f.runs_against}
                for n, f in form.items() if f
            },
            "september": {"wins": sept_wins, "losses": len(sept_games) - sept_wins},
            "quality": quality_split(games, team, pct, top, bottom),
            "swing": biggest_swing(games, team),
            "season": block(season, season_ranks),
            "sept": block(sept, sept_ranks),
        })
    return rows


_cache: Optional[tuple[float, dict[str, Any]]] = None
_lock = asyncio.Lock()


async def team_table(refresh: bool = False) -> dict[str, Any]:
    """Fetch (or reuse for 30 minutes) the full table of remaining postseason teams."""
    global _cache
    async with _lock:
        if not refresh and _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
            return _cache[1]
        async with httpx.AsyncClient(timeout=40.0) as client:
            sem = asyncio.Semaphore(8)
            teams_resp = await client.get(f"{MLB_API}/teams", params={"sportId": 1, "season": SEASON})
            teams_resp.raise_for_status()
            names_to_id = {t["name"]: t["id"] for t in teams_resp.json()["teams"]}
            games, (remaining_info, next_games) = await asyncio.gather(
                fetch_season_games(client, SEASON_START, REGULAR_SEASON_END), _remaining_teams(client)
            )
            ids = list(names_to_id.items())
            season_stats, sept_stats = await asyncio.gather(
                asyncio.gather(*[_team_stats(client, sem, i, {"stats": "season", "season": SEASON}) for _, i in ids]),
                asyncio.gather(*[
                    _team_stats(client, sem, i, {"stats": "byDateRange", "startDate": SEPT_START,
                                                 "endDate": REGULAR_SEASON_END, "season": SEASON})
                    for _, i in ids
                ]),
            )
            season = {n: s for (n, _), s in zip(ids, season_stats)}
            sept = {n: s for (n, _), s in zip(ids, sept_stats)}
            rows = build_rows(games, sorted(remaining_info), names_to_id, season, sept)
            for row in rows:
                info = next_games.get(row["team"])
                if info:
                    for key in ("own_starter", "opp_starter"):
                        p = info[key]
                        if p:
                            p["era"] = await fetch_pitcher_era(client, p["id"], info["date"], SEASON_START)
                row["next_game"] = info
                row["round"] = remaining_info[row["team"]]["round"]
        result = {"as_of": time.time(), "teams": rows, "league_size": len(season)}
        _cache = (time.monotonic(), result)
        return result

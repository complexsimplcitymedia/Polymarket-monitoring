"""
Shared ESPN public API fetch layer for NFL and NBA scanners.

ESPN's site.api.espn.com exposes unauthenticated standings and per-team
schedule/score data with an identical shape across leagues, so the fetch
and parsing logic lives here once and the sport-specific modules only
supply the league path and their own momentum/regime thresholds.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


async def fetch_standings(sport: str, league: str) -> List[Dict[str, Any]]:
    """
    Fetch current standings for every team in a league, flattened across
    conferences. ESPN always resolves this to the live/current season, so
    no season year needs to be passed or hardcoded.
    """
    url = f"{ESPN_BASE}/v2/sports/{sport}/{league}/standings"

    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch {league} standings: HTTP {resp.status_code}")
            return []
        data = resp.json()

    teams: List[Dict[str, Any]] = []
    for conference in data.get("children", []):
        conf_name = conference.get("abbreviation") or conference.get("name", league.upper())
        entries = conference.get("standings", {}).get("entries", [])
        for rank, entry in enumerate(entries, start=1):
            team_info = entry.get("team", {})
            stats = {s.get("name"): s for s in entry.get("stats", []) if s.get("name")}

            def stat_val(key: str, default: float = 0.0) -> float:
                s = stats.get(key)
                return float(s["value"]) if s and s.get("value") is not None else default

            def stat_display(key: str, default: str = "-") -> str:
                s = stats.get(key)
                return s.get("displayValue", default) if s else default

            streak_display = stat_display("streak", "-")
            streak_type = "wins" if streak_display.startswith("W") else (
                "losses" if streak_display.startswith("L") else ""
            )
            try:
                streak_num = int(streak_display[1:]) if streak_type else 0
            except ValueError:
                streak_num = 0

            teams.append({
                "team_id": int(team_info.get("id")),
                "name": team_info.get("displayName", team_info.get("name", "")),
                "abbreviation": team_info.get("abbreviation", ""),
                "division": conf_name,
                "division_rank": rank,
                "wins": int(stat_val("wins")),
                "losses": int(stat_val("losses")),
                "ties": int(stat_val("ties")),
                "win_pct": stat_val("winPercent"),
                "streak_code": streak_display,
                "streak_type": streak_type,
                "streak_num": streak_num,
                "points_for": stat_val("pointsFor"),
                "points_against": stat_val("pointsAgainst"),
                "point_differential": stat_val("pointDifferential") or stat_val("differential"),
            })

    return teams


async def fetch_team_recent_games(
    sport: str, league: str, team_id: int, limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Fetch the most recent `limit` completed games for a team from its
    current-season schedule, with final score margin and win/loss.
    """
    url = f"{ESPN_BASE}/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule"

    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch schedule for team {team_id}: HTTP {resp.status_code}")
            return []
        data = resp.json()

    completed: List[Dict[str, Any]] = []
    for event in data.get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        status = comp.get("status", {}).get("type", {})
        if not status.get("completed"):
            continue

        competitors = comp.get("competitors", [])
        me = next((c for c in competitors if str(c.get("id")) == str(team_id)), None)
        opp = next((c for c in competitors if str(c.get("id")) != str(team_id)), None)
        if not me or not opp:
            continue

        my_score = float((me.get("score") or {}).get("value", 0))
        opp_score = float((opp.get("score") or {}).get("value", 0))

        completed.append({
            "date": event.get("date"),
            "won": bool(me.get("winner")),
            "team_score": my_score,
            "opponent_score": opp_score,
            "margin": my_score - opp_score,
        })

    return completed[-limit:]


async def fetch_recency_for_teams(
    sport: str, league: str, team_ids: List[int], limit: int = 5
) -> Dict[int, List[Dict[str, Any]]]:
    """Fetch recent games for many teams concurrently."""
    tasks = [fetch_team_recent_games(sport, league, tid, limit=limit) for tid in team_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: Dict[int, List[Dict[str, Any]]] = {}
    for tid, res in zip(team_ids, results):
        out[tid] = [] if isinstance(res, Exception) else res
    return out

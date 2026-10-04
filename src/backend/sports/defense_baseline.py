"""A defense's season rushing yards allowed per carry, built from its finished games' box scores.

ESPN does not publish yards allowed per team, so each completed game's box score is read once and cached
(a finished game never changes). It is only requested for a defense whose opponent is running well in a live game.
"""
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_games: dict[tuple[str, str], Optional[tuple[int, float]]] = {}  # (event id, team id) -> (carries, yards) the team ALLOWED


def rush_allowed_in_game(summary: dict, team_id: str) -> Optional[tuple[int, float]]:
    """Carries and rushing yards the opponent of ``team_id`` had in this game, or None when not readable."""
    for t in (summary.get("boxscore") or {}).get("teams") or []:
        if str((t.get("team") or {}).get("id")) == str(team_id):
            continue  # the team itself; its opponent's line is the yards it allowed
        st = {s.get("name"): s.get("displayValue") for s in t.get("statistics") or []}
        try:
            return int(st["rushingAttempts"]), float(st["rushingYards"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def season_ypc_allowed(lines: list[tuple[int, float]]) -> Optional[float]:
    carries = sum(n for n, _ in lines)
    return sum(y for _, y in lines) / carries if carries else None


async def ypc_allowed(client: httpx.AsyncClient, espn_base: str, team_id: str) -> Optional[tuple[float, int]]:
    """(yards per carry allowed this season, games counted) for a team, or None if it cannot be built."""
    try:
        sched = (await client.get(f"{espn_base}/teams/{team_id}/schedule")).json()
    except Exception as e:
        logger.warning(f"Schedule for team {team_id} unavailable: {e}")
        return None
    lines: list[tuple[int, float]] = []
    for ev in sched.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        if not (comp.get("status") or {}).get("type", {}).get("completed"):
            continue
        key = (str(ev["id"]), str(team_id))
        if key not in _games:
            try:
                summary = (await client.get(f"{espn_base}/summary", params={"event": ev["id"]})).json()
                _games[key] = rush_allowed_in_game(summary, team_id)
            except Exception as e:
                logger.warning(f"Box score {ev['id']} unavailable: {e}")
                continue  # try again next time, do not cache a failure
        if _games[key]:
            lines.append(_games[key])
    ypc = season_ypc_allowed(lines)
    return (ypc, len(lines)) if ypc is not None else None

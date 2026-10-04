"""College football (by conference) and NFL team tables."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.backend.sports.football_teams import football_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/football", tags=["Football"])


@router.get("/{league}/teams")
async def get_team_table(league: str, refresh: bool = False) -> Dict[str, Any]:
    """
    One row per team for ``cfb`` or ``nfl``: record and form, home and road splits, record
    against ranked and winning teams, offense, defense and turnovers with ranks among the
    league, the AP rank, and the next game. Cached for 30 minutes; the first build takes a
    little while for college football because it reads every FBS team.
    """
    if league not in ("cfb", "nfl"):
        raise HTTPException(status_code=404, detail="league must be 'cfb' or 'nfl'")
    try:
        return await football_table(league, refresh=refresh)
    except Exception as e:
        logger.error(f"Football table failed for {league}: {e}")
        raise HTTPException(status_code=502, detail=f"Could not build the {league} table: {e}")

"""MLB postseason team table: every stat column for the teams still alive."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.backend.sports.mlb_teams import team_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mlb", tags=["MLB"])


@router.get("/teams")
async def get_playoff_teams(refresh: bool = False) -> Dict[str, Any]:
    """
    One row per team still in the postseason: record and recent form, record against good and
    bad teams, offense, pitching and defense (season and September, each with its rank among
    all 30 teams), and the next game with the starters' ERAs. Cached for 30 minutes.
    """
    try:
        return await team_table(refresh=refresh)
    except Exception as e:
        logger.error(f"MLB team table failed: {e}")
        raise HTTPException(status_code=502, detail=f"Could not build the team table: {e}")

"""Program tiers: the trader's own 1 to 5 rating of each team's program."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.program_tiers import load_tiers, save_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tiers", tags=["Program tiers"])


class TierIn(BaseModel):
    tier: Optional[int] = None  # 1 to 5, or null to clear
    note: Optional[str] = None


@router.get("/{league}")
async def get_tiers(league: str) -> Dict[str, Any]:
    """Every saved tier for a league, keyed by team id."""
    return {"league": league, "tiers": await load_tiers(league)}


@router.put("/{league}/{team_id}")
async def put_tier(league: str, team_id: str, body: TierIn) -> Dict[str, Any]:
    """Set or clear one team's program tier."""
    try:
        return await save_tier(league, team_id, body.tier, body.note)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Saving program tier failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save the tier")

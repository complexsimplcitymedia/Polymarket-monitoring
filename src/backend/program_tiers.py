"""Reading and writing the trader's program tiers (stored in the app's own database)."""

import logging
from typing import Any, Optional

from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import ProgramTier

logger = logging.getLogger(__name__)

LEAGUES = {"mlb", "cfb", "nfl", "nba", "cbb"}
MIN_TIER, MAX_TIER = 1, 5


def tier_key(league: str, team_id: str) -> str:
    return f"{league}:{team_id}"


def validate(league: str, tier: Optional[int]) -> None:
    if league not in LEAGUES:
        raise ValueError(f"league must be one of {sorted(LEAGUES)}")
    if tier is not None and not (MIN_TIER <= tier <= MAX_TIER):
        raise ValueError(f"tier must be {MIN_TIER} to {MAX_TIER}, or empty to clear it")


async def load_tiers(league: str) -> dict[str, dict[str, Any]]:
    """Saved tiers for one league, keyed by team id. An unreachable database means none."""
    prefix = f"{league}:"
    try:
        async with async_session_factory() as session:
            rows = (await session.execute(select(ProgramTier).where(ProgramTier.key.like(f"{prefix}%")))).scalars().all()
    except Exception as e:
        logger.warning(f"Could not load program tiers: {e}")
        return {}
    return {r.key[len(prefix):]: {"tier": r.tier, "note": r.note} for r in rows}


async def save_tier(league: str, team_id: str, tier: Optional[int], note: Optional[str] = None) -> dict[str, Any]:
    """Set (or clear, with tier=None) a team's tier. The note is only changed when given."""
    validate(league, tier)
    async with async_session_factory() as session:
        key = tier_key(league, team_id)
        row = await session.get(ProgramTier, key)
        if row is None:
            row = ProgramTier(key=key)
            session.add(row)
        row.tier = tier
        if note is not None:
            row.note = note
        await session.commit()
        return {"team_id": team_id, "tier": row.tier, "note": row.note}

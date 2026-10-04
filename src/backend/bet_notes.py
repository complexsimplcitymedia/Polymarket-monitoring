"""Reading and writing the trader's tags and notes on bets (stored in the app's own database)."""

import logging
from typing import Any, Optional

from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import BetNote

logger = logging.getLogger(__name__)

TAGS = {"analysis", "vibe", "hedge"}
WHY_ENDED = {"bounce", "target", "cut", "held"}


async def load_notes() -> dict[str, dict[str, Any]]:
    """Every saved note keyed by bet_key. An unreachable database means no notes, not an error."""
    try:
        async with async_session_factory() as session:
            rows = (await session.execute(select(BetNote))).scalars().all()
    except Exception as e:  # the account page must still work without the notes table
        logger.warning(f"Could not load bet notes: {e}")
        return {}
    return {r.bet_key: {"tag": r.tag, "note": r.note, "why_ended": r.why_ended} for r in rows}


def merge_notes(bets: list[dict[str, Any]], notes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Copies of the bets with tag, note and why_ended filled in. Untagged bets count as analysis."""
    merged = []
    for b in bets:
        n = notes.get(b["bet_key"]) or {}
        merged.append({**b, "tag": n.get("tag") or "analysis", "note": n.get("note"), "why_ended": n.get("why_ended")})
    return merged


async def save_note(
    bet_key: str, tag: Optional[str] = None, note: Optional[str] = None, why_ended: Optional[str] = None,
    clear_why: bool = False,
) -> dict[str, Any]:
    """Create or update the note for a bet. Only the fields given are changed."""
    if tag is not None and tag not in TAGS:
        raise ValueError(f"tag must be one of {sorted(TAGS)}")
    if why_ended is not None and why_ended not in WHY_ENDED:
        raise ValueError(f"why_ended must be one of {sorted(WHY_ENDED)}")
    async with async_session_factory() as session:
        row = await session.get(BetNote, bet_key)
        if row is None:
            row = BetNote(bet_key=bet_key, tag=tag or "analysis")
            session.add(row)
        if tag is not None:
            row.tag = tag
        if note is not None:
            row.note = note
        if why_ended is not None:
            row.why_ended = why_ended
        elif clear_why:
            row.why_ended = None
        await session.commit()
        return {"bet_key": row.bet_key, "tag": row.tag, "note": row.note, "why_ended": row.why_ended}

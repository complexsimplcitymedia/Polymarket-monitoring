"""Account page endpoint: balances, bonus hold, open positions, cash flows, trading results."""

import logging
from typing import Any, Dict

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.account import AccountNotConfigured, account_service
from src.backend.bet_notes import load_notes, merge_notes, save_note
from src.backend.sports.live_scores import attach_live_scores
from src.backend.sports.trader import summarize_bets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account", tags=["Account"])


@router.get("/summary")
async def get_account_summary(refresh: bool = False) -> Dict[str, Any]:
    """
    Read-only snapshot of the Polymarket US account. Cached for a minute; pass
    ``refresh=true`` to force a fresh pull.
    """
    try:
        data = await account_service.summary(refresh=refresh)
        # Live scores are attached on every request (the summary itself is cached for a minute)
        try:
            items = await attach_live_scores(data["open_positions"]["items"])
        except Exception as e:  # scores are a nicety; the account must still load without them
            logger.warning(f"Live scores unavailable: {e}")
            items = data["open_positions"]["items"]
        return {**data, "open_positions": {**data["open_positions"], "items": items}}
    except AccountNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Account summary failed: {e}")
        raise HTTPException(status_code=502, detail=f"Could not read the account: {e}")


class BetNoteIn(BaseModel):
    bet_key: str
    tag: Optional[str] = None  # "analysis" or "vibe"
    note: Optional[str] = None
    why_ended: Optional[str] = None  # "bounce", "target", "cut" or "held"
    clear_why: bool = False


@router.get("/bets")
async def get_account_bets(refresh: bool = False) -> Dict[str, Any]:
    """
    Every bet as one row (team backed, price paid, stake, how it ended, result), newest first,
    with the trader's tag and note on each, and totals per sport, bet type and tag. Facts only.
    """
    try:
        data = await account_service.bets(refresh=refresh)
    except AccountNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Account bets failed: {e}")
        raise HTTPException(status_code=502, detail=f"Could not read the account: {e}")
    bets = merge_notes(data["bets"], await load_notes())
    return {**data, "bets": bets, "by_tag": summarize_bets(bets, "tag")}


@router.put("/bets/note")
async def put_bet_note(body: BetNoteIn) -> Dict[str, Any]:
    """Tag a bet as analysis or vibe and attach a note or why it ended. Only given fields change."""
    try:
        return await save_note(body.bet_key, body.tag, body.note, body.why_ended, body.clear_why)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Saving bet note failed: {e}")
        raise HTTPException(status_code=500, detail="Could not save the note")

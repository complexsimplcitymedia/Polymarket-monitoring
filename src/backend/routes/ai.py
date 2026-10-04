"""The in-app AI: ask a question about the live games and get an answer from the stored data."""
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.backend import ai
from src.backend.config import settings
from src.backend.database import async_session_factory
from src.backend.models import GameSnapshot

router = APIRouter(prefix="/api/ai", tags=["AI"])


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    game_id: Optional[str] = None
    league: Optional[str] = None
    model: str = Field(min_length=1, max_length=200)  # any model id from NanoGPT


@router.get("/status")
async def status() -> Dict[str, Any]:
    return {"configured": bool(settings.NANOGPT_API_KEY)}


@router.get("/models")
async def models() -> List[str]:
    try:
        return await ai.list_models()
    except ai.AiNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not load the model list from NanoGPT")


@router.get("/games")
async def games() -> List[Dict[str, Any]]:
    """Games with a reading in the last 20 minutes, for the game picker."""
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(minutes=20)
    async with async_session_factory() as session:
        latest = select(func.max(GameSnapshot.id)).where(GameSnapshot.created_at > since).group_by(GameSnapshot.league, GameSnapshot.game_id)
        rows = (await session.execute(select(GameSnapshot).where(GameSnapshot.id.in_(latest)).order_by(GameSnapshot.id.desc()))).scalars().all()
    return [{"league": r.league, "game_id": r.game_id, "title": f"{r.away_team} {r.away_score} @ {r.home_team} {r.home_score}", "detail": r.detail} for r in rows]


@router.post("/ask")
async def ask(body: AskBody) -> Dict[str, Any]:
    context = await ai.gather_context(body.game_id, body.league)
    try:
        result = await ai.ask(body.question, context, body.model)
    except ai.AiNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ai.EmptyAnswer as e:
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"NanoGPT answered {e.response.status_code}")
    except httpx.HTTPError:
        raise HTTPException(status_code=504, detail="NanoGPT did not answer in time")
    return {**result, "context_chars": len(context)}

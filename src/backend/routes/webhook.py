"""Webhook receiver for Open WebUI events — the persistent tunnel.

Open WebUI posts every chat event here. The backend stores them so the
AI and alert systems know what the user is looking at in real time.
"""
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from src.backend.database import Base, async_session_factory

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


class WebUIEvent(Base):
    __tablename__ = "webui_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), index=True)
    user_id = Column(String(200))
    chat_id = Column(String(200), index=True)
    model = Column(String(200))
    content = Column(Text)
    raw = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), index=True)


@router.post("/openwebui")
async def openwebui_event(request: Request) -> Dict[str, Any]:
    """Receive all events from Open WebUI."""
    body = await request.json()

    event_type = body.get("type") or body.get("event") or "unknown"
    user = body.get("user") or {}
    chat = body.get("chat") or body.get("data") or {}

    async with async_session_factory() as session:
        session.add(WebUIEvent(
            event_type=str(event_type),
            user_id=str(user.get("id") or user.get("email") or ""),
            chat_id=str(chat.get("id") or ""),
            model=str(chat.get("model") or body.get("model") or ""),
            content=str(chat.get("content") or chat.get("message") or body.get("message") or "")[:4000],
            raw=str(body)[:8000],
        ))
        await session.commit()

    return {"status": "ok", "received": event_type}


@router.get("/openwebui/recent")
async def recent_events(limit: int = 20) -> list:
    """Last N events from Open WebUI."""
    async with async_session_factory() as session:
        rows = (await session.execute(
            WebUIEvent.__table__.select()
            .order_by(WebUIEvent.id.desc())
            .limit(limit)
        )).fetchall()
    return [dict(r._mapping) for r in rows]

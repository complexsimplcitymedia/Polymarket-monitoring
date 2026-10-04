"""Alerts feed and email setup check."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from sqlalchemy import select

from src.backend.config import settings
from src.backend.database import async_session_factory
from src.backend.models import Alert
from src.backend.notify import email_configured, send_email
from src.backend.sports.alerts import standing
from src.backend.sports.live_scores import fetch_scoreboards

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("")
async def list_alerts(limit: int = 50) -> Dict[str, Any]:
    """Recent alerts, newest first, plus whether email delivery is set up (no secrets returned)."""
    async with async_session_factory() as session:
        rows = (await session.execute(select(Alert).order_by(Alert.created_at.desc()).limit(min(limit, 200)))).scalars().all()
    try:
        boards = await fetch_scoreboards()
    except Exception:  # without scores the alerts still list, just without a current line
        boards = []

    def current(a: Alert) -> Optional[Dict[str, Any]]:
        """Where the game stands now, and whether the alerted team is still ahead by enough."""
        st = standing(a.title, a.team, boards)
        if not st:
            return None
        g = st["game"]
        return {"away": g["away"]["name"], "home": g["home"]["name"], "away_score": g["away"]["score"],
                "home_score": g["home"]["score"], "detail": g["detail"], "state": g["state"],
                "margin": st["margin"], "still_leading": (st["margin"] >= -settings.ALERT_TRAIL_MAX_DEFICIT) if (a.margin or 0) < 0
                else st["margin"] >= settings.ALERT_MIN_LEAD}

    return {
        "email_configured": email_configured(),
        "enabled": settings.ALERTS_ENABLED,
        "max_price": settings.ALERT_MAX_PRICE,
        "min_lead": settings.ALERT_MIN_LEAD,
        "cooldown_minutes": settings.ALERT_COOLDOWN_MINUTES,
        "alerts": [
            {"id": a.id, "kind": a.kind, "created_at": a.created_at.isoformat() + "Z", "priority": a.priority, "sport": a.sport,
             "team": a.team, "title": a.title, "espn_win_prob": a.espn_win_prob, "market_price": a.market_price,
             "gap": a.gap, "margin": a.margin, "detail": a.detail, "delivery": a.delivery, "now": current(a),
             "status": a.status, "retract_note": a.retract_note}
            for a in rows
        ],
    }


@router.post("/test-email")
async def test_email() -> Dict[str, Any]:
    """Send a test email to the configured address so delivery can be checked."""
    status = await send_email("[Test] Polymarket alerts", "If you can read this, alert emails are working.")
    return {"status": status, "email_configured": email_configured()}

"""
Read-only view of the trader's Polymarket US account.

Pulls balances, open positions and the activity feed with GET calls only, then builds
what the account page shows: balance and bonus fields, open positions, cash flows and
closed-cycle results. Nothing here places, changes or cancels an order.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from src.backend.config import settings
from src.backend.sports.trader import (
    build_bets,
    cash_summary,
    summarize_bets,
    summarize_results,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
MAX_ACTIVITY_PAGES = 100  # 100 events per page


class AccountNotConfigured(RuntimeError):
    """No Polymarket US API credentials are set."""


def _value(amount: Optional[dict]) -> float:
    if isinstance(amount, dict) and amount.get("value") not in (None, ""):
        return float(amount["value"])
    return 0.0


def _client() -> Any:
    from polymarket_us import PolymarketUS

    key_id = settings.POLYMARKET_KEY_ID or settings.POLYMARKET_API_KEY
    secret = settings.POLYMARKET_SECRET_KEY or settings.POLYMARKET_SECRET
    if not (key_id and secret):
        raise AccountNotConfigured("Polymarket US credentials are not configured")
    return PolymarketUS(key_id=key_id, secret_key=secret)


def _fetch_raw() -> dict[str, Any]:
    """Blocking SDK calls; run in a thread."""
    client = _client()
    activities: list[dict] = []
    cursor = None
    for _ in range(MAX_ACTIVITY_PAGES):
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = client.portfolio.activities(params)
        batch = page.get("activities", [])
        activities += batch
        cursor = page.get("nextCursor")
        if page.get("eof") or not cursor or not batch:
            break
    return {
        "activities": activities,
        "positions": client.portfolio.positions(),
        "balances": client.account.balances(),
    }


def build_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Turn raw API payloads into the account page's data. Pure, so it is testable."""
    bal = (raw["balances"].get("balances") or [{}])[0]
    balance = float(bal.get("currentBalance") or 0.0)
    hold = float(bal.get("bonusHold") or 0.0)

    positions_raw = raw["positions"].get("positions") or {}
    items = positions_raw.items() if isinstance(positions_raw, dict) else enumerate(positions_raw)
    open_positions = []
    for key, p in items:
        meta = p.get("marketMetadata") or {}
        legs = p.get("comboLegDetails") or []
        open_positions.append({
            "slug": p.get("marketSlug") or meta.get("slug") or str(key),
            "title": meta.get("title") or "",
            "outcome": meta.get("outcome") or "",
            "contracts": float(p.get("netPositionDecimal") or p.get("netPosition") or 0),
            "avg_price": _value(p.get("avgPx")),
            "cost": _value(p.get("cost")),
            "value": _value(p.get("cashValue")),
            "legs": [
                {"title": leg.get("title", ""), "outcome": leg.get("outcome", ""), "slug": leg.get("slug", ""),
                 "start": leg.get("eventStartTime"),
                 "state": str(leg.get("state", "")).replace("COMBO_LEG_STATE_", "")}
                for leg in legs
            ],
        })
    open_value = sum(p["value"] for p in open_positions)

    activities = raw["activities"]
    cash = cash_summary(activities, balance=balance, open_positions_value=open_value)
    bets = build_bets(activities)
    fills = [a for a in activities if a["type"] == "ACTIVITY_TYPE_TRADE"]
    fees = sum(
        _value(a["trade"]["aggressorExecution"].get("commissionNotionalCollected"))
        for a in fills
    )
    return {
        "balance": {
            "current": balance,
            "buying_power": float(bal.get("buyingPower") or 0.0),
            "cash": float(bal.get("displayedCash") or 0.0),
            "bonus": float(bal.get("displayedBonus") or 0.0),
            "bonus_hold": hold,
            "available_to_withdraw": float(bal.get("availableToWithdraw") or 0.0),
            "pending_withdrawals": bal.get("pendingWithdrawals") or [],
            # Trader's working model: only the balance above the bonus hold can be withdrawn
            "model_withdrawable": max(balance - hold, 0.0),
        },
        "open_positions": {
            "count": len(open_positions),
            "cost": sum(p["cost"] for p in open_positions),
            "value": open_value,
            "items": open_positions,
        },
        "cash_flows": cash,
        "trading": {
            **summarize_results(bets),
            "total_fills": len(fills),
            "fees_paid": fees,
        },
    }


def build_bets_view(raw: dict[str, Any]) -> dict[str, Any]:
    """Every bet as one row, plus totals per sport and per bet type."""
    bets = build_bets(raw["activities"])
    return {
        "count": len(bets),
        "bets": bets,
        "by_league": summarize_bets(bets, "league"),
        "by_kind": summarize_bets(bets, "kind"),
    }


class AccountService:
    def __init__(self) -> None:
        self._cache: Optional[tuple[float, dict[str, Any]]] = None
        self._lock = asyncio.Lock()

    async def _raw(self, refresh: bool) -> dict[str, Any]:
        """Raw API payloads, cached so the summary and the bets view share one pull."""
        now = time.monotonic()
        if not refresh and self._cache and now - self._cache[0] < CACHE_TTL_SECONDS:
            return self._cache[1]
        raw = await asyncio.to_thread(_fetch_raw)
        raw["fetched_at"] = time.time()
        self._cache = (now, raw)
        return raw

    async def summary(self, refresh: bool = False) -> dict[str, Any]:
        async with self._lock:
            raw = await self._raw(refresh)
            result = build_summary(raw)
            result["fetched_at"] = raw["fetched_at"]
            return result

    async def bets(self, refresh: bool = False) -> dict[str, Any]:
        async with self._lock:
            raw = await self._raw(refresh)
            result = build_bets_view(raw)
            result["fetched_at"] = raw["fetched_at"]
            return result


account_service = AccountService()

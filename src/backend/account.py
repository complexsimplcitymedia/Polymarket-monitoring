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


def _client(slot: int = 0) -> Any:
    from polymarket_us import PolymarketUS

    pool = settings.get_polymarket_key_pool()
    if not pool:
        raise AccountNotConfigured("Polymarket US credentials are not configured")
    key_id, secret = pool[slot % len(pool)]
    return PolymarketUS(key_id=key_id, secret_key=secret)


def _fetch_raw(key_slot: int = 0) -> dict[str, Any]:
    """Blocking SDK calls with 429 backoff and key-slot failover across the pool."""
    pool = settings.get_polymarket_key_pool()
    max_attempts = len(pool) if pool else 1

    last_error = None
    for attempt in range(max_attempts):
        slot = (key_slot + attempt) % max_attempts
        try:
            client = _client(slot)
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
        except Exception as e:
            last_error = e
            err_msg = str(e).lower()
            if "429" in err_msg or "rate limit" in err_msg or "too many" in err_msg:
                logger.warning(f"Key slot {slot} rate limited (429): {e}. Rotating to next slot with backoff...")
                time.sleep(1.0)
                continue
            else:
                logger.warning(f"Error fetching account raw data with slot {slot}: {e}. Retrying with next slot...")
                continue
    if last_error:
        raise last_error
    raise RuntimeError("Failed to fetch raw account data")


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
        self._ws_task: Optional[asyncio.Task] = None

    def start_stream(self) -> None:
        """Launch background WebSocket stream to hold private stream open."""
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._stream_worker())

    async def _stream_worker(self) -> None:
        """Hold private WebSocket stream open to keep balance and position state live."""
        import json
        import base64
        import websockets
        from nacl.signing import SigningKey

        backoff = 1.0
        while True:
            pool = settings.get_polymarket_key_pool()
            if not pool:
                await asyncio.sleep(10.0)
                continue

            # Key slot 0 is dedicated to the private account WebSocket
            key_id, secret_key = pool[0]
            path = "/v1/ws/private"
            url = f"wss://api.polymarket.us{path}"

            try:
                timestamp = str(int(time.time() * 1000))
                message = f"{timestamp}GET{path}"
                secret_key_bytes = base64.b64decode(secret_key)[:32]
                sig = base64.b64encode(SigningKey(secret_key_bytes).sign(message.encode()).signature).decode()

                headers = [
                    ("X-PM-Access-Key", key_id),
                    ("X-PM-Timestamp", timestamp),
                    ("X-PM-Signature", sig),
                ]

                async with websockets.connect(url, additional_headers=headers) as ws:
                    logger.info("Private WebSocket connected for real-time account stream")
                    backoff = 1.0

                    # Subscribe to balances, positions, orders
                    for sub_type in [
                        "SUBSCRIPTION_TYPE_ACCOUNT_BALANCE",
                        "SUBSCRIPTION_TYPE_POSITION",
                        "SUBSCRIPTION_TYPE_ORDER",
                    ]:
                        await ws.send(json.dumps({
                            "subscribe": {
                                "requestId": f"sub-{sub_type}",
                                "subscriptionType": sub_type,
                            }
                        }))

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            # Reactive update of cached balance or position in memory
                            if any(k in msg for k in ["accountBalanceSubscriptionSnapshot", "accountBalancesSnapshot", "accountBalancesUpdate", "accountBalanceSubscriptionUpdate", "accountBalanceUpdate"]):
                                bal_payload = (
                                    msg.get("accountBalanceSubscriptionSnapshot")
                                    or msg.get("accountBalancesSnapshot")
                                    or msg.get("accountBalancesUpdate")
                                    or msg.get("accountBalanceSubscriptionUpdate")
                                    or msg.get("accountBalanceUpdate")
                                )
                                if bal_payload:
                                    bal_list = bal_payload if isinstance(bal_payload, list) else [bal_payload]
                                    async with self._lock:
                                        if self._cache:
                                            self._cache[1]["balances"] = {"balances": bal_list}
                                            self._cache = (time.monotonic(), self._cache[1])
                            elif any(k in msg for k in ["positionSubscriptionSnapshot", "positionsSnapshot", "positionSubscriptionUpdate", "positionUpdate"]):
                                pos_payload = (
                                    msg.get("positionSubscriptionSnapshot")
                                    or msg.get("positionsSnapshot")
                                    or msg.get("positionSubscriptionUpdate")
                                    or msg.get("positionUpdate")
                                )
                                if pos_payload:
                                    pos_list = pos_payload if isinstance(pos_payload, list) else [pos_payload]
                                    async with self._lock:
                                        if self._cache:
                                            self._cache[1]["positions"] = {"positions": pos_list}
                                            self._cache = (time.monotonic(), self._cache[1])
                        except Exception as parse_err:
                            logger.debug(f"Stream parse notice: {parse_err}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Private stream reconnecting in {backoff:.1f}s: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def _raw(self, refresh: bool) -> dict[str, Any]:
        """Raw API payloads, cached and kept fresh by the live private WebSocket stream."""
        self.start_stream()
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

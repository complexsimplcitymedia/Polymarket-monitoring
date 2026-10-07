"""
Polymarket Data API v2 helper.

Provides a thin wrapper around https://data-api.polymarket.com/v2 so the rest
of the backend can keep working with camelCase field names and bare lists.

Migration notes from Polymarket docs:
- Base URL: https://data-api.polymarket.com/v2
- Responses wrap in { data: [...], pagination: {...} }
- Field names are snake_case; we normalize back to camelCase for callers.
- market parameter -> condition (aliases accepted on v2, but we use condition).
- Pagination is cursor based: pagination.next_cursor is null when done.
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DATA_API_V2_BASE = "https://data-api.polymarket.com/v2"

# v2 snake_case -> v1 camelCase aliases we keep using internally.
_SNAKE_TO_CAMEL = {
    "proxy_wallet": "proxyWallet",
    "condition_id": "conditionId",
    "outcome_index": "outcomeIndex",
    "profile_image": "profileImage",
    "market_slug": "marketSlug",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
    "total_value": "totalValue",
    "trade_value": "tradeValue",
    "usd_value": "usdValue",
    "size_matched": "sizeMatched",
    "last_trade_price": "lastTradePrice",
    "last_trade_size": "lastTradeSize",
    "volume_24h": "volume24h",
    "volume_7d": "volume7d",
    "reward_daily_rate": "rewardDailyRate",
    "event_id": "eventId",
    "event_ticker": "eventTicker",
    "event_slug": "eventSlug",
    "market_id": "marketId",
    "token_id": "tokenId",
    "maker_amount": "makerAmount",
    "taker_amount": "takerAmount",
    "fee_rate_bps": "feeRateBps",
    "expiration": "expiration",
    "signature_type": "signatureType",
}


def _normalize_keys(obj: Any) -> Any:
    """Recursively convert snake_case keys to camelCase aliases."""
    if isinstance(obj, dict):
        normalized: dict[str, Any] = {}
        for k, v in obj.items():
            new_key = _SNAKE_TO_CAMEL.get(k, k)
            normalized[new_key] = _normalize_keys(v)
        return normalized
    if isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    return obj


def _extract_data(response_json: Any) -> list[dict]:
    """Pull data list from v2 envelope, falling back to bare list/object."""
    if isinstance(response_json, dict):
        data = response_json.get("data")
        if isinstance(data, list):
            return data
        # Fallback: bare dict with a known array key
        for key in ("positions", "results", "items", "trades", "holders"):
            if isinstance(response_json.get(key), list):
                return response_json[key]
        return []
    if isinstance(response_json, list):
        return response_json
    return []


def _extract_next_cursor(response_json: Any) -> Optional[str]:
    """Read cursor from v2 pagination object."""
    if not isinstance(response_json, dict):
        return None
    pagination = response_json.get("pagination")
    if isinstance(pagination, dict):
        cursor = pagination.get("next_cursor")
        if cursor:
            return str(cursor)
    return None


async def get_v2(
    endpoint: str,
    params: Optional[dict[str, Any]] = None,
    timeout: float = 15.0,
    follow_cursors: bool = False,
    max_pages: int = 10,
) -> list[dict]:
    """
    Call a Data API v2 endpoint and return a normalized list of results.

    Args:
        endpoint: route under /v2, e.g. "trades", "positions", "holders".
        params: query params. 'market' is automatically renamed to 'condition'.
        timeout: request timeout.
        follow_cursors: if True, keep fetching until next_cursor is null.
        max_pages: safety cap for cursor pagination.
    """
    url = f"{DATA_API_V2_BASE}/{endpoint.lstrip('/')}"
    query = dict(params or {})
    if "market" in query:
        query["condition"] = query.pop("market")

    results: list[dict] = []
    cursor: Optional[str] = None
    page = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            if cursor:
                query["cursor"] = cursor
            try:
                response = await client.get(url, params=query)
                if response.status_code != 200:
                    logger.warning(
                        f"Data API v2 {endpoint} returned {response.status_code}: {response.text[:200]}"
                    )
                    break
                payload = response.json()
                page_results = _extract_data(payload)
                if page_results:
                    results.extend(_normalize_keys(page_results))
                cursor = _extract_next_cursor(payload)
                page += 1
                if not follow_cursors or not cursor or page >= max_pages:
                    break
            except Exception as e:
                logger.error(f"Data API v2 {endpoint} error: {e}")
                break

    return results


async def post_v2(
    endpoint: str,
    json_payload: Optional[dict[str, Any]] = None,
    timeout: float = 15.0,
) -> Any:
    """POST to a Data API v2 endpoint and return normalized data."""
    url = f"{DATA_API_V2_BASE}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, json=json_payload)
            if response.status_code != 200:
                logger.warning(
                    f"Data API v2 POST {endpoint} returned {response.status_code}: {response.text[:200]}"
                )
                return None
            payload = response.json()
            return _normalize_keys(_extract_data(payload))
        except Exception as e:
            logger.error(f"Data API v2 POST {endpoint} error: {e}")
            return None


# Convenience wrappers for the routes we currently use.
async def fetch_trades(condition: str, limit: int = 2000) -> list[dict]:
    return await get_v2("trades", params={"condition": condition, "limit": min(limit, 500)}, follow_cursors=True)


async def fetch_holders(condition: str) -> list[dict]:
    """Return a flat list of holders across all outcome tokens for a condition."""
    rows = await get_v2("holders", params={"condition": condition})
    flat: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        token_id = row.get("tokenId") or row.get("token_id")
        outcome_index = row.get("outcomeIndex") if row.get("outcomeIndex") is not None else row.get("outcome_index")
        for h in row.get("holders", []):
            if not isinstance(h, dict):
                continue
            enriched = dict(h)
            if token_id and "tokenId" not in enriched and "token_id" not in enriched:
                enriched["tokenId"] = token_id
            if outcome_index is not None and "outcomeIndex" not in enriched and "outcome_index" not in enriched:
                enriched["outcomeIndex"] = outcome_index
            flat.append(enriched)
    return flat


async def fetch_positions(user: str, limit: int = 500, status: Optional[str] = None) -> list[dict]:
    params: dict[str, Any] = {"user": user, "limit": min(limit, 500)}
    if status:
        params["status"] = status
    return await get_v2("positions", params=params, follow_cursors=True)


async def fetch_value(user: str) -> list[dict]:
    return await get_v2("value", params={"user": user})

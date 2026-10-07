"""Status feed proxy for external exchange and partner status pages."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])

# Polymarket US statuspage API
POLYMARKET_STATUS_URL = "https://status.polymarketexchange.com/api/v2/summary.json"
STATUS_TIMEOUT = 10.0


@router.get("/polymarket")
async def polymarket_status() -> dict[str, Any]:
    """Proxy Polymarket's statuspage summary so the UI can show exchange health."""
    try:
        async with httpx.AsyncClient(timeout=STATUS_TIMEOUT) as client:
            resp = await client.get(POLYMARKET_STATUS_URL)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"Polymarket statuspage returned {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="Statuspage error") from e
    except httpx.RequestError as e:
        logger.warning(f"Could not reach Polymarket statuspage: {e}")
        raise HTTPException(status_code=503, detail="Statuspage unreachable") from e

    status = data.get("status", {})
    components = data.get("components", [])
    incidents = data.get("incidents", [])
    scheduled = data.get("scheduled_maintenances", [])

    return {
        "overall": status.get("description", "Unknown"),
        "indicator": status.get("indicator", "unknown"),
        "updated_at": data.get("page", {}).get("updated_at"),
        "components": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "status": c.get("status"),
                "group": c.get("group"),
                "updated_at": c.get("updated_at"),
            }
            for c in components
            if not c.get("group") and c.get("status") != "operational"
        ],
        "incidents": [
            {
                "id": i.get("id"),
                "name": i.get("name"),
                "status": i.get("status"),
                "impact": i.get("impact"),
                "updated_at": i.get("updated_at"),
            }
            for i in incidents[:5]
        ],
        "scheduled_maintenances": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "status": s.get("status"),
                "scheduled_for": s.get("scheduled_for"),
                "scheduled_until": s.get("scheduled_until"),
            }
            for s in scheduled[:3]
        ],
    }


@router.get("/polymarket/raw")
async def polymarket_status_raw() -> dict[str, Any]:
    """Raw statuspage summary passthrough."""
    try:
        async with httpx.AsyncClient(timeout=STATUS_TIMEOUT) as client:
            resp = await client.get(POLYMARKET_STATUS_URL)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        logger.warning(f"Could not reach Polymarket statuspage: {e}")
        raise HTTPException(status_code=503, detail="Statuspage unreachable") from e

"""
FastAPI Router for Polymarket CLOB Direct Trading.

Enables programmatic order execution, balance inspection, order book scanning,
and multi-leg parlay execution bypassing the web UI.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.backend.config import settings
from src.backend.extras.trading import trading_service

router = APIRouter(prefix="/api/trading", tags=["Trading"])


class OrderRequest(BaseModel):
    token_id: str = Field(..., description="Asset token ID for YES or NO outcome")
    price: float = Field(..., ge=0.001, le=0.999, description="Price per share (0.001 - 0.999)")
    size: float = Field(..., gt=0, description="Number of outcome shares")
    side: str = Field(default="BUY", description="BUY or SELL")
    order_type: str = Field(default="GTC", description="GTC, FOK, FAK, GTD")
    dry_run: bool = Field(default=False, description="If true, simulate without submitting to chain")


class ParlayLegRequest(BaseModel):
    token_id: str = Field(..., description="Asset token ID")
    price: float = Field(..., ge=0.001, le=0.999, description="Target limit price")
    side: str = Field(default="BUY", description="BUY or SELL")
    market_title: Optional[str] = Field(default=None, description="Market title for logging")


class ParlayOrderRequest(BaseModel):
    legs: List[ParlayLegRequest] = Field(..., min_length=2, description="List of parlay legs")
    total_budget: float = Field(..., gt=0, description="Total budget in USDC")
    dry_run: bool = Field(default=False, description="If true, simulate without submitting to chain")


@router.get("/status")
async def get_trading_status() -> Dict[str, Any]:
    """
    Check the connection status of the Polymarket CLOB trading pipeline,
    wallet address, and available USDC collateral balance.
    """
    return await trading_service.get_trading_status()


@router.get("/orderbook/{token_id}")
async def get_order_book(token_id: str) -> Dict[str, Any]:
    """
    Get live order book (bids, asks, spread, midpoint) directly from Polymarket CLOB.
    """
    return await trading_service.get_order_book(token_id)


@router.post("/order")
async def place_order(req: OrderRequest) -> Dict[str, Any]:
    """
    Submit a limit order directly to the Polymarket CLOB.
    """
    try:
        res = await trading_service.place_order(
            token_id=req.token_id,
            price=req.price,
            size=req.size,
            side=req.side,
            order_type=req.order_type,
            dry_run=req.dry_run,
        )
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error", "Order failed"))
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trading pipeline error: {str(e)}")


@router.post("/parlay")
async def place_parlay(req: ParlayOrderRequest) -> Dict[str, Any]:
    """
    Execute a multi-leg parlay bundle sequentially across Polymarket order books.
    """
    try:
        legs_data = [leg.model_dump() for leg in req.legs]
        return await trading_service.place_parlay_bundle(
            legs=legs_data,
            total_budget=req.total_budget,
            dry_run=req.dry_run,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parlay execution failed: {str(e)}")


@router.get("/orders")
async def get_open_orders(market_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """
    Get all active/open orders on the CLOB for the connected wallet.
    """
    return await trading_service.get_open_orders(market_id)


@router.delete("/order/{order_id}")
async def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    Cancel an open order on the CLOB.
    """
    try:
        return await trading_service.cancel_order(order_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/orders")
async def cancel_all_orders() -> Dict[str, Any]:
    """
    Cancel all open orders on the CLOB.
    """
    try:
        return await trading_service.cancel_all_orders()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/execute-opportunity/{opportunity_id}")
async def execute_opportunity(
    opportunity_id: int,
    budget_usdc: float = Query(5.0, gt=0, description="Amount in USDC to allocate to this trade"),
    dry_run: bool = Query(False, description="If true, simulate without submitting to chain")
) -> Dict[str, Any]:
    """
    1-Click execution of any detected opportunity stored in the database.
    """
    import json
    from sqlalchemy import select
    from src.backend.database import async_session_factory
    from src.backend.models import Opportunity

    async with async_session_factory() as session:
        op = await session.get(Opportunity, opportunity_id)
        if not op:
            raise HTTPException(status_code=404, detail="Opportunity not found")

        # Handle Parlay bundle
        if op.category == "PARLAY":
            details = json.loads(op.details_json or "{}")
            legs = details.get("legs", [])
            if not legs:
                raise HTTPException(status_code=400, detail="Parlay legs missing")

            res = await trading_service.place_parlay_bundle(
                legs=legs,
                total_budget=budget_usdc,
                dry_run=dry_run,
            )
            if res.get("success"):
                op.status = "EXECUTED"
                await session.commit()
            return res

        # Handle Single Market (Weather / Deterministic)
        if not op.target_token_id:
            # If benchmark, simulate or reject
            if not dry_run:
                raise HTTPException(status_code=400, detail="Target token ID not available on benchmark market")
            target_token = "simulated_token_" + str(opportunity_id)
        else:
            target_token = op.target_token_id

        price = op.target_limit_price or 0.50
        size = round(budget_usdc / price, 2) if price > 0 else 1.0

        res = await trading_service.place_order(
            token_id=target_token,
            price=price,
            size=size,
            side=op.target_side or "BUY",
            dry_run=dry_run,
        )

        if res.get("success"):
            op.status = "EXECUTED"
            await session.commit()

        return {
            "opportunity_id": opportunity_id,
            "title": op.title,
            "budget_usdc": budget_usdc,
            "execution": res,
        }



@router.get("/autotrade")
async def get_autotrade_status() -> Dict[str, Any]:
    """
    Inspect current autonomous execution settings and limits.
    """
    return {
        "enabled": settings.AUTO_TRADE_ENABLED,
        "max_bet_usdc": settings.AUTO_TRADE_MAX_BET,
        "min_ev_pct": settings.AUTO_TRADE_MIN_EV,
        "dry_run": settings.AUTO_TRADE_DRY_RUN,
    }


@router.post("/autotrade/toggle")
async def toggle_autotrade(
    enabled: Optional[bool] = None,
    dry_run: Optional[bool] = None,
    max_bet: Optional[float] = None,
    min_ev: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Dynamically update autonomous trading parameters.
    """
    if enabled is not None:
        settings.AUTO_TRADE_ENABLED = enabled
    if dry_run is not None:
        settings.AUTO_TRADE_DRY_RUN = dry_run
    if max_bet is not None and max_bet > 0:
        settings.AUTO_TRADE_MAX_BET = max_bet
    if min_ev is not None and min_ev > 0:
        settings.AUTO_TRADE_MIN_EV = min_ev

    return {
        "status": "UPDATED",
        "enabled": settings.AUTO_TRADE_ENABLED,
        "max_bet_usdc": settings.AUTO_TRADE_MAX_BET,
        "min_ev_pct": settings.AUTO_TRADE_MIN_EV,
        "dry_run": settings.AUTO_TRADE_DRY_RUN,
    }

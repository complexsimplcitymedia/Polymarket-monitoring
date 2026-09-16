"""
FastAPI Router for Prediction Market Opportunity Scanners.

Includes:
- Weather & Temperature Mispricing Scanner (NOAA / Open-Meteo vs CLOB)
- Correlated Multi-Market Parlay Engine & Enterprise Agent Analysis
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.scanners.weather import scan_weather_markets
from src.backend.scanners.parlay import (
    discover_parlay_candidates,
    analyze_parlay_with_enterprise_agent,
)

router = APIRouter(prefix="/api/scanners", tags=["Scanners"])


class ParlayAnalysisRequest(BaseModel):
    parlay_id: Optional[str] = None
    category: Optional[str] = "Macro & Fed Policy"
    title: Optional[str] = "Custom Parlay"
    legs: List[Dict[str, Any]]
    combined_implied_prob: Optional[float] = 25.0
    payout_multiplier: Optional[str] = "4.0x"


@router.get("/weather")
async def get_weather_opportunities() -> List[Dict[str, Any]]:
    """
    Scan Polymarket weather & temperature markets, compare against
    real-time NOAA/HRRR meteorological forecasts, and calculate mathematical EV.
    """
    try:
        return await scan_weather_markets()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather scanner error: {str(e)}")


@router.get("/parlays")
async def get_parlay_opportunities() -> List[Dict[str, Any]]:
    """
    Discover correlated multi-market parlay opportunities across active markets.
    """
    try:
        return await discover_parlay_candidates()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parlay scanner error: {str(e)}")


@router.post("/parlays/analyze")
async def analyze_parlay(req: ParlayAnalysisRequest) -> Dict[str, Any]:
    """
    Run enterprise agent analysis on a correlated parlay combination to assess
    joint probability, causal correlation, and risk breakdown.
    """
    try:
        return await analyze_parlay_with_enterprise_agent(req.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parlay analysis failed: {str(e)}")


@router.get("/opportunities")
async def list_opportunities(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get the latest high-conviction detected trading opportunities from PostgreSQL.
    """
    from src.backend.tasks.opportunity_hunter import get_latest_opportunities
    return await get_latest_opportunities(limit=limit)


@router.post("/run")
async def trigger_scan() -> Dict[str, Any]:
    """
    Manually trigger an immediate scan across all weather and parlay models.
    """
    from src.backend.tasks.opportunity_hunter import run_opportunity_scan
    results = await run_opportunity_scan()
    return {"status": "SUCCESS", "detected_count": len(results), "opportunities": results}


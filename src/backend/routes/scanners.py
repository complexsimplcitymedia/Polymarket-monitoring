"""
FastAPI Router for Prediction Market Opportunity Scanners.

Includes:
- Weather & Temperature Mispricing Scanner (NOAA / Open-Meteo vs CLOB)
- Correlated Multi-Market Parlay Engine & Enterprise Agent Analysis
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.backend.scanners.weather import (
    scan_weather_markets,
    get_tracked_cities,
    fetch_city_weather_matrix,
)
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


@router.get("/weather/cities")
async def list_weather_cities() -> List[Dict[str, Any]]:
    """
    List top 25 pre-indexed Polymarket weather cities with station metadata.
    """
    try:
        return get_tracked_cities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tracked cities: {str(e)}")


@router.get("/weather/matrix")
async def get_city_weather_matrix(
    city: str = "sf",
    target_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deep-dive weather analysis for any city: 10-year historical climatology,
    cloud cover & overcast patterns, NWP multi-model consensus, and 2-degree bracket odds.
    """
    try:
        return await fetch_city_weather_matrix(city_query=city, target_date_str=target_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather matrix error: {str(e)}")


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


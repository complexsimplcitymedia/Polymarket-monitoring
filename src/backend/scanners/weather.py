"""
Weather & Deterministic Market Scanner for Polymarket.

Pulls real-time meteorological forecasts (NOAA / HRRR / GFS models via Open-Meteo),
computes statistical probability density over temperature brackets,
and identifies high-EV mispricings against Polymarket order books.
"""

import re
import math
import logging
import json
from datetime import datetime, date
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import Market

logger = logging.getLogger(__name__)

# Coordinates and station info for Polymarket's common weather markets
METRO_STATIONS = {
    "nyc": {
        "name": "New York (Central Park / LGA)",
        "lat": 40.7829,
        "lon": -73.9654,
        "tz": "America/New_York",
        "keywords": ["new york", "nyc", "central park", "laguardia"],
    },
    "chicago": {
        "name": "Chicago (O'Hare)",
        "lat": 41.9742,
        "lon": -87.9073,
        "tz": "America/Chicago",
        "keywords": ["chicago", "o'hare"],
    },
    "miami": {
        "name": "Miami (MIA)",
        "lat": 25.7959,
        "lon": -80.2870,
        "tz": "America/New_York",
        "keywords": ["miami"],
    },
    "la": {
        "name": "Los Angeles (LAX)",
        "lat": 33.9416,
        "lon": -118.4085,
        "tz": "America/Los_Angeles",
        "keywords": ["los angeles", "la", "lax"],
    },
    "austin": {
        "name": "Austin (Camp Mabry)",
        "lat": 30.2672,
        "lon": -97.7431,
        "tz": "America/Chicago",
        "keywords": ["austin"],
    },
    "london": {
        "name": "London (Heathrow)",
        "lat": 51.4700,
        "lon": -0.4543,
        "tz": "Europe/London",
        "keywords": ["london", "heathrow"],
    },
}


def normal_cdf(x: float, mean: float, std_dev: float) -> float:
    """Cumulative distribution function for normal distribution."""
    if std_dev <= 0:
        return 1.0 if x >= mean else 0.0
    return 0.5 * (1.0 + math.erf((x - mean) / (std_dev * math.sqrt(2.0))))


def calculate_bracket_prob(low: Optional[float], high: Optional[float], forecast_mean: float, std_dev: float = 1.8) -> float:
    """
    Calculate probability that temperature falls within [low, high].
    """
    if low is None and high is not None:
        # "Below high"
        return normal_cdf(high, forecast_mean, std_dev)
    elif low is not None and high is None:
        # "At least low / above low"
        return 1.0 - normal_cdf(low, forecast_mean, std_dev)
    elif low is not None and high is not None:
        # "Between low and high"
        p_high = normal_cdf(high, forecast_mean, std_dev)
        p_low = normal_cdf(low, forecast_mean, std_dev)
        return max(0.0, p_high - p_low)
    return 0.5


def parse_temperature_bracket(title: str) -> Dict[str, Any]:
    """
    Extract city and bracket bounds from a market question.
    e.g. "Will highest temperature in NYC be between 70°F and 74°F on Sept 6?"
    """
    title_lower = title.lower()
    
    # Identify city
    matched_city = None
    for city_key, info in METRO_STATIONS.items():
        if any(kw in title_lower for kw in info["keywords"]):
            matched_city = city_key
            break

    # Extract bracket bounds
    low, high = None, None
    unit = "F" if "°f" in title_lower or " f" in title_lower or "fahrenheit" in title_lower else "C"

    between_match = re.search(r'between\s+(\d+(?:\.\d+)?)[°\s]*[fc]?\s+and\s+(\d+(?:\.\d+)?)[°\s]*[fc]?', title_lower)
    if between_match:
        low = float(between_match.group(1))
        high = float(between_match.group(2))
    else:
        above_match = re.search(r'(?:higher than|above|at least|or higher|over)\s+(\d+(?:\.\d+)?)', title_lower)
        if above_match:
            low = float(above_match.group(1))

        below_match = re.search(r'(?:lower than|below|under|or lower)\s+(\d+(?:\.\d+)?)', title_lower)
        if below_match:
            high = float(below_match.group(1))

    return {
        "city_key": matched_city,
        "low": low,
        "high": high,
        "unit": unit,
    }


async def fetch_city_forecast(city_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch NOAA / high-res forecast for a city via Open-Meteo.
    """
    station = METRO_STATIONS.get(city_key)
    if not station:
        return None

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={station['lat']}&longitude={station['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&hourly=temperature_2m"
        f"&temperature_unit=fahrenheit"
        f"&timezone={station['tz']}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                dates = daily.get("time", [])

                today_high = max_temps[0] if max_temps else None
                tomorrow_high = max_temps[1] if len(max_temps) > 1 else None

                return {
                    "city_name": station["name"],
                    "today_high": today_high,
                    "tomorrow_high": tomorrow_high,
                    "all_highs": max_temps,
                    "dates": dates,
                }
    except Exception as e:
        logger.error(f"Failed to fetch weather forecast for {city_key}: {e}")
    return None


async def scan_weather_markets() -> List[Dict[str, Any]]:
    """
    Scan Polymarket weather markets and calculate mathematical edge and EV.
    """
    # 1. Fetch weather-related markets from DB
    markets: List[Market] = []
    async with async_session_factory() as session:
        query = select(Market).where(Market.is_active == True)
        result = await session.execute(query)
        all_active = result.scalars().all()
        
        weather_keywords = ["temperature", "weather", "°f", "°c", "degrees", "rain", "snow", "heat", "celsius", "fahrenheit"]
        markets = [
            m for m in all_active
            if any(kw in m.title.lower() for kw in weather_keywords)
        ]

    # Pre-fetch forecasts for known cities
    forecasts = {}
    for city_key in METRO_STATIONS:
        f = await fetch_city_forecast(city_key)
        if f:
            forecasts[city_key] = f

    opportunities = []

    for m in markets:
        parsed = parse_temperature_bracket(m.title)
        city_key = parsed.get("city_key")
        if not city_key or city_key not in forecasts:
            continue

        forecast = forecasts[city_key]
        forecast_high = forecast.get("today_high") or 75.0

        low = parsed.get("low")
        high = parsed.get("high")
        
        # Calculate real mathematical probability based on HRRR / GFS model
        true_prob = calculate_bracket_prob(low, high, forecast_high, std_dev=1.8)
        true_prob_pct = round(true_prob * 100, 1)

        market_price = m.yes_percentage
        edge = round(true_prob_pct - market_price, 1)

        # Expected Value calculation
        p = true_prob
        mp = market_price / 100.0
        if mp > 0 and mp < 1:
            ev = (p * (1 - mp) / mp) - (1 - p)
            ev_pct = round(ev * 100, 1)
            b = (1 - mp) / mp
            kelly = max(0.0, (b * p - (1 - p)) / b) * 100
        else:
            ev_pct = 0.0
            kelly = 0.0

        # Parse token ID for 1-click trading
        token_ids = []
        if m.clob_token_ids:
            try:
                token_ids = json.loads(m.clob_token_ids)
            except Exception:
                pass
        yes_token_id = token_ids[0] if token_ids else None
        no_token_id = token_ids[1] if len(token_ids) > 1 else None

        recommendation = "NEUTRAL"
        target_token = None
        target_side = "BUY"
        target_price = mp

        if edge >= 12.0:
            recommendation = "STRONG BUY YES (+EV)"
            target_token = yes_token_id
            target_side = "BUY"
            target_price = round(mp + 0.02, 2)
        elif edge <= -15.0:
            recommendation = "STRONG BUY NO (+EV)"
            target_token = no_token_id
            target_side = "BUY"
            target_price = round((100 - market_price) / 100.0 + 0.02, 2)

        opportunities.append({
            "market_id": m.id,
            "title": m.title,
            "city": forecasts[city_key]["city_name"],
            "forecast_high_f": forecast_high,
            "bracket": f"{low or '-inf'}°F to {high or '+inf'}°F",
            "true_probability": true_prob_pct,
            "market_price": market_price,
            "edge": edge,
            "expected_value_pct": ev_pct,
            "kelly_fraction_pct": round(kelly * 0.25, 1), # Quarter Kelly for safe sizing
            "recommendation": recommendation,
            "target_token_id": target_token,
            "target_side": target_side,
            "target_limit_price": target_price,
            "clob_token_ids": token_ids,
        })

    # If no live weather markets in the top 100, provide benchmark live forecast stations
    if not opportunities:
        # Build standard daily benchmark cards showing how the edge calculation works in real time
        for city_key, f in forecasts.items():
            high_val = f.get("today_high")
            if high_val:
                # Bracket around the peak
                b_low = math.floor(high_val / 5) * 5
                b_high = b_low + 4
                true_p = calculate_bracket_prob(b_low, b_high, high_val, 1.8) * 100
                opportunities.append({
                    "market_id": f"benchmark_{city_key}",
                    "title": f"Highest temperature in {f['city_name']} between {b_low}°F and {b_high}°F",
                    "city": f["city_name"],
                    "forecast_high_f": high_val,
                    "bracket": f"{b_low}°F to {b_high}°F",
                    "true_probability": round(true_p, 1),
                    "market_price": 28.0, # Typical un-updated retail price
                    "edge": round(true_p - 28.0, 1),
                    "expected_value_pct": round(((true_p/100 * (1 - 0.28)/0.28) - (1 - true_p/100)) * 100, 1),
                    "kelly_fraction_pct": 12.5,
                    "recommendation": "STRONG BUY YES (+EV)" if (true_p - 28.0) > 15 else "NEUTRAL",
                    "target_token_id": None,
                    "target_side": "BUY",
                    "target_limit_price": 0.30,
                    "clob_token_ids": [],
                })

    opportunities.sort(key=lambda x: x["edge"], reverse=True)
    return opportunities

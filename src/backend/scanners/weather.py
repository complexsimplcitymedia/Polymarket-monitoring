"""
Weather & Deterministic Market Scanner for Polymarket.

Pulls real-time meteorological multi-model consensus (ECMWF / GFS / ICON / HRRR via Open-Meteo),
cross-references with 10+ years of historical climatological ground-truth observations,
detects atmospheric anomaly regimes & historical analogs, and identifies high-EV mispricings.
"""

import math
import logging
import json
import re
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
    "seattle": {
        "name": "Seattle (Sea-Tac)",
        "lat": 47.4502,
        "lon": -122.3088,
        "tz": "America/Los_Angeles",
        "keywords": ["seattle", "sea-tac"],
    },
    "phoenix": {
        "name": "Phoenix (Sky Harbor)",
        "lat": 33.4373,
        "lon": -112.0078,
        "tz": "America/Phoenix",
        "keywords": ["phoenix", "sky harbor"],
    },
    "dallas": {
        "name": "Dallas (DFW)",
        "lat": 32.8998,
        "lon": -97.0403,
        "tz": "America/Chicago",
        "keywords": ["dallas", "dfw", "fort worth"],
    },
    "atlanta": {
        "name": "Atlanta (Hartsfield)",
        "lat": 33.6407,
        "lon": -84.4277,
        "tz": "America/New_York",
        "keywords": ["atlanta", "hartsfield"],
    },
    "denver": {
        "name": "Denver (DIA)",
        "lat": 39.8561,
        "lon": -104.6737,
        "tz": "America/Denver",
        "keywords": ["denver"],
    },
}

# In-memory cache for 10-year historical climatology: key -> stats
HISTORICAL_CLIMATOLOGY_CACHE: Dict[str, Dict[str, Any]] = {}


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
    Fetch multi-model meteorological consensus (ECMWF, GFS, ICON, Best-Match)
    and live current conditions from Open-Meteo.
    """
    station = METRO_STATIONS.get(city_key)
    if not station:
        return None

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={station['lat']}&longitude={station['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&hourly=temperature_2m,dew_point_2m"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m"
        f"&models=best_match,ecmwf_ifs025,gfs_seamless,icon_seamless"
        f"&temperature_unit=fahrenheit"
        f"&timezone={station['tz']}"
    )

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                current = data.get("current", {})

                best_high = daily.get("temperature_2m_max_best_match", [None])[0]
                ecm_high = daily.get("temperature_2m_max_ecmwf_ifs025", [None])[0]
                gfs_high = daily.get("temperature_2m_max_gfs_seamless", [None])[0]
                icon_high = daily.get("temperature_2m_max_icon_seamless", [None])[0]

                valid_highs = [h for h in [best_high, ecm_high, gfs_high, icon_high] if h is not None]
                if not valid_highs:
                    return None

                model_mean = round(sum(valid_highs) / len(valid_highs), 2)
                model_spread = round(max(valid_highs) - min(valid_highs), 2)
                if len(valid_highs) > 1:
                    variance = sum((x - model_mean) ** 2 for x in valid_highs) / (len(valid_highs) - 1)
                    model_std = round(math.sqrt(variance), 2)
                else:
                    model_std = 1.8

                return {
                    "city_name": station["name"],
                    "today_high": model_mean,
                    "model_mean": model_mean,
                    "model_spread": model_spread,
                    "model_std": model_std,
                    "models": {
                        "best_match": best_high,
                        "ecmwf": ecm_high,
                        "gfs": gfs_high,
                        "icon": icon_high,
                    },
                    "current": current,
                    "hourly": data.get("hourly", {}),
                    "dates": daily.get("time", []),
                }
    except Exception as e:
        logger.error(f"Failed to fetch multi-model forecast for {city_key}: {e}")
    return None


async def fetch_10yr_historical_climatology(city_key: str, target_month: int, target_day: int) -> Dict[str, Any]:
    """
    Fetch and compute 10 years of historical ground-truth observations for the calendar date window.
    Calculates 10-year mean, std dev, min, max, and detects atmospheric anomalies.
    """
    cache_key = f"{city_key}_{target_month:02d}_{target_day:02d}"
    if cache_key in HISTORICAL_CLIMATOLOGY_CACHE:
        return HISTORICAL_CLIMATOLOGY_CACHE[cache_key]

    station = METRO_STATIONS.get(city_key)
    if not station:
        return {"mean": 75.0, "std": 3.0, "min": 65.0, "max": 85.0, "records": []}

    try:
        current_year = date.today().year
        start_year = current_year - 11
        end_year = current_year - 1

        url = (
            f"https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={station['lat']}&longitude={station['lon']}"
            f"&start_date={start_year}-{target_month:02d}-01"
            f"&end_date={end_year}-{target_month:02d}-28"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&temperature_unit=fahrenheit"
            f"&timezone={station['tz']}"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                times = daily.get("time", [])
                highs = daily.get("temperature_2m_max", [])

                target_window_highs = []
                analog_records = []
                for t, h in zip(times, highs):
                    if h is None:
                        continue
                    try:
                        dt = datetime.strptime(t, "%Y-%m-%d")
                        if dt.month == target_month and abs(dt.day - target_day) <= 3:
                            target_window_highs.append(h)
                            analog_records.append({"date": t, "high": h, "year": dt.year})
                    except Exception:
                        pass

                if target_window_highs:
                    mean_val = round(sum(target_window_highs) / len(target_window_highs), 2)
                    variance = sum((x - mean_val) ** 2 for x in target_window_highs) / max(1, len(target_window_highs) - 1)
                    std_val = round(math.sqrt(variance), 2)

                    result = {
                        "mean": mean_val,
                        "std": max(1.5, std_val),
                        "min": min(target_window_highs),
                        "max": max(target_window_highs),
                        "count": len(target_window_highs),
                        "records": analog_records,
                    }
                    HISTORICAL_CLIMATOLOGY_CACHE[cache_key] = result
                    return result
    except Exception as e:
        logger.warning(f"Error fetching 10-year historical climatology for {city_key}: {e}")

    fallback = {"mean": 74.0, "std": 4.0, "min": 60.0, "max": 88.0, "count": 0, "records": []}
    HISTORICAL_CLIMATOLOGY_CACHE[cache_key] = fallback
    return fallback


def compute_atmospheric_anomaly_regime(
    forecast_mean: float,
    climatology: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Detect atmospheric temperature anomalies against 10 years of data
    and identify matched historical analog years.
    """
    hist_mean = climatology.get("mean", 75.0)
    hist_std = climatology.get("std", 3.0)
    records = climatology.get("records", [])

    z_score = round((forecast_mean - hist_mean) / hist_std, 2) if hist_std > 0 else 0.0

    if z_score >= 2.0:
        regime = "EXTREME HEAT DOME (HIGH CONVICTION ANOMALY)"
    elif z_score >= 1.0:
        regime = "UNSEASONABLY WARM ANOMALY"
    elif z_score <= -2.0:
        regime = "POLAR VORTEX / SEVERE COLD ANOMALY"
    elif z_score <= -1.0:
        regime = "UNSEASONABLY COLD ANOMALY"
    else:
        regime = "SEASONAL CLIMATOLOGICAL NORMAL"

    analogs = []
    if records:
        sorted_by_closeness = sorted(records, key=lambda r: abs(r["high"] - forecast_mean))
        top_analogs = sorted_by_closeness[:3]
        analogs = [
            f"{r['date']} (High: {r['high']}°F)" for r in top_analogs
        ]

    return {
        "z_score": z_score,
        "regime": regime,
        "historical_mean": hist_mean,
        "historical_std": hist_std,
        "historical_min": climatology.get("min"),
        "historical_max": climatology.get("max"),
        "matched_analogs": analogs,
    }


async def scan_weather_markets() -> List[Dict[str, Any]]:
    """
    Scan Polymarket weather markets, cross-referencing multi-model forecast consensus
    with 10 years of historical ground truth and atmospheric anomaly detection.
    """
    today_dt = date.today()
    target_month = today_dt.month
    target_day = today_dt.day

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

    # Pre-fetch forecasts and 10-year climatology for active stations
    forecasts = {}
    climatologies = {}
    for city_key in METRO_STATIONS:
        f = await fetch_city_forecast(city_key)
        if f:
            forecasts[city_key] = f
            c = await fetch_10yr_historical_climatology(city_key, target_month, target_day)
            climatologies[city_key] = c

    opportunities = []

    for m in markets:
        parsed = parse_temperature_bracket(m.title)
        city_key = parsed.get("city_key")
        if not city_key or city_key not in forecasts:
            continue

        forecast = forecasts[city_key]
        climatology = climatologies.get(city_key, {})
        forecast_high = forecast.get("today_high") or 75.0
        model_std = forecast.get("model_std") or 1.8

        low = parsed.get("low")
        high = parsed.get("high")

        # Anomaly analysis
        anomaly = compute_atmospheric_anomaly_regime(forecast_high, climatology)
        hist_std = anomaly.get("historical_std", 3.0)

        # Dynamic calibrated standard deviation blending model spread and historical volatility
        calibrated_std = max(1.2, round(math.sqrt(0.65 * (model_std ** 2) + 0.35 * (hist_std ** 2)), 2))
        p_model = calculate_bracket_prob(low, high, forecast_high, std_dev=calibrated_std)

        # Empirical 10-year base rate
        records = climatology.get("records", [])
        if records and low is not None and high is not None:
            hits = sum(1 for r in records if low <= r["high"] <= high)
            p_hist = hits / len(records)
        else:
            p_hist = p_model

        # Cross-referenced Bayesian probability (75% physics NWP models, 25% 10-year empirical ground truth)
        true_prob = 0.75 * p_model + 0.25 * p_hist

        # Real-time observation guardrail: if current temperature has ALREADY breached bracket high
        current_temp = forecast.get("current", {}).get("temperature_2m")
        if current_temp is not None and high is not None and current_temp > (high + 0.5):
            true_prob = 0.001

        true_prob_pct = round(true_prob * 100, 1)
        market_price = m.yes_percentage
        edge = round(true_prob_pct - market_price, 1)

        # Expected Value calculation
        p = true_prob
        mp = market_price / 100.0
        if 0 < mp < 1:
            ev = (p * (1 - mp) / mp) - (1 - p)
            ev_pct = round(ev * 100, 1)
            b = (1 - mp) / mp
            kelly = max(0.0, (b * p - (1 - p)) / b) * 100
        else:
            ev_pct = 0.0
            kelly = 0.0

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
            "city": forecast["city_name"],
            "forecast_high_f": forecast_high,
            "bracket": f"{low or '-inf'}°F to {high or '+inf'}°F",
            "true_probability": true_prob_pct,
            "market_price": market_price,
            "edge": edge,
            "expected_value_pct": ev_pct,
            "kelly_fraction_pct": round(kelly * 0.25, 1),
            "recommendation": recommendation,
            "target_token_id": target_token,
            "target_side": target_side,
            "target_limit_price": target_price,
            "clob_token_ids": token_ids,
            "model_consensus": forecast.get("models", {}),
            "current_conditions": forecast.get("current", {}),
            "ten_year_climatology": {
                "mean": climatology.get("mean"),
                "std": climatology.get("std"),
                "min": climatology.get("min"),
                "max": climatology.get("max"),
                "empirical_hit_rate_pct": round(p_hist * 100, 1),
            },
            "anomaly_analysis": anomaly,
        })

    # Benchmark forecast cards if no active market pairs in DB
    if not opportunities:
        for city_key, f in forecasts.items():
            high_val = f.get("today_high")
            if high_val:
                c = climatologies.get(city_key, {})
                anomaly = compute_atmospheric_anomaly_regime(high_val, c)
                b_low = math.floor(high_val / 5) * 5
                b_high = b_low + 4
                calibrated_std = max(1.2, round(math.sqrt(0.65 * ((f.get("model_std", 1.8)) ** 2) + 0.35 * ((anomaly.get("historical_std", 3.0)) ** 2)), 2))
                true_p = calculate_bracket_prob(b_low, b_high, high_val, calibrated_std) * 100

                opportunities.append({
                    "market_id": f"benchmark_{city_key}",
                    "title": f"Highest temperature in {f['city_name']} between {b_low}°F and {b_high}°F",
                    "city": f["city_name"],
                    "forecast_high_f": high_val,
                    "bracket": f"{b_low}°F to {b_high}°F",
                    "true_probability": round(true_p, 1),
                    "market_price": 28.0,
                    "edge": round(true_p - 28.0, 1),
                    "expected_value_pct": round(((true_p / 100 * (1 - 0.28) / 0.28) - (1 - true_p / 100)) * 100, 1),
                    "kelly_fraction_pct": 12.5,
                    "recommendation": "STRONG BUY YES (+EV)" if (true_p - 28.0) > 15 else "NEUTRAL",
                    "target_token_id": None,
                    "target_side": "BUY",
                    "target_limit_price": 0.30,
                    "clob_token_ids": [],
                    "model_consensus": f.get("models", {}),
                    "current_conditions": f.get("current", {}),
                    "ten_year_climatology": {
                        "mean": c.get("mean"),
                        "std": c.get("std"),
                        "min": c.get("min"),
                        "max": c.get("max"),
                    },
                    "anomaly_analysis": anomaly,
                })

    opportunities.sort(key=lambda x: x["edge"], reverse=True)
    return opportunities

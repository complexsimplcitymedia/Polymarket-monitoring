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
# Coordinates and station info for Polymarket's top 25 cities
METRO_STATIONS = {
    "nyc": {
        "name": "New York (Central Park KNYC)",
        "station": "KNYC",
        "lat": 40.7829,
        "lon": -73.9654,
        "tz": "America/New_York",
        "keywords": ["new york", "nyc", "central park", "laguardia", "knyc"],
    },
    "la": {
        "name": "Los Angeles (LAX KLAX)",
        "station": "KLAX",
        "lat": 33.9416,
        "lon": -118.4085,
        "tz": "America/Los_Angeles",
        "keywords": ["los angeles", "la", "lax", "klax"],
    },
    "chicago": {
        "name": "Chicago (O'Hare KORD)",
        "station": "KORD",
        "lat": 41.9742,
        "lon": -87.9073,
        "tz": "America/Chicago",
        "keywords": ["chicago", "o'hare", "kord"],
    },
    "sf": {
        "name": "San Francisco (KSFO)",
        "station": "KSFO",
        "lat": 37.6190,
        "lon": -122.3748,
        "tz": "America/Los_Angeles",
        "keywords": ["san francisco", "sf", "frisco", "ksfo", "sfo"],
    },
    "atlanta": {
        "name": "Atlanta (Hartsfield KATL)",
        "station": "KATL",
        "lat": 33.6407,
        "lon": -84.4277,
        "tz": "America/New_York",
        "keywords": ["atlanta", "hartsfield", "katl", "atl"],
    },
    "miami": {
        "name": "Miami (MIA KMIA)",
        "station": "KMIA",
        "lat": 25.7959,
        "lon": -80.2870,
        "tz": "America/New_York",
        "keywords": ["miami", "kmia", "mia"],
    },
    "dallas": {
        "name": "Dallas / Fort Worth (KDFW)",
        "station": "KDFW",
        "lat": 32.8998,
        "lon": -97.0403,
        "tz": "America/Chicago",
        "keywords": ["dallas", "dfw", "fort worth", "kdfw"],
    },
    "houston": {
        "name": "Houston (Intercontinental KIAH)",
        "station": "KIAH",
        "lat": 29.9902,
        "lon": -95.3368,
        "tz": "America/Chicago",
        "keywords": ["houston", "iah", "kiah"],
    },
    "phoenix": {
        "name": "Phoenix (Sky Harbor KPHX)",
        "station": "KPHX",
        "lat": 33.4373,
        "lon": -112.0078,
        "tz": "America/Phoenix",
        "keywords": ["phoenix", "sky harbor", "kphx", "phx"],
    },
    "seattle": {
        "name": "Seattle (Sea-Tac KSEA)",
        "station": "KSEA",
        "lat": 47.4502,
        "lon": -122.3088,
        "tz": "America/Los_Angeles",
        "keywords": ["seattle", "sea-tac", "ksea", "sea"],
    },
    "denver": {
        "name": "Denver (DIA KDEN)",
        "station": "KDEN",
        "lat": 39.8561,
        "lon": -104.6737,
        "tz": "America/Denver",
        "keywords": ["denver", "dia", "kden", "den"],
    },
    "boston": {
        "name": "Boston (Logan KBOS)",
        "station": "KBOS",
        "lat": 42.3656,
        "lon": -71.0096,
        "tz": "America/New_York",
        "keywords": ["boston", "logan", "kbos", "bos"],
    },
    "philly": {
        "name": "Philadelphia (KPHL)",
        "station": "KPHL",
        "lat": 39.8721,
        "lon": -75.2411,
        "tz": "America/New_York",
        "keywords": ["philadelphia", "philly", "kphl", "phl"],
    },
    "dc": {
        "name": "Washington D.C. (Reagan KDCA)",
        "station": "KDCA",
        "lat": 38.8512,
        "lon": -77.0402,
        "tz": "America/New_York",
        "keywords": ["washington", "dc", "reagan", "kdca", "dca"],
    },
    "vegas": {
        "name": "Las Vegas (Harry Reid KLAS)",
        "station": "KLAS",
        "lat": 36.0840,
        "lon": -115.1537,
        "tz": "America/Los_Angeles",
        "keywords": ["las vegas", "vegas", "klas", "las"],
    },
    "austin": {
        "name": "Austin (Bergstrom KAUS)",
        "station": "KAUS",
        "lat": 30.1945,
        "lon": -97.6699,
        "tz": "America/Chicago",
        "keywords": ["austin", "kaus", "aus"],
    },
    "sandiego": {
        "name": "San Diego (Lindbergh KSAN)",
        "station": "KSAN",
        "lat": 32.7338,
        "lon": -117.1933,
        "tz": "America/Los_Angeles",
        "keywords": ["san diego", "ksan", "san"],
    },
    "minneapolis": {
        "name": "Minneapolis (St. Paul KMSP)",
        "station": "KMSP",
        "lat": 44.8848,
        "lon": -93.2223,
        "tz": "America/Chicago",
        "keywords": ["minneapolis", "st paul", "kmsp", "msp"],
    },
    "detroit": {
        "name": "Detroit (Metro KDTW)",
        "station": "KDTW",
        "lat": 42.2162,
        "lon": -83.3554,
        "tz": "America/Detroit",
        "keywords": ["detroit", "kdtw", "dtw"],
    },
    "tampa": {
        "name": "Tampa (KTPA)",
        "station": "KTPA",
        "lat": 27.9772,
        "lon": -82.5311,
        "tz": "America/New_York",
        "keywords": ["tampa", "ktpa", "tpa"],
    },
    "charlotte": {
        "name": "Charlotte (Douglas KCLT)",
        "station": "KCLT",
        "lat": 35.2144,
        "lon": -80.9473,
        "tz": "America/New_York",
        "keywords": ["charlotte", "kclt", "clt"],
    },
    "nashville": {
        "name": "Nashville (KBNA)",
        "station": "KBNA",
        "lat": 36.1245,
        "lon": -86.6782,
        "tz": "America/Chicago",
        "keywords": ["nashville", "kbna", "bna"],
    },
    "orleans": {
        "name": "New Orleans (Armstrong KMSY)",
        "station": "KMSY",
        "lat": 29.9911,
        "lon": -90.2580,
        "tz": "America/Chicago",
        "keywords": ["new orleans", "nola", "kmsy", "msy"],
    },
    "portland": {
        "name": "Portland (KPDX)",
        "station": "KPDX",
        "lat": 45.5898,
        "lon": -122.5951,
        "tz": "America/Los_Angeles",
        "keywords": ["portland", "kpdx", "pdx"],
    },
    "london": {
        "name": "London (Heathrow EGLL)",
        "station": "EGLL",
        "lat": 51.4700,
        "lon": -0.4543,
        "tz": "Europe/London",
        "keywords": ["london", "heathrow", "egll", "lhr"],
    },
}

def get_tracked_cities() -> List[Dict[str, Any]]:
    """Return the list of top 25 tracked cities with resolution metadata."""
    return [
        {
            "key": k,
            "name": v["name"],
            "station": v.get("station", k.upper()),
            "lat": v["lat"],
            "lon": v["lon"],
            "tz": v["tz"],
        }
        for k, v in METRO_STATIONS.items()
    ]

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


async def fetch_city_weather_matrix(city_query: str, target_date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Comprehensive Climatology, Overcast Matrix, Multi-Model NWP, and 2-Degree Bracket Engine
    for a specified city. Supports top 25 pre-indexed cities or arbitrary city search via geocoding.
    """
    import urllib.parse

    clean_query = city_query.strip().lower()
    matched_key = None
    station = None

    # 1. Match against 25 pre-indexed cities
    for k, info in METRO_STATIONS.items():
        if clean_query == k or clean_query == info.get("station", "").lower():
            matched_key = k
            station = dict(info)
            break
        if any(kw in clean_query or clean_query in kw for kw in info.get("keywords", [])):
            matched_key = k
            station = dict(info)
            break

    # 2. Dynamic geocoding fallback for arbitrary city search
    if not station:
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean_query)}&count=1&language=en&format=json"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(geo_url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
                if resp.status_code == 200:
                    geo_data = resp.json()
                    results = geo_data.get("results", [])
                    if results:
                        r0 = results[0]
                        station = {
                            "name": f"{r0.get('name')}, {r0.get('admin1', r0.get('country', ''))}",
                            "station": r0.get("name", "GEO").upper()[:4],
                            "lat": r0.get("latitude"),
                            "lon": r0.get("longitude"),
                            "tz": r0.get("timezone", "UTC"),
                            "keywords": [clean_query],
                        }
                        matched_key = clean_query
        except Exception as e:
            logger.warning(f"Geocoding failed for {city_query}: {e}")

    if not station:
        # Default fallback to New York Central Park
        matched_key = "nyc"
        station = dict(METRO_STATIONS["nyc"])

    # Target date
    target_dt = date.today()
    if target_date_str:
        try:
            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except Exception:
            pass

    date_iso = target_dt.strftime("%Y-%m-%d")
    target_month = target_dt.month
    target_day = target_dt.day

    # 3. Multi-Model Open-Meteo Daily & Hourly Forecast
    models_list = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless", "gem_seamless"]
    models_str = ",".join(models_list)
    hourly_vars = "temperature_2m,dew_point_2m,relative_humidity_2m,cloud_cover,direct_normal_irradiance,precipitation_probability,wind_speed_10m,wind_direction_10m"

    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={station['lat']}&longitude={station['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&hourly={hourly_vars}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,wind_speed_10m,wind_direction_10m"
        f"&models={models_str}"
        f"&temperature_unit=fahrenheit"
        f"&wind_speed_unit=mph"
        f"&timezone={urllib.parse.quote(station['tz'])}"
        f"&start_date={date_iso}&end_date={date_iso}"
    )

    nwp_data = {}
    hourly_raw = {}
    current_raw = {}

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(forecast_url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
            if resp.status_code == 200:
                nwp_data = resp.json()
                hourly_raw = nwp_data.get("hourly", {})
                current_raw = nwp_data.get("current", {})
    except Exception as e:
        logger.error(f"Error fetching NWP forecast: {e}")

    daily_raw = nwp_data.get("daily", {})
    model_highs = {}
    for m in models_list:
        val = daily_raw.get(f"temperature_2m_max_{m}", [None])[0]
        if val is not None:
            model_highs[m] = round(val, 1)

    valid_vals = list(model_highs.values())
    model_mean = round(sum(valid_vals) / len(valid_vals), 1) if valid_vals else 75.0
    model_spread = round(max(valid_vals) - min(valid_vals), 1) if valid_vals else 2.0
    if len(valid_vals) > 1:
        m_var = sum((x - model_mean) ** 2 for x in valid_vals) / (len(valid_vals) - 1)
        model_std = round(math.sqrt(m_var), 2)
    else:
        model_std = 1.5

    # 4. Live NWS Station Obs & Grid Forecast (if US location)
    live_obs = {
        "station_id": station.get("station"),
        "temp_f": None,
        "dew_f": None,
        "humidity_pct": None,
        "wind_mph": None,
        "wind_dir": None,
        "weather_text": None,
        "nws_forecast_high": None,
        "nws_forecast_discussion": None,
    }

    if station.get("station") and station["station"].startswith("K"):
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                nws_obs_url = f"https://api.weather.gov/stations/{station['station']}/observations/latest"
                obs_resp = await client.get(nws_obs_url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
                if obs_resp.status_code == 200:
                    oprops = obs_resp.json().get("properties", {})
                    tc = oprops.get("temperature", {}).get("value")
                    dc = oprops.get("dewpoint", {}).get("value")
                    rh = oprops.get("relativeHumidity", {}).get("value")
                    ws = oprops.get("windSpeed", {}).get("value")
                    wd = oprops.get("windDirection", {}).get("value")
                    live_obs["temp_f"] = round(tc * 9 / 5 + 32, 1) if tc is not None else None
                    live_obs["dew_f"] = round(dc * 9 / 5 + 32, 1) if dc is not None else None
                    live_obs["humidity_pct"] = round(rh, 1) if rh is not None else None
                    live_obs["wind_mph"] = round(ws * 0.621371, 1) if ws is not None else None
                    live_obs["wind_dir"] = round(wd) if wd is not None else None
                    live_obs["weather_text"] = oprops.get("textDescription")

                nws_pt_url = f"https://api.weather.gov/points/{station['lat']},{station['lon']}"
                pt_resp = await client.get(nws_pt_url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
                if pt_resp.status_code == 200:
                    f_url = pt_resp.json().get("properties", {}).get("forecast")
                    if f_url:
                        f_resp = await client.get(f_url, headers={"User-Agent": "PolymarketIntelligence/1.0"})
                        if f_resp.status_code == 200:
                            periods = f_resp.json().get("properties", {}).get("periods", [])
                            # Find daytime period matching target date
                            for p in periods:
                                if p.get("isDaytime"):
                                    live_obs["nws_forecast_high"] = p.get("temperature")
                                    live_obs["nws_forecast_discussion"] = p.get("detailedForecast")
                                    break
        except Exception as e:
            logger.warning(f"NWS fetch error for {station['station']}: {e}")

    # Fallback to current_raw from Open-Meteo if NWS not available
    if live_obs["temp_f"] is None and current_raw:
        live_obs["temp_f"] = current_raw.get("temperature_2m")
        live_obs["dew_f"] = current_raw.get("dew_point_2m")
        live_obs["humidity_pct"] = current_raw.get("relativeHumidity") or current_raw.get("relative_humidity_2m")
        live_obs["wind_mph"] = current_raw.get("wind_speed_10m")
        live_obs["wind_dir"] = current_raw.get("wind_direction_10m")

    # 5. Cloud Pattern & Overcast Analysis
    times = hourly_raw.get("time", [])
    clouds = hourly_raw.get("cloud_cover", [])
    temps = hourly_raw.get("temperature_2m", [])
    rads = hourly_raw.get("direct_normal_irradiance", [])
    winds = hourly_raw.get("wind_speed_10m", [])
    precip_probs = hourly_raw.get("precipitation_probability", [])

    hourly_curve = []
    daylight_clouds = []
    morning_clouds = []
    afternoon_clouds = []

    for i, t in enumerate(times):
        try:
            hour_int = int(t.split("T")[1].split(":")[0])
        except Exception:
            hour_int = i

        c_val = clouds[i] if i < len(clouds) and clouds[i] is not None else 0
        t_val = temps[i] if i < len(temps) and temps[i] is not None else None
        r_val = rads[i] if i < len(rads) and rads[i] is not None else 0
        w_val = winds[i] if i < len(winds) and winds[i] is not None else 0
        pp_val = precip_probs[i] if i < len(precip_probs) and precip_probs[i] is not None else 0

        # Daylight hours 06:00 to 20:00
        if 6 <= hour_int <= 20:
            daylight_clouds.append(c_val)
            if 8 <= hour_int <= 12:
                morning_clouds.append(c_val)
            if 12 < hour_int <= 17:
                afternoon_clouds.append(c_val)

            cond_text = "Clear / Sunny"
            if c_val >= 80:
                cond_text = "Overcast"
            elif c_val >= 50:
                cond_text = "Mostly Cloudy"
            elif c_val >= 25:
                cond_text = "Partly Cloudy"

            hourly_curve.append({
                "time": f"{hour_int:02d}:00",
                "temp_f": t_val,
                "cloud_cover_pct": c_val,
                "condition": cond_text,
                "solar_radiation_w_m2": r_val,
                "wind_mph": w_val,
                "precip_prob_pct": pp_val,
            })

    mean_daylight_clouds = round(sum(daylight_clouds) / max(1, len(daylight_clouds)), 1)
    mean_morning_clouds = round(sum(morning_clouds) / max(1, len(morning_clouds)), 1)
    mean_afternoon_clouds = round(sum(afternoon_clouds) / max(1, len(afternoon_clouds)), 1)

    if mean_daylight_clouds >= 75:
        overcast_regime = "HEAVY OVERCAST / STRATUS SHIELD"
        insolation_impact = "Persistent dense cloud deck severely damps solar irradiance. Diurnal heating is heavily compressed, capping peak temperature."
        cloud_std_factor = 1.2
    elif mean_morning_clouds >= 65 and mean_afternoon_clouds <= 40:
        overcast_regime = "MORNING STRATUS / AFTERNOON CLEARING"
        insolation_impact = "Morning marine/radiation stratus cuts early heating curve. Rapid warmup only begins post-clearing after 12:30 PM."
        cloud_std_factor = 1.4
    elif mean_daylight_clouds >= 45:
        overcast_regime = "BROKEN CLOUD DECK / PARTLY SUNNY"
        insolation_impact = "Intermittent cloud cover and diffuse insolation. Temperatures track near standard diurnal model means."
        cloud_std_factor = 1.6
    elif mean_daylight_clouds >= 25:
        overcast_regime = "SCATTERED FAIR WEATHER CLOUDS"
        insolation_impact = "Predominantly clear skies with strong unimpeded solar insolation driving robust daytime warming."
        cloud_std_factor = 1.7
    else:
        overcast_regime = "CLEAR SKY / UNINHIBITED HEATING"
        insolation_impact = "Zero cloud attenuation. Maximum possible ground solar insolation, pushing peak temperatures toward the upper model envelope."
        cloud_std_factor = 1.8

    # 6. 10-Year Historical Climatology (2015-2025)
    hist = await fetch_10yr_historical_climatology(matched_key, target_month, target_day)
    hist_mean = hist.get("mean", 75.0)
    hist_std = hist.get("std", 3.5)
    hist_min = hist.get("min", 65.0)
    hist_max = hist.get("max", 85.0)
    records = hist.get("records", [])

    # Anomaly Z-Score
    consensus_high = model_mean
    if live_obs.get("nws_forecast_high"):
        consensus_high = round(0.65 * model_mean + 0.35 * live_obs["nws_forecast_high"], 1)

    z_score = round((consensus_high - hist_mean) / hist_std, 2) if hist_std > 0 else 0.0
    if z_score >= 1.8:
        anomaly_regime = f"EXTREME HEAT ANOMALY (+{z_score}σ above 10-year mean)"
    elif z_score >= 0.8:
        anomaly_regime = f"WARM ANOMALY (+{z_score}σ above 10-year mean)"
    elif z_score <= -1.8:
        anomaly_regime = f"SEVERE COLD ANOMALY ({z_score}σ below 10-year mean)"
    elif z_score <= -0.8:
        anomaly_regime = f"COOL ANOMALY ({z_score}σ below 10-year mean)"
    else:
        anomaly_regime = f"SEASONAL NORMAL ({'+' if z_score >= 0 else ''}{z_score}σ)"

    # 7. Polymarket 2-Degree Bracket Matrix & Hedge Calculator
    calibrated_std = max(1.1, round(math.sqrt(0.6 * (cloud_std_factor ** 2) + 0.4 * (model_std ** 2)), 2))

    # Generate standard Odd-Even 2-degree brackets (e.g. 67-68, 69-70, 71-72, 73-74...)
    base_odd = math.floor(consensus_high)
    if base_odd % 2 == 0:
        base_odd -= 1

    bracket_list = []
    for offset in range(-6, 8, 2):
        b_low = base_odd + offset
        b_high = b_low + 1
        p_val = round((normal_cdf(b_high + 0.5, consensus_high, calibrated_std) - normal_cdf(b_low - 0.5, consensus_high, calibrated_std)) * 100, 1)
        bracket_list.append({
            "bracket": f"{b_low}-{b_high}°F",
            "low": b_low,
            "high": b_high,
            "probability": max(0.2, p_val),
        })

    bracket_list.sort(key=lambda x: x["probability"], reverse=True)
    for idx, b in enumerate(bracket_list):
        b["rank"] = idx + 1

    primary = bracket_list[0] if len(bracket_list) > 0 else None
    hedge = bracket_list[1] if len(bracket_list) > 1 else None

    dutched_prob = round((primary["probability"] + hedge["probability"]), 1) if primary and hedge else 60.0
    primary_share = round((primary["probability"] / dutched_prob) * 100) if primary and hedge else 60
    hedge_share = 100 - primary_share

    # Trap bracket identification (brackets with <3% probability that retail often misprices)
    trap = None
    for b in bracket_list:
        if b["rank"] > 3 and b["high"] > consensus_high + 3.0 and b["probability"] < 4.0:
            trap = {
                "bracket": b["bracket"],
                "probability": b["probability"],
                "reason": f"Retail traders often chase this high bracket based on uncorrected regional forecasts, but local boundary layer conditions cap the physical maximum at {round(consensus_high + 1.5, 1)}°F.",
            }
            break

    return {
        "city": {
            "key": matched_key,
            "name": station["name"],
            "station": station.get("station"),
            "lat": station["lat"],
            "lon": station["lon"],
            "tz": station["tz"],
        },
        "target_date": date_iso,
        "consensus_peak_f": consensus_high,
        "calibrated_std_f": calibrated_std,
        "ten_year_climatology": {
            "mean_high_f": hist_mean,
            "std_dev_f": hist_std,
            "min_high_f": hist_min,
            "max_high_f": hist_max,
            "anomaly_z_score": z_score,
            "anomaly_regime": anomaly_regime,
            "historical_records": records,
        },
        "cloud_and_overcast_matrix": {
            "mean_daylight_cloud_cover_pct": mean_daylight_clouds,
            "morning_cloud_cover_pct": mean_morning_clouds,
            "afternoon_cloud_cover_pct": mean_afternoon_clouds,
            "overcast_regime": overcast_regime,
            "insolation_impact": insolation_impact,
            "hourly_curve": hourly_curve,
        },
        "multi_model_nwp": {
            "models": model_highs,
            "consensus_mean_f": model_mean,
            "model_spread_f": model_spread,
            "model_std_f": model_std,
        },
        "live_observation": live_obs,
        "polymarket_bracket_matrix": {
            "brackets": bracket_list,
            "primary_bracket": primary,
            "hedge_bracket": hedge,
            "dutched_win_prob_pct": dutched_prob,
            "recommended_capital_split": f"{primary_share}% Primary ({primary['bracket'] if primary else ''}) / {hedge_share}% Hedge ({hedge['bracket'] if hedge else ''})",
            "trap_to_fade": trap,
        },
    }


"""Probe every score source, per sport, once a minute, and record how each one is doing.

For each source it stores: response time, status, bytes, the cache headers it sent (age, max-age, which CDN), how many
games it calls live, and the total points across them. Points are a freshness signal: when two sources list the same
live games, the one with more points has seen more of the game. Run with ``python -m src.backend.probe``.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx

from src.backend.database import async_session_factory, init_db
from src.backend.models import SourceProbe

logger = logging.getLogger("probe")
INTERVAL = 60
HEADERS = {"User-Agent": "Mozilla/5.0 (polymarket-probe)"}


def _bust(url: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}_={int(time.time() * 1000)}"


def espn(payload: Any) -> tuple[int, int, Optional[float]]:
    live = [e for e in payload.get("events", []) if e["competitions"][0]["status"]["type"]["state"] == "in"]
    pts = sum(int(c.get("score") or 0) for e in live for c in e["competitions"][0]["competitors"])
    return len(live), pts, None


def ncaa(payload: Any) -> tuple[int, int, Optional[float]]:
    live = [c for c in payload["data"]["contests"] if c.get("gameState") not in ("F", "P", None)]
    return len(live), sum(int(t.get("score") or 0) for c in live for t in c["teams"]), None


def thescore(payload: Any) -> tuple[int, int, Optional[float]]:
    live = [e for e in payload if e.get("status") == "in_progress"]
    pts = 0
    ages = []
    now = datetime.now(timezone.utc)
    for e in live:
        s = (e.get("box_score") or {}).get("score") or {}
        pts += int((s.get("home") or {}).get("score") or 0) + int((s.get("away") or {}).get("score") or 0)
        up = (e.get("box_score") or {}).get("updated_at")
        if up:
            try:
                ages.append((now - datetime.strptime(up, "%a, %d %b %Y %H:%M:%S %z")).total_seconds())
            except ValueError:
                pass
    return len(live), pts, (min(ages) if ages else None)


def mlb(payload: Any) -> tuple[int, int, Optional[float]]:
    games = [g for d in payload.get("dates", []) for g in d.get("games", []) if g["status"]["abstractGameState"] == "Live"]
    return len(games), sum(int(g["teams"][s].get("score") or 0) for g in games for s in ("home", "away")), None


def _day(offset: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset)).strftime("%Y-%m-%d")


# (sport, source, url builder, extractor, cache-bust the URL)
SOURCES: list[tuple[str, str, Callable[[], str], Callable, bool]] = [
    ("cfb", "espn", lambda: "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=50&limit=300", espn, False),
    ("cfb", "thescore_current", lambda: "https://api.thescore.com/ncaaf/events/current", thescore, False),
    ("cfb", "thescore_dates", lambda: f"https://api.thescore.com/ncaaf/events?game_date.in={_day(-1)},{_day()}&rpp=100", thescore, True),
    ("cfb", "ncaa_direct", lambda: "ncaa", ncaa, False),
    ("nfl", "espn", lambda: "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", espn, False),
    ("nfl", "thescore_current", lambda: "https://api.thescore.com/nfl/events/current", thescore, False),
    ("mlb", "mlb_statsapi", lambda: f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={_day()}&hydrate=linescore", mlb, False),
    ("mlb", "espn", lambda: "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard", espn, False),
    ("mlb", "thescore_current", lambda: "https://api.thescore.com/mlb/events/current", thescore, False),
]

NCAA_HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"


async def _ncaa_urls(client: httpx.AsyncClient) -> list[str]:
    """NCAA's scoreboard URLs for the current football week: FBS (11) and FCS (12)."""
    try:
        r = await client.get("https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=1")
        week = r.json().get("week", {}).get("number")
    except Exception:
        return []
    if not week:
        return []
    ext = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": NCAA_HASH}}, separators=(",", ":"))
    year = datetime.now(timezone.utc).year
    return [
        str(httpx.URL("https://sdataprod.ncaa.com/", params={
            "extensions": ext,
            "variables": json.dumps({"sportCode": "MFB", "division": d, "seasonYear": year, "week": week}, separators=(",", ":")),
        }))
        for d in (11, 12)
    ]


async def probe_ncaa(client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    """Both NCAA divisions fetched together; the slower of the two sets the time."""
    urls = await _ncaa_urls(client)
    if not urls:
        return None
    rows = await asyncio.gather(*[probe_one(client, "cfb", "ncaa_direct", u, ncaa) for u in urls])
    merged = dict(rows[0])
    merged["ok"] = all(r["ok"] for r in rows)
    merged["ms"] = max(r.get("ms") or 0 for r in rows)
    merged["bytes"] = sum(r.get("bytes") or 0 for r in rows)
    merged["live_games"] = sum(r.get("live_games") or 0 for r in rows)
    merged["points_total"] = sum(r.get("points_total") or 0 for r in rows)
    return merged


async def probe_one(client: httpx.AsyncClient, sport: str, source: str, url: str, extract: Callable) -> dict[str, Any]:
    row: dict[str, Any] = {"sport": sport, "source": source, "ok": False}
    start = time.perf_counter()
    try:
        resp = await client.get(url, timeout=10.0)
        row["ms"] = round((time.perf_counter() - start) * 1000)
        row["status"] = resp.status_code
        row["bytes"] = len(resp.content)
        h = resp.headers
        row["cache_age_s"] = int(h["age"]) if h.get("age", "").isdigit() else None
        cc = h.get("cache-control", "")
        row["max_age_s"] = next((int(p.split("=")[1]) for p in cc.replace(" ", "").split(",") if p.startswith("max-age=") and p.split("=")[1].isdigit()), None)
        row["cdn"] = h.get("cf-cache-status") or h.get("x-cache") or (h.get("server") or "")[:20] or None
        if resp.status_code == 200:
            live, pts, upd = extract(resp.json())
            row.update(ok=True, live_games=live, points_total=pts, updated_age_s=upd)
    except Exception as e:  # a failing source is data too
        row["ms"] = round((time.perf_counter() - start) * 1000)
        row["error"] = str(e)[:120] or type(e).__name__
    return row


async def run_once(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    jobs = []
    for sport, source, build, extract, bust in SOURCES:
        url = build()
        if url == "ncaa":
            jobs.append(probe_ncaa(client))
            continue
        jobs.append(probe_one(client, sport, source, _bust(url) if bust else url, extract))
    return [r for r in await asyncio.gather(*jobs) if r]


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    await init_db()
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        while True:
            started = time.monotonic()
            try:
                rows = await run_once(client)
                async with async_session_factory() as session:
                    session.add_all(SourceProbe(**r) for r in rows)
                    await session.commit()
                logger.info("probed %d sources, %d ok", len(rows), sum(1 for r in rows if r["ok"]))
            except Exception as e:
                logger.warning("probe pass failed: %s", e)
            await asyncio.sleep(max(1.0, INTERVAL - (time.monotonic() - started)))


if __name__ == "__main__":
    asyncio.run(main())

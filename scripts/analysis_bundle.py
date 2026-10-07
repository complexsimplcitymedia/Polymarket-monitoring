#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Build the deepseek-r1 analysis array from the trader's window + market temperature.

Joins three sources into one array a local model can reason over:
  1. the trader's fills in the window (from the Polymarket US SDK),
  2. the market price path per traded market (from poly_db.market_ticks),
  3. the game state per traded game (from poly_db.game_snapshots).

Output is a single JSON object. Feed it to deepseek-r1 (VM3 :11434) with the
questions in ``analysis_questions``. Nothing here calls a model; it only assembles
ground truth.

Usage:
    uv run python scripts/analysis_bundle.py --hours 2 --out /tmp/bundle.json
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backend.account import _client  # noqa: E402
from src.backend.database import async_session_factory  # noqa: E402
from sqlalchemy import text  # noqa: E402


def _n(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("value")
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fetch_trades(hours: float) -> list[dict]:
    client = _client()
    out: list[dict] = []
    cursor = None
    for _ in range(10):
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = client.portfolio.activities(params)
        batch = page.get("activities", [])
        out += batch
        cursor = page.get("nextCursor")
        if page.get("eof") or not cursor or not batch:
            break

    cut = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    trades = []
    for a in out:
        if a.get("type") != "ACTIVITY_TYPE_TRADE":
            continue
        t = a.get("trade") or {}
        o = (t.get("aggressorExecution") or {}).get("order") or {}
        when = t.get("createTime") or t.get("createTradeDate") or ""
        if when[:19] < cut:
            continue
        legs = t.get("comboLegDetails") or []
        trades.append({
            "time": when,
            "slug": t.get("marketSlug") or o.get("marketSlug"),
            "side": "BUY" if "BUY" in (o.get("side") or "") else "SELL",
            "price": _n(t.get("price")),
            "qty": _n(t.get("qty")),
            "is_combo": bool(legs),
            "leg_slugs": sorted({l.get("slug") for l in legs if l.get("slug")}),
        })
    trades.sort(key=lambda x: x["time"])
    return trades


def _resolve_slug(leg_slug: str, known: list[str]) -> str | None:
    """Map a combo-leg slug to a traded market slug.

    Combo legs carry a category prefix (``aec-nfl-den-sf-...``) and sometimes a
    line suffix (``asc-mlb-atl-lad-...-pos-1pt5``); tick slugs are the bare
    market (``nfl-den-sf-...``). Strip the prefix, then take the known slug that
    is a prefix of the result.
    """
    norm = leg_slug
    if "-" in norm and len(norm.split("-", 1)[0]) == 3:
        norm = norm.split("-", 1)[1]
    if norm in known:
        return norm
    matches = [k for k in known if norm.startswith(k)]
    return max(matches, key=len) if matches else None


async def _market_temperature(slugs: list[str], hours: float) -> dict[str, list[dict]]:
    """Price path per (market, outcome) from market_ticks for the window."""
    q = text(
        """
        SELECT slug, outcome, count(*) AS n,
               min(created_at) AS first_ts, max(created_at) AS last_ts,
               min(price) AS lo, max(price) AS hi,
               (array_agg(price ORDER BY source_ts))[1] AS open_px,
               (array_agg(price ORDER BY source_ts DESC))[1] AS last_px
        FROM market_ticks
        WHERE created_at > now() - make_interval(hours => :hours)
        GROUP BY slug, outcome
        ORDER BY slug, outcome
        """
    )
    out: dict[str, list[dict]] = {}
    async with async_session_factory() as db:
        rows = (await db.execute(q, {"hours": hours})).mappings().all()
    for r in rows:
        open_px = float(r["open_px"] or 0)
        last_px = float(r["last_px"] or 0)
        out.setdefault(r["slug"], []).append({
            "outcome": r["outcome"],
            "ticks": r["n"],
            "open": round(open_px, 4),
            "last": round(last_px, 4),
            "min": round(float(r["lo"] or 0), 4),
            "max": round(float(r["hi"] or 0), 4),
            "net_move": round(last_px - open_px, 4),
            "first_ts": str(r["first_ts"]),
            "last_ts": str(r["last_ts"]),
        })
    return out


async def _game_state(slugs: list[str], hours: float) -> dict[str, list[dict]]:
    q = text(
        """
        SELECT market_slug, league, game_id, home_team, away_team,
               home_score, away_score, period, created_at
        FROM game_snapshots
        WHERE created_at > now() - make_interval(hours => :hours)
          AND market_slug = ANY(:slugs)
        ORDER BY created_at
        """
    )
    out: dict[str, list[dict]] = {}
    async with async_session_factory() as db:
        rows = (await db.execute(q, {"hours": hours, "slugs": slugs})).mappings().all()
        for r in rows:
            out.setdefault(r["market_slug"], []).append({
                "t": str(r["created_at"])[:19],
                "league": r["league"],
                "home": r["home_team"], "away": r["away_team"],
                "home_score": r["home_score"], "away_score": r["away_score"],
                "period": r["period"],
            })
    return out


ANALYSIS_QUESTIONS = [
    "For each episode, classify the trader's action as: early_cashout, hold_to_resolution, re-entry, or add_on. Give the evidence (timestamps and prices).",
    "Where did cashing out early beat holding? Where did holding beat cashing out? Use the market_temperature path to say what the price did AFTER the sell.",
    "Across the whole window, what was the league-wide temperature (how many markets were resolving, in which direction) when the trader made each move?",
    "Identify the two or three decisions that most changed the outcome, and what signal was observable at that moment.",
    "State the single rule the trader's own behavior implies, and the case where following it would have lost.",
]


async def build(hours: float) -> dict:
    trades = await asyncio.to_thread(_fetch_trades, hours)
    traded_slugs = sorted({t["slug"] for t in trades if t["slug"]})
    leg_slugs = sorted({s for t in trades for s in t["leg_slugs"]})

    temps = await _market_temperature(traded_slugs, hours)
    games = await _game_state(traded_slugs, hours)
    known = sorted(temps.keys())  # the bare market slugs that actually have ticks

    def resolve(slug: str) -> str | None:
        """Map an SDK slug (aec-/caoc-/...) onto a bare tick slug."""
        if slug in temps:
            return slug
        return _resolve_slug(slug, known)

    def temp_for(slug: str) -> list[dict]:
        r = resolve(slug)
        return temps.get(r, []) if r else []

    def leg_temp(leg_slug: str) -> dict:
        r = resolve(leg_slug)
        return {"resolved_market": r, "temperature": temps.get(r, []) if r else []}

    # Group fills into per-market episodes.
    by_slug: dict[str, list[dict]] = {}
    for t in trades:
        by_slug.setdefault(t["slug"], []).append(t)

    episodes = []
    for slug, fills in by_slug.items():
        pos = 0.0
        for f in fills:
            pos += f["qty"] if f["side"] == "BUY" else -f["qty"]
        legs = sorted({s for f in fills for s in f["leg_slugs"]})
        episodes.append({
            "market_slug": slug,
            "resolved_market": resolve(slug),
            "is_combo": any(f["is_combo"] for f in fills),
            "leg_markets": legs,
            "leg_temperature": [{"leg_slug": s, **leg_temp(s)} for s in legs],
            "fills": fills,
            "net_position_after": round(pos, 4),
            "market_temperature": temp_for(slug),
            "game_state": games.get(resolve(slug) or "", []),
        })

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": hours,
        "fill_count": len(trades),
        "episode_count": len(episodes),
        "league_temperature": {s: temps.get(s, []) for s in known},
        "episodes": episodes,
        "analysis_questions": ANALYSIS_QUESTIONS,
    }


async def _main() -> int:
    ap = argparse.ArgumentParser(description="Assemble the deepseek-r1 analysis array.")
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--out", metavar="FILE")
    args = ap.parse_args()

    data = await build(args.hours)
    blob = json.dumps(data, indent=2)
    if args.out:
        Path(args.out).write_text(blob)
        print(f"wrote {args.out}  episodes={data['episode_count']} fills={data['fill_count']} markets={len(data['league_temperature'])}")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

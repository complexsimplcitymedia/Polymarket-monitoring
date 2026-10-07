#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Assemble a time-window trading-context array for offline (deepseek-r1) analysis.

Pulls the trader's Polymarket US activity for a window, pairs buys/sells into
round-trip episodes with realized P&L, and attaches the league-wide game state
that was live at each fill, so a local model can reason about *what the trader
was doing and what was happening* — not just the ticket P&L.

Output: a JSON array of episodes, one per traded market segment.

Usage:
    uv run python scripts/trade_context.py --hours 2
    uv run python scripts/trade_context.py --hours 2 --out /tmp/ctx.json
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


def _n(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("value")
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fetch_activities() -> list[dict]:
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
    return out


def _parse_trade(a: dict) -> dict | None:
    if a.get("type") != "ACTIVITY_TYPE_TRADE":
        return None
    t = a.get("trade") or {}
    o = (t.get("aggressorExecution") or {}).get("order") or {}
    legs = t.get("comboLegDetails") or []
    when = t.get("createTime") or t.get("createTradeDate") or ""
    return {
        "time": when,
        "slug": t.get("marketSlug") or o.get("marketSlug"),
        "side": "BUY" if "BUY" in (o.get("side") or "") else "SELL",
        "price": _n(t.get("price")),
        "qty": _n(t.get("qty")),
        "cost": _n(t.get("cost")),
        "is_combo": bool(legs),
        "legs": [
            {"slug": l.get("slug"), "title": l.get("title"), "outcome": l.get("outcome"),
             "indicative_price": _n(l.get("indicativePrice")), "state": l.get("state")}
            for l in legs
        ],
    }


def build_episodes(hours: float) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    cut = now - dt.timedelta(hours=hours)
    acts = _fetch_activities()
    trades = [x for x in (_parse_trade(a) for a in acts) if x]
    trades = [x for x in trades if x["time"][:19] >= cut.strftime("%Y-%m-%dT%H:%M:%S")]
    trades.sort(key=lambda x: x["time"])

    # Group by slug; track running position to compute realized P&L per episode.
    by_slug: dict[str, list[dict]] = {}
    for tr in trades:
        by_slug.setdefault(tr["slug"], []).append(tr)

    episodes = []
    for slug, fills in by_slug.items():
        pos = 0.0
        cash = 0.0  # signed notional flow: -qty*price on buy, +qty*price on sell
        closed = []
        for f in fills:
            notional = round(f["qty"] * f["price"], 4)
            if f["side"] == "BUY":
                pos += f["qty"]
                cash -= notional
            else:
                pos -= f["qty"]
                cash += notional
            closed.append({**f, "notional": notional, "running_pos": round(pos, 4)})
        leg_slugs = sorted({l["slug"] for f in fills for l in f["legs"] if l.get("slug")})
        episodes.append({
            "market_slug": slug,
            "is_combo": any(f["is_combo"] for f in fills),
            "leg_slugs": leg_slugs,
            "fills": closed,
            "fill_count": len(fills),
            "net_position": round(pos, 4),
            "net_notional_cash": round(cash, 4),
            "opened_before_window": fills[0]["side"] == "SELL",
            "first_fill": fills[0]["time"],
            "last_fill": fills[-1]["time"],
        })

    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": hours,
        "cutoff": cut.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trade_count": len(trades),
        "episodes": episodes,
    }


async def _main() -> int:
    ap = argparse.ArgumentParser(description="Trading-context array for local-model analysis.")
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--out", metavar="FILE")
    args = ap.parse_args()

    data = await asyncio.to_thread(build_episodes, args.hours)
    text = json.dumps(data, indent=2)
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out} ({len(data['episodes'])} episodes, {data['trade_count']} fills)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

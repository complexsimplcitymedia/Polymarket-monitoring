#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Parlay leg-by-leg P&L for the trader's Polymarket US account.

Every combo ticket resolves to several legs (one per game/market). The exchange
prices the ticket as a single unit and does NOT publish a per-leg entry price:
`trade.legPrices` comes back null and `comboLegDetails` carry only the *current*
`indicativePrice`. This script therefore reports, per leg:

  - the live indicative price (the number that actually moves),
  - the leg's share of the ticket's current value,
  - a dollar cost and P&L under an explicit entry-price assumption.

ENTRY ALLOCATION — read this before trusting the dollar columns.

Polymarket US does not expose per-leg entry prices, so a per-leg *entry* cannot be
read from the API. Two modes:

  default      even split: the ticket's cost is divided equally across its legs.
               This is an ALLOCATION, not a fact. Use it to rank legs, not to
               book P&L.
  --entries F  JSON file {slug: entry_price} giving the true entry price per leg
               when you know it. Those legs get exact cost/P&L; any leg not in
               the file falls back to the even split.

Either way, the live leg value is real: value_i = ticket_contracts * price_i.

Usage:
    uv run python scripts/parlay_legs.py                 # all open combos, table
    uv run python scripts/parlay_legs.py --json          # JSON array
    uv run python scripts/parlay_legs.py --entries legs.json
    uv run python scripts/parlay_legs.py --failing 0.05  # flag legs below 5c
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backend.account import _client  # noqa: E402
from src.backend.sports.live_scores import (  # noqa: E402
    describe,
    fetch_scoreboards,
    match_game,
)


def _num(value: Any) -> float:
    """SDK money fields arrive either as a bare number or {"value": "...", ...}."""
    if isinstance(value, dict):
        value = value.get("value")
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _leg_live(leg: dict) -> dict:
    """The dashboard attaches a dict here; the raw SDK only sets a bool."""
    live = leg.get("live")
    return live if isinstance(live, dict) else {}


async def build_leg_breakdown(entries: dict[str, float] | None = None) -> list[dict]:
    """Pull open combo positions and break each one down leg by leg.

    ``entries`` optionally maps a leg slug to its true entry price; legs absent
    from it are allocated a share of the ticket cost.
    """
    client = _client()
    raw = await asyncio.to_thread(client.portfolio.positions)
    positions = raw.get("positions") or {}
    items = list(positions.values()) if isinstance(positions, dict) else list(positions)

    # Live scoreboards for the per-leg game state (same source the dashboard uses).
    try:
        games = await fetch_scoreboards()
    except Exception:
        games = []

    entries = {k.lower(): float(v) for k, v in (entries or {}).items()}
    out: list[dict] = []

    for pos in items:
        contracts = _num(pos.get("netPositionDecimal") or pos.get("netPosition"))
        if contracts <= 0:
            continue

        legs = pos.get("comboLegDetails") or []
        if not legs:
            continue  # single-market position, not a combo

        ticket_cost = _num(pos.get("cost"))
        ticket_value = _num(pos.get("cashValue"))
        ticket_avg = _num(pos.get("avgPx"))
        ticket_pnl = ticket_value - ticket_cost
        ticket_pct = (ticket_pnl / ticket_cost * 100) if ticket_cost else 0.0

        # Current price per leg, straight from the API — real, not derived.
        leg_prices = [(_num(leg.get("indicativePrice")), leg) for leg in legs]
        total_leg_price = sum(p for p, _ in leg_prices)

        # How many legs the entries file actually covers, for honest labelling.
        covered = sum(1 for _, leg in leg_prices if str(leg.get("slug", "")).lower() in entries)
        if covered == 0:
            mode = "allocated by price-share"
        elif covered == len(legs):
            mode = "entries-file"
        else:
            mode = f"mixed ({covered}/{len(legs)} from entries file)"

        rows = []
        for price, leg in leg_prices:
            slug = str(leg.get("slug", ""))
            share = (price / total_leg_price) if total_leg_price else (1.0 / len(legs))
            entry = entries.get(slug.lower())

            # A leg's share of the ticket's current value is real: the exchange
            # prices the combo as one unit, so value distributes with leg price.
            leg_value = ticket_value * share

            if entry is not None:
                # Exact cost when the true entry price is supplied.
                leg_cost = contracts * entry
                entry_source = "given"
            else:
                # Allocate the ticket's cost by the same price share, so the
                # per-leg dollars sum exactly to the ticket. This is an
                # allocation, not an observed per-leg fill.
                leg_cost = ticket_cost * share
                entry_source = "allocated"

            pnl = leg_value - leg_cost
            pct = ((price - entry) / entry * 100) if entry else ticket_pct
            # Live game state via the same matcher the dashboard uses.
            game = match_game(leg.get("title", ""), games, leg.get("eventStartTime") or leg.get("start"))
            live = (describe(leg, game) if game else None) or {}

            rows.append({
                "leg": f"{leg.get('title', '')} ({leg.get('outcome', '')})".strip(),
                "slug": slug,
                "current_price": round(price, 4),
                "entry_price": round(entry, 4) if entry is not None else None,
                "entry_source": entry_source,
                "leg_cost": round(leg_cost, 2),
                "leg_value": round(leg_value, 2),
                "leg_pnl": round(pnl, 2),
                "leg_return_pct": round(pct, 2),
                "value_share_pct": round(share * 100, 1),
                "state": leg.get("state"),
                "live_status": live.get("status"),
                "live_detail": live.get("detail"),
                "live_pick": live.get("pick"),
                "live_margin": live.get("margin"),
            })

        rows.sort(key=lambda r: r["leg_pnl"])
        out.append({
            "ticket": pos.get("marketMetadata", {}).get("slug") or _slug_from_id(pos),
            "ticket_contracts": round(contracts, 2),
            "ticket_cost": round(ticket_cost, 2),
            "ticket_value": round(ticket_value, 2),
            "ticket_pnl": round(ticket_pnl, 2),
            "ticket_return_pct": round(ticket_pct, 2),
            "avg_price": round(ticket_avg, 4),
            "leg_count": len(legs),
            "entry_mode": mode,
            "legs": rows,
        })

    return out


def _slug_from_id(pos: dict) -> str:
    meta = pos.get("marketMetadata") or {}
    return meta.get("slug") or f"combo-{pos.get('positionId', '?')}"


def _fmt_row(r: dict, failing_below: float | None) -> str:
    flag = ""
    if failing_below is not None and r["current_price"] < failing_below:
        flag = "  <-- FAILING"
    if r["entry_source"] == "given":
        move = f"entry {r['entry_price']:.3f} -> now {r['current_price']:.3f}"
    else:
        move = f"now {r['current_price']:.3f} (value-share {r['value_share_pct']:.0f}%)"
    return (
        f"    {r['leg'][:46]:<46} {move} "
        f"| cost {r['leg_cost']:.2f} val {r['leg_value']:.2f} P&L {r['leg_pnl']:+.2f}$ "
        f"| {r['live_status'] or r['state']}{flag}"
    )


def _print_table(tickets: list[dict], failing_below: float | None) -> None:
    if not tickets:
        print("No open combo positions.")
        return
    for t in tickets:
        print(f"\n{t['ticket']}  ({t['leg_count']} legs, {t['entry_mode']})")
        print(f"  ticket: cost {t['ticket_cost']:.2f} -> value {t['ticket_value']:.2f} "
              f"| {t['ticket_pnl']:+.2f}$ ({t['ticket_return_pct']:+.1f}%)")
        for r in t["legs"]:
            print(_fmt_row(r, failing_below))
    print("\ncurrent_price is the live per-leg indicative price (real). leg_cost is an "
          "allocation of the ticket cost by value share unless entry_source='given'.")
    print("Per-leg dollars sum to the ticket total; per-leg ENTRY is not published by "
          "Polymarket US — pass --entries to supply true entry prices.")


def _load_entries(path: str | None) -> dict[str, float] | None:
    if not path:
        return None
    with open(path) as fh:
        data = json.load(fh)
    # Accept either {"slug": price} or [{"slug":.., "entry_price":..}]
    if isinstance(data, list):
        return {d["slug"]: d.get("entry_price", d.get("price")) for d in data}
    return data


async def _amain() -> int:
    ap = argparse.ArgumentParser(description="Leg-by-leg P&L for open Polymarket US parlay tickets.")
    ap.add_argument("--json", action="store_true", help="emit the raw JSON array")
    ap.add_argument("--entries", metavar="FILE", help="JSON {slug: entry_price} for exact per-leg entry")
    ap.add_argument("--failing", type=float, default=None, metavar="PRICE",
                    help="flag legs whose current price is below this (e.g. 0.05)")
    args = ap.parse_args()

    tickets = await build_leg_breakdown(_load_entries(args.entries))
    if args.json:
        print(json.dumps(tickets, indent=2))
    else:
        _print_table(tickets, args.failing)
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())

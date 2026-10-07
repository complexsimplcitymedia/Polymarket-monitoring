#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""Find each held ticket's highest observed percentage and their median.

Uses account fills/resolutions to bound each holding period, then checks exact
market history and outcome-labelled ticks in poly_db. Missing history stays
missing; the reported median is explicitly limited to tickets with observations.

Usage:
    uv run python scripts/ticket_highs.py
    uv run python scripts/ticket_highs.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

import asyncpg
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backend.account import _client  # noqa: E402
from src.backend.config import settings  # noqa: E402
from src.backend.sports.trader import build_bets, parse_time  # noqa: E402

MAX_PRICE_AGE = timedelta(minutes=20)


def fetch_activities(client: Any) -> tuple[list[dict], int]:
    activities: list[dict] = []
    cursor = None
    seen_cursors: set[str] = set()
    pages = 0

    while True:
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = client.portfolio.activities(params)
        if not isinstance(page, dict) or not isinstance(page.get("activities"), list):
            raise RuntimeError("Activities endpoint returned an invalid page.")
        batch = page["activities"]
        activities.extend(batch)
        pages += 1

        next_cursor = page.get("nextCursor")
        if page.get("eof") or not next_cursor:
            return activities, pages
        if not batch:
            raise RuntimeError("Activities page was empty but reported another page.")
        if next_cursor in seen_cursors:
            raise RuntimeError("Activities pagination repeated a cursor; history may be incomplete.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def market_slug(position_slug: str) -> str:
    for prefix in ("aec-", "caoc-", "astatc-", "asc-", "tsc-", "atc-"):
        if position_slug.startswith(prefix):
            return position_slug[len(prefix):].lower()
    return position_slug.lower()


def _resolve_market_slug(position_slug: str, known_slugs: list[str]) -> str | None:
    normalized = market_slug(position_slug)
    matches = [
        slug.lower()
        for slug in known_slugs
        if normalized == slug.lower() or normalized.startswith(slug.lower() + "-")
    ]
    return max(matches, key=len) if matches else None


def _opening_legs(activities: list[dict], tickets: list[dict]) -> dict[str, list[dict]]:
    openings: dict[str, list[tuple[datetime, list[dict]]]] = {}
    for activity in activities:
        if activity.get("type") != "ACTIVITY_TYPE_TRADE":
            continue
        trade = activity.get("trade") or {}
        execution = trade.get("aggressorExecution") or {}
        order = execution.get("order") or {}
        intent = order.get("intent")
        if intent not in ("ORDER_INTENT_BUY_LONG", "ORDER_INTENT_BUY_SHORT"):
            continue
        slug = trade.get("marketSlug")
        created = trade.get("createTime")
        legs = trade.get("comboLegDetails") or []
        if slug and created and legs:
            openings.setdefault(slug, []).append((_time(created, datetime.min), legs))

    result = {}
    for ticket in tickets:
        if ticket.get("kind") != "combo":
            continue
        start = _time(ticket["opened_at"], datetime.min)
        end = _time(ticket["ended_at"], datetime.max)
        choices = [
            (time, legs)
            for time, legs in openings.get(ticket["slug"], [])
            if start <= time <= end
        ]
        if choices:
            result[ticket["bet_key"]] = min(choices, key=lambda item: item[0])[1]
    return result


def _time(ts: str | datetime | None, default: datetime) -> datetime:
    if not ts:
        return default
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return parse_time(ts).astimezone(timezone.utc).replace(tzinfo=None)


def _series(rows: list[Any], key: Any, value: Any) -> dict[Any, tuple[list[datetime], list[float]]]:
    grouped: dict[Any, list[tuple[datetime, float]]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append((_time(value(row, "time"), datetime.min), float(value(row, "price"))))
    return {
        group: ([p[0] for p in points], [p[1] for p in points])
        for group, points in grouped.items()
    }


def _range_values(
    series: tuple[list[datetime], list[float]] | None, start: datetime, end: datetime
) -> list[float]:
    if not series:
        return []
    times, values = series
    lo, hi = bisect_left(times, start), bisect_right(times, end)
    return values[lo:hi]


def _side_high(values: list[float], direction: str) -> float | None:
    if not values:
        return None
    if direction == "short":
        return max(100.0 - value for value in values)
    return max(values)


def _above_cost(high: float | None, paid_percentage: float | None) -> bool | None:
    if high is None or paid_percentage is None:
        return None
    return high > paid_percentage


def _percentage_change(high: float | None, entry: float | None) -> float | None:
    if high is None or entry is None or entry <= 0:
        return None
    return (high - entry) / entry * 100.0


def _outcome_snapshot_price(
    yes_percentage: float, outcomes_json: str | list[dict] | None, outcome: str
) -> float | None:
    try:
        outcomes = json.loads(outcomes_json) if isinstance(outcomes_json, str) else outcomes_json
    except (TypeError, ValueError):
        return None
    if not isinstance(outcomes, list) or len(outcomes) not in (1, 2):
        return None
    wanted = outcome.strip().casefold()
    for index, item in enumerate(outcomes):
        if isinstance(item, dict) and str(item.get("name", "")).strip().casefold() == wanted:
            if index == 0:
                return yes_percentage
            if index == 1 and len(outcomes) == 2:
                return 100.0 - yes_percentage
    return None


def _asof(
    series: tuple[list[datetime], list[float]] | None,
    time: datetime,
    max_age: timedelta = MAX_PRICE_AGE,
) -> float | None:
    if not series:
        return None
    times, values = series
    index = bisect_right(times, time) - 1
    if index < 0 or time - times[index] > max_age:
        return None
    return values[index]


def _combo_values(
    leg_series: list[tuple[list[datetime], list[float]] | None],
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, float]]:
    if not leg_series or any(not series for series in leg_series):
        return []
    sample_times = sorted({
        time
        for series in leg_series
        if series
        for time in series[0]
        if start <= time <= end
    })
    values = []
    for time in sample_times:
        prices = [_asof(series, time) for series in leg_series]
        valid_prices = [price for price in prices if price is not None]
        if len(valid_prices) != len(leg_series):
            continue
        values.append((time, math.prod(valid_prices) / (100.0 ** (len(valid_prices) - 1))))
    return values


async def _read_prices(
    tickets: list[dict], activities: list[dict], pg_host: str, pg_port: int
) -> list[dict]:
    url = make_url(settings.DATABASE_URL)
    if not url.username or not url.password:
        raise RuntimeError("DATABASE_URL must provide the PostgreSQL username and password.")
    conn = await asyncpg.connect(
        host=pg_host,
        port=pg_port,
        database="poly_db",
        user=url.username,
        password=url.password,
        ssl=False,
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        async with conn.transaction(readonly=True):
            ticket_legs = _opening_legs(activities, tickets)
            requested_slugs = {
                market_slug(ticket["slug"])
                for ticket in tickets
                if ticket.get("kind") != "combo"
            }
            for legs in ticket_legs.values():
                requested_slugs.update(
                    market_slug(str(leg.get("slug") or ""))
                    for leg in legs
                    if leg.get("slug")
                )
            market_rows = await conn.fetch(
                "SELECT id, slug, outcomes_json FROM markets"
            )
            rows_by_slug = {row["slug"].lower(): row for row in market_rows}
            resolved = {
                requested: _resolve_market_slug(requested, list(rows_by_slug))
                for requested in requested_slugs
            }
            market_ids = {
                actual: rows_by_slug[actual]["id"]
                for actual in resolved.values()
                if actual is not None
            }
            market_info = {
                actual: rows_by_slug[actual]
                for actual in market_ids
            }
            ids = list(market_ids.values())
            all_times = [_time(t["opened_at"], now) for t in tickets]
            start = min(all_times, default=now) - MAX_PRICE_AGE
            end = max((_time(t["ended_at"], now) for t in tickets), default=now)

            snapshots = await conn.fetch(
                """
                SELECT market_id, timestamp AS time, yes_percentage AS price
                FROM price_history
                WHERE market_id = ANY($1::varchar[]) AND timestamp BETWEEN $2 AND $3
                ORDER BY timestamp
                """,
                ids,
                start,
                end,
            ) if ids else []
            ticks = await conn.fetch(
                """
                SELECT slug, lower(outcome) AS outcome, source_ts AS time, price
                FROM market_ticks
                WHERE lower(slug) = ANY($1::text[]) AND source_ts BETWEEN $2 AND $3
                ORDER BY source_ts
                """,
                list(market_ids),
                start,
                end,
            ) if requested_slugs else []

        snapshot_series = _series(snapshots, lambda r: r["market_id"], lambda r, k: r[k])
        tick_series = _series(
            ticks, lambda r: (r["slug"].lower(), r["outcome"]), lambda r, k: r[k]
        )
        result = []
        for ticket in tickets:
            ticket_start = _time(ticket["opened_at"], now)
            ticket_end = _time(ticket["ended_at"], now)
            slug = market_slug(ticket["slug"])
            candidates: list[float] = []
            sources: list[str] = []
            sample_count = 0

            contracts = float(ticket.get("contracts") or 0.0)
            paid_percentage = (
                float(ticket["stake"]) / contracts * 100.0
                if contracts > 0
                else None
            )

            details: dict[str, Any] = {}
            if ticket.get("kind") == "combo":
                leg_results = []
                leg_series = []
                for leg in ticket_legs.get(ticket["bet_key"], []):
                    leg_slug = str(leg.get("slug") or "")
                    requested = market_slug(leg_slug)
                    actual_slug = resolved.get(requested)
                    info = market_info.get(actual_slug or "")
                    outcome = str(leg.get("outcome") or "").strip()
                    snapshot = snapshot_series.get(market_ids.get(actual_slug or ""))
                    snapshots_for_outcome = []
                    if snapshot and info and outcome:
                        for time, price in zip(*snapshot):
                            mapped = _outcome_snapshot_price(
                                price, info["outcomes_json"], outcome
                            )
                            if mapped is not None:
                                snapshots_for_outcome.append((time, mapped))
                    snapshot_leg_series = (
                        (
                            [time for time, _ in snapshots_for_outcome],
                            [price for _, price in snapshots_for_outcome],
                        )
                        if snapshots_for_outcome
                        else None
                    )
                    tick_leg_series = tick_series.get(
                        (actual_slug, outcome.casefold())
                    ) if actual_slug and outcome else None
                    if tick_leg_series:
                        normalized_ticks = (
                            tick_leg_series[0],
                            [value * 100.0 for value in tick_leg_series[1]],
                        )
                        series = normalized_ticks
                        source = "outcome ticks"
                    else:
                        series = snapshot_leg_series
                        source = "15-minute snapshots"
                    leg_series.append(series)
                    high_values = _range_values(series, ticket_start, ticket_end)
                    high = max(high_values) if high_values else None
                    entry = _asof(series, ticket_start)
                    leg_results.append({
                        "slug": leg_slug,
                        "market_slug": actual_slug,
                        "outcome": outcome,
                        "entry_percentage": round(entry, 2) if entry is not None else None,
                        "high_percentage": round(high, 2) if high is not None else None,
                        "change_percentage_points": (
                            round(high - entry, 2)
                            if high is not None and entry is not None
                            else None
                        ),
                        "change_percent": (
                            round(change, 2) if (change := _percentage_change(high, entry)) is not None else None
                        ),
                        "samples": len(high_values),
                        "source": source if series else None,
                    })
                    if high_values:
                        sample_count += len(high_values)

                synchronized = _combo_values(leg_series, ticket_start, ticket_end)
                peak = max(synchronized, key=lambda point: point[1], default=None)
                peak_time, combo_high = peak if peak is not None else (None, None)
                for index, leg_result in enumerate(leg_results):
                    at_peak = (
                        _asof(leg_series[index], peak_time)
                        if peak_time is not None
                        else None
                    )
                    leg_result["percentage_at_combo_high"] = (
                        round(at_peak, 2) if at_peak is not None else None
                    )
                    leg_result["change_to_combo_high_percent"] = (
                        round(change, 2)
                        if (change := _percentage_change(
                            at_peak, leg_result["entry_percentage"]
                        )) is not None
                        else None
                    )
                entry_prices = [
                    _asof(series, ticket_start) for series in leg_series
                ]
                valid_entry_prices = [
                    price for price in entry_prices if price is not None
                ]
                estimated_entry = (
                    math.prod(valid_entry_prices) / (100.0 ** (len(valid_entry_prices) - 1))
                    if valid_entry_prices and len(valid_entry_prices) == len(leg_series)
                    else None
                )
                candidates = [combo_high] if combo_high is not None else []
                sources = ["synchronized product of underlying outcome prices"] if candidates else []
                high_percentage = combo_high
                details = {
                    "legs": leg_results,
                    "estimated_entry_percentage": (
                        round(estimated_entry, 2) if estimated_entry is not None else None
                    ),
                    "high_percentage": round(combo_high, 2) if combo_high is not None else None,
                    "change_percentage_points": (
                        round(combo_high - estimated_entry, 2)
                        if combo_high is not None and estimated_entry is not None
                        else None
                    ),
                    "change_percent": (
                        round(change, 2)
                        if (change := _percentage_change(combo_high, estimated_entry)) is not None
                        else None
                    ),
                    "change_from_paid_percentage_points": (
                        round(combo_high - paid_percentage, 2)
                        if combo_high is not None and paid_percentage is not None
                        else None
                    ),
                    "change_from_paid_percent": (
                        round(change, 2)
                        if (change := _percentage_change(combo_high, paid_percentage)) is not None
                        else None
                    ),
                    "synchronized_samples": len(synchronized),
                    "high_observed_at": (
                        peak_time.isoformat() + "Z" if peak_time is not None else None
                    ),
                    "above_actual_cost": _above_cost(combo_high, paid_percentage),
                    "valuation_note": (
                        "Estimate: product of held-side leg prices at synchronized observations; "
                        "not an observed combo-ticket quote."
                    ),
                }
            else:
                matched_slug = resolved.get(slug)
                snapshot_values = _range_values(
                    snapshot_series.get(market_ids.get(matched_slug or "")),
                    ticket_start,
                    ticket_end,
                )
                snapshot_high = _side_high(snapshot_values, ticket["direction"])
                if snapshot_high is not None:
                    candidates.append(snapshot_high)
                    sources.append("15-minute snapshots")
                    sample_count += len(snapshot_values)

                outcome = (ticket.get("backed") or "").strip().casefold()
                tick_values = _range_values(
                    tick_series.get((matched_slug, outcome)) if outcome else None,
                    ticket_start,
                    ticket_end,
                )
                if tick_values:
                    tick_high = _side_high(
                        [value * 100.0 for value in tick_values], ticket["direction"]
                    )
                    if tick_high is not None:
                        candidates.append(tick_high)
                        sources.append("outcome ticks")
                        sample_count += len(tick_values)
                high_percentage = max(candidates) if candidates else None

            result.append({
                "slug": ticket["slug"],
                "kind": ticket["kind"],
                "title": ticket["title"],
                "backed": ticket["backed"],
                "direction": ticket["direction"],
                "opened_at": ticket["opened_at"],
                "ended_at": ticket["ended_at"],
                "paid_percentage": round(paid_percentage, 2) if paid_percentage is not None else None,
                "high_percentage": round(high_percentage, 2) if high_percentage is not None else None,
                "above_cost": _above_cost(high_percentage, paid_percentage),
                "samples": sample_count,
                "sources": sources,
                **details,
            })
        return result
    finally:
        await conn.close()


async def build_report(pg_host: str, pg_port: int) -> dict[str, Any]:
    activities, pages = await asyncio.to_thread(fetch_activities, _client())
    tickets = build_bets(activities)
    highs = await _read_prices(tickets, activities, pg_host, pg_port)
    measured = [t for t in highs if t["high_percentage"] is not None]
    above_cost = [t for t in measured if t["above_cost"]]
    return {
        "activity_pages": pages,
        "tickets": len(highs),
        "tickets_with_history": len(measured),
        "tickets_above_cost": len(above_cost),
        "tickets_without_history": len(highs) - len(measured),
        "median_high_above_cost_percentage": (
            round(median(t["high_percentage"] for t in above_cost), 2) if above_cost else None
        ),
        "definition": (
            "Among tickets with observed history, include a ticket only when its held-side "
            "high exceeded entry cost per contract including fees."
        ),
        "combo_definition": (
            "Combo values are estimates from the product of each selected outcome's market price "
            "at synchronized observations; they are not observed combo-ticket quotes. Per-leg "
            "entry values use the latest matched underlying price at or before ticket open."
        ),
        "sampling_note": (
            "15-minute market snapshots may miss intraperiod highs; outcome ticks are event-specific. "
            "Combo estimates require usable history for every leg."
        ),
        "ticket_highs": highs,
    }


def print_report(report: dict[str, Any]) -> None:
    median_high = report["median_high_above_cost_percentage"]
    median_label = f"{median_high:.2f}%" if median_high is not None else "N/A"
    print(
        f"Median high above cost: {median_label} "
        f"({report['tickets_above_cost']} qualifying / "
        f"{report['tickets_with_history']} with history; "
        f"{report['tickets']} tickets total)"
    )
    combos = [t for t in report["ticket_highs"] if t["kind"] == "combo"]
    measured = [t for t in combos if t["high_percentage"] is not None]
    qualifying = [t for t in measured if t["above_cost"]]
    median_combo_high = (
        median(t["high_percentage"] for t in qualifying) if qualifying else None
    )
    median_combo_return = [
        t["change_from_paid_percent"]
        for t in qualifying
        if t["change_from_paid_percent"] is not None
    ]
    print(
        f"Combo estimates: {len(qualifying)} above cost / {len(measured)} measurable "
        f"({len(combos)} combos total); median synchronized high "
        f"{f'{median_combo_high:.2f}%' if median_combo_high is not None else 'N/A'}; "
        f"median estimated change from paid cost "
        f"{f'{median(median_combo_return):+.2f}%' if median_combo_return else 'N/A'}"
    )
    for ticket in combos:
        opened = str(ticket["opened_at"])[:16]
        change = ticket["change_from_paid_percent"]
        change_label = f"{change:+.2f}%" if change is not None else "N/A"
        paid = ticket["paid_percentage"]
        high = ticket["high_percentage"]
        paid_label = f"{paid:.2f}%" if paid is not None else "N/A"
        high_label = f"{high:.2f}%" if high is not None else "N/A"
        status = "above cost" if ticket["above_cost"] else (
            "did not exceed cost" if ticket["above_cost"] is False else "not measurable"
        )
        print(
            f"  {ticket['slug']} ({opened}) paid {paid_label} -> "
            f"estimated combo high {high_label} ({change_label} from cost; {status})"
        )
        legs = ticket.get("legs", [])
        if not legs:
            print("    No matched leg details found in the opening activity.")
        for leg in legs:
            entry, high = leg["entry_percentage"], leg["high_percentage"]
            move = (
                f"individual high {entry:.2f}% -> {high:.2f}% "
                f"({leg['change_percent']:+.2f}%)"
                if entry is not None and high is not None and leg["change_percent"] is not None
                else "insufficient leg history"
            )
            at_peak = leg.get("percentage_at_combo_high")
            if at_peak is not None:
                peak_move = leg["change_to_combo_high_percent"]
                move += (
                    f"; at combo high {at_peak:.2f}%"
                    f" ({peak_move:+.2f}% from entry)"
                    if peak_move is not None
                    else f"; at combo high {at_peak:.2f}%"
                )
            print(f"    {leg['outcome']}: {move}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Median high percentage among tickets that exceeded cost.")
    parser.add_argument("--json", action="store_true", help="print full ticket-level results as JSON")
    parser.add_argument("--out", metavar="FILE", help="write the JSON report to a file")
    parser.add_argument("--pg-host", default=os.getenv("POLY_PG_HOST", "127.0.0.1"))
    parser.add_argument("--pg-port", type=int, default=int(os.getenv("POLY_PG_PORT", "5433")))
    args = parser.parse_args()

    report = await build_report(args.pg_host, args.pg_port)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
        print(f"Wrote {args.out}")
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

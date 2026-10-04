"""
Trader report: normalizes Polymarket US account activity into trading terms.

The user trades by buying dips and selling the bounce, so outcomes do not matter here;
this layer only answers "what did each fill cost, and what is the cash result". Pure
functions over the raw ``portfolio.activities()`` payload, no network or database.

Polymarket US quirks handled here:
- A market has one listed outcome. Buying the other team is a "short" of that outcome,
  and the ``price`` field then shows the listed outcome's price, not what was paid.
  Price paid is therefore taken from cost / quantity.
- ``cost`` includes the commission; subtracting the fee gives the net contract price.
- BUY_LONG / BUY_SHORT open a position, SELL_LONG / SELL_SHORT close one. A fill on the
  SELL side with BUY_SHORT intent is an entry, not an exit.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.backend.sports.registry import league_of

OPEN_INTENTS = {"ORDER_INTENT_BUY_LONG": "long", "ORDER_INTENT_BUY_SHORT": "short"}
CLOSE_INTENTS = {"ORDER_INTENT_SELL_LONG": "long", "ORDER_INTENT_SELL_SHORT": "short"}


def _value(amount: Optional[dict]) -> Optional[float]:
    if isinstance(amount, dict) and amount.get("value") not in (None, ""):
        return float(amount["value"])
    return None


def market_kind(slug: str) -> str:
    """Slug prefix tells the bet type: combo (caoc-), player prop (astatc-), else single."""
    if slug.startswith("caoc"):
        return "combo"
    if slug.startswith("astatc"):
        return "prop"
    return "single"


@dataclass
class Fill:
    time: str
    slug: str
    kind: str
    action: str  # "open" or "close"
    direction: str  # "long" or "short" (which side of the listed contract)
    qty: float
    cost: float  # cash moved, including fee
    fee: float
    order_id: str
    realized_pnl: Optional[float]
    title: str = ""
    backed: str = ""  # the team the position is on (the contract's held side)
    legs: int = 0  # combo leg count, 0 for single-market bets

    @property
    def paid_per_contract(self) -> float:
        return self.cost / self.qty

    @property
    def net_price(self) -> float:
        """Contract price excluding the commission."""
        return (self.cost - self.fee) / self.qty


def normalize_trade(trade: dict[str, Any]) -> Fill:
    execution = trade["aggressorExecution"]
    order = execution["order"]
    intent = order["intent"]
    if intent in OPEN_INTENTS:
        action, direction = "open", OPEN_INTENTS[intent]
    elif intent in CLOSE_INTENTS:
        action, direction = "close", CLOSE_INTENTS[intent]
    else:
        raise ValueError(f"unknown order intent: {intent}")
    qty = float(trade.get("qtyDecimal") or trade["qty"])
    meta = order.get("marketMetadata") or {}
    return Fill(
        time=trade["createTime"],
        slug=trade["marketSlug"],
        kind=market_kind(trade["marketSlug"]),
        action=action,
        direction=direction,
        qty=qty,
        cost=_value(trade.get("cost")) or 0.0,
        fee=_value(execution.get("commissionNotionalCollected")) or 0.0,
        order_id=order["id"],
        realized_pnl=_value(trade.get("realizedPnl")),
        title=meta.get("title") or "",
        backed=meta.get("outcome") or "",
        legs=len(trade.get("comboLegDetails") or []),
    )


def fills_from_activities(activities: list[dict]) -> list[Fill]:
    return sorted(
        (normalize_trade(a["trade"]) for a in activities if a["type"] == "ACTIVITY_TYPE_TRADE"),
        key=lambda f: f.time,
    )


def entry_orders(fills: list[Fill]) -> dict[str, dict[str, Any]]:
    """One row per entry order (split fills summed): size in dollars and bet type."""
    orders: dict[str, dict[str, Any]] = defaultdict(lambda: {"size": 0.0, "fees": 0.0, "kind": ""})
    for f in fills:
        if f.action == "open":
            orders[f.order_id]["size"] += f.cost
            orders[f.order_id]["fees"] += f.fee
            orders[f.order_id]["kind"] = f.kind
    return dict(orders)


def cash_summary(
    activities: list[dict], balance: float, open_positions_value: float = 0.0
) -> dict[str, float]:
    """Cash-flow P&L: the anchor figure, since it cannot miss fees.

    profit = withdrawals + balance + open positions - deposits - bonuses. Deposits that
    merely return earlier withdrawals cancel out inside this formula. ``balance`` is
    buying power, which for this account is bonus credit (not withdrawable cash), and
    open positions must be added because their cost has already left the balance.
    """
    kinds = {
        "ACTIVITY_TYPE_ACCOUNT_DEPOSIT": "deposits",
        "ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL": "withdrawals",
        "ACTIVITY_TYPE_REFERRAL_BONUS": "bonuses",
    }
    totals = {
        "deposits": 0.0, "withdrawals": 0.0, "bonuses": 0.0,
        "deposit_match_bonuses": 0.0, "referral_bonuses": 0.0,
    }
    for a in activities:
        key = kinds.get(a["type"])
        if not key:
            continue
        change = a["accountBalanceChange"]
        if change.get("status") == "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED":
            amount = float(change["amount"]["value"])
            totals[key] += amount
            if key == "bonuses":
                # Deposit matches come from re-depositing winnings; the rest are referral releases
                kind = (change.get("metadata") or {}).get("incentive_type") or change.get("description", "")
                split = "deposit_match_bonuses" if "PROMOTION_DEPOSIT_BONUS" in kind else "referral_bonuses"
                totals[split] += amount
    totals["balance"] = balance
    totals["open_positions_value"] = open_positions_value
    totals["net_cash_out"] = totals["withdrawals"] - totals["deposits"]
    # Everything gained, bonuses included: cash received plus what is still held
    totals["total_gain"] = totals["net_cash_out"] + balance + open_positions_value
    # What trading earned beyond the platform's free credit
    totals["profit_excluding_bonuses"] = totals["total_gain"] - totals["bonuses"]
    return totals


@dataclass
class Cycle:
    """One position's life on one side of one market: entries, then exits (if any).

    A cycle starts when the position goes from flat to open and ends when it returns to
    flat. A cycle with ``remaining_qty`` > 0 is still open, or ran to settlement.
    """

    slug: str
    kind: str
    direction: str
    opened_at: str
    closed_at: Optional[str]
    qty_opened: float
    entry_price: float  # weighted net price per contract, fee excluded
    entry_cost: float
    exit_price: Optional[float]  # weighted proceeds per contract on closes
    fees: float
    realized_pnl: Optional[float]  # sum of recorded P&L on closing fills, None if none recorded
    remaining_qty: float
    fills: int
    title: str = ""
    backed: str = ""
    legs: int = 0
    order_id: str = ""

    @property
    def league(self) -> str:
        return league_of(self.slug)


def build_cycles(fills: list[Fill]) -> list[Cycle]:
    """Group fills into position cycles per (market, direction), in time order."""
    by_key: dict[tuple[str, str], list[Fill]] = defaultdict(list)
    for f in fills:
        by_key[(f.slug, f.direction)].append(f)

    cycles: list[Cycle] = []
    for (slug, direction), group in by_key.items():
        group.sort(key=lambda f: f.time)
        cur: Optional[dict[str, Any]] = None
        held = 0.0

        def finish(c: dict[str, Any], closed_at: Optional[str]) -> None:
            qty_closed = c["qty_closed"]
            cycles.append(
                Cycle(
                    slug=slug, kind=market_kind(slug), direction=direction,
                    opened_at=c["opened_at"], closed_at=closed_at,
                    qty_opened=c["qty_opened"],
                    entry_price=c["entry_net"] / c["qty_opened"],
                    entry_cost=c["entry_cost"],
                    exit_price=(c["exit_cost"] / qty_closed) if qty_closed else None,
                    fees=c["fees"],
                    realized_pnl=c["pnl"] if c["has_pnl"] else None,
                    remaining_qty=max(c["qty_opened"] - qty_closed, 0.0),
                    fills=c["fills"],
                    title=c["title"], backed=c["backed"], legs=c["legs"], order_id=c["order_id"],
                )
            )

        for f in group:
            if f.action == "open":
                if cur is None:
                    cur = {"opened_at": f.time, "qty_opened": 0.0, "entry_net": 0.0,
                           "entry_cost": 0.0, "qty_closed": 0.0, "exit_cost": 0.0,
                           "fees": 0.0, "pnl": 0.0, "has_pnl": False, "fills": 0,
                           "title": f.title, "backed": f.backed, "legs": f.legs,
                           "order_id": f.order_id}
                    held = 0.0
                cur["qty_opened"] += f.qty
                cur["entry_net"] += f.cost - f.fee
                cur["entry_cost"] += f.cost
                held += f.qty
            else:
                if cur is None:
                    continue  # a close with no recorded entry; cannot attribute it
                cur["qty_closed"] += f.qty
                cur["exit_cost"] += f.cost
                held -= f.qty
                if f.realized_pnl is not None:
                    cur["pnl"] += f.realized_pnl
                    cur["has_pnl"] = True
            cur["fees"] += f.fee
            cur["fills"] += 1
            if held <= 1e-9:
                finish(cur, f.time)
                cur = None
        if cur is not None:
            finish(cur, None)

    return sorted(cycles, key=lambda c: c.opened_at)


def parse_time(ts: str) -> datetime:
    """Parse an API timestamp; fractional seconds can run to nanoseconds, so trim to micro."""
    ts = ts.rstrip("Z")
    if "." in ts:
        head, frac = ts.split(".", 1)
        ts = f"{head}.{frac[:6]}"
    return datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)


def concurrent_opens(cycles: list[Cycle], cycle: Cycle, window_minutes: float = 30.0) -> int:
    """How many other cycles were opened within the window either side: stacking or rolling."""
    center, span = parse_time(cycle.opened_at), timedelta(minutes=window_minutes)
    return sum(
        1 for other in cycles
        if other is not cycle and abs(parse_time(other.opened_at) - center) <= span
    )


def summarize_results(bets: list[dict[str, Any]]) -> dict[str, Any]:
    """Win rate, payoff and hold time over bets, from the bet rows built by ``build_bets``.

    Results come from cash in and out, not the platform's realized-P&L field. "sold" bets
    were closed before the game ended; "settled" ones were held to the end, and open ones
    have no result yet.
    """

    def group(items: list[dict[str, Any]]) -> dict[str, Any]:
        done = [b for b in items if b["pnl"] is not None]
        wins = [b["pnl"] for b in done if b["pnl"] > 0]
        losses = [b["pnl"] for b in done if b["pnl"] <= 0]
        entered = sum(b["stake"] for b in done)
        net = sum(b["pnl"] for b in done)
        return {
            "n": len(done),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(done) if done else None,
            "avg_win": sum(wins) / len(wins) if wins else None,
            "avg_loss": sum(losses) / len(losses) if losses else None,
            "best": max(wins) if wins else None,
            "worst": min(losses) if losses else None,
            "net": net,
            "entered": entered,
            "return_on_entered": net / entered if entered else None,
        }

    sold = [b for b in bets if b["how_ended"] == "sold"]
    settled = [b for b in bets if b["how_ended"] == "settled"]
    holds = sorted(b["hold_minutes"] for b in sold if b["hold_minutes"] is not None)
    return {
        "all": group(bets),
        "sold": group(sold),
        "settled": group(settled),
        "by_kind": {k: group([b for b in bets if b["kind"] == k]) for k in ("single", "combo", "prop")},
        "by_league": {
            lg: group([b for b in bets if b["league"] == lg])
            for lg in sorted({b["league"] for b in bets})
        },
        "by_legs": {
            str(n): group([b for b in bets if b["kind"] == "combo" and b.get("legs") == n])
            for n in sorted({b.get("legs") for b in bets if b["kind"] == "combo" and b.get("legs")})
        },
        "open": sum(1 for b in bets if b["how_ended"] == "open"),
        "hold_minutes_sold": {
            "median": holds[len(holds) // 2] if holds else None,
            "p25": holds[len(holds) // 4] if holds else None,
            "p75": holds[3 * len(holds) // 4] if holds else None,
        },
    }


def _ledger_events(activities: list[dict], fills: list[Fill]) -> list[tuple]:
    """Every money movement in time order: deposits, bonuses, withdrawals, fills, payouts."""
    events: list[tuple] = []
    for a in activities:
        kind = a["type"]
        if kind not in (
            "ACTIVITY_TYPE_ACCOUNT_DEPOSIT", "ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL", "ACTIVITY_TYPE_REFERRAL_BONUS"
        ):
            continue
        change = a["accountBalanceChange"]
        if change.get("status") != "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED":
            continue
        amount = float(change["amount"]["value"])
        created = change.get("createTime") or change.get("updateTime") or "1970-01-01T00:00:00Z"
        updated = change.get("updateTime") or created
        if kind.endswith("DEPOSIT"):
            events.append((created, 0, "deposit", amount))
        elif kind.endswith("WITHDRAWAL"):
            events.append((updated, 0, "withdrawal", amount))
        else:
            matched = (change.get("metadata") or {}).get("incentive_type") == "PROMOTION_DEPOSIT_BONUS"
            events.append((created, 0, "matched" if matched else "referral", amount))
    for f in fills:
        events.append((f.time, 1, f.action, f))
    for a in activities:
        if a["type"] != "ACTIVITY_TYPE_POSITION_RESOLUTION":
            continue
        r = a["positionResolution"]
        before = r["beforePosition"]
        net = float(before.get("netPositionDecimal") or before.get("netPosition") or 0)
        long_price = _long_price_at_settlement(r.get("market") or {})
        if long_price is None:
            continue
        held = long_price if net > 0 else 1.0 - long_price
        events.append((r["updateTime"], 2, "payout", (r["marketSlug"], "short" if net < 0 else "long", abs(net) * held)))
    return sorted(events, key=lambda e: (parse_time(e[0]), e[1]))


def fund_stakes(activities: list[dict], fills: list[Fill]) -> dict[int, dict[str, float]]:
    """Where each entry's money came from, by replaying the account's money in time order.

    Four pools: ``own`` (the first deposit, the only new money), ``win`` (recycled winnings
    and later deposits, real money), ``match`` (deposit-match bonus) and ``ref`` (referral
    credit). Rules, from the trader's own experience of the platform:
    - cash is spent before bonus credit;
    - a matched bonus becomes real money once it is bet;
    - a referral bonus stays locked, and profit made on referral-funded money inherits that lock.
    Replaying the feed with these rules ends at $0 cash and the exact locked-bonus balance the
    account shows. Returns, per opening fill (keyed by ``id(fill)``), the dollars drawn from each pool.
    """
    pools = {"own": 0.0, "win": 0.0, "match": 0.0, "ref": 0.0}
    positions: dict[tuple[str, str], dict[str, Any]] = {}
    funding: dict[int, dict[str, float]] = {}
    first_deposit = True

    for _, _, kind, x in _ledger_events(activities, fills):
        if kind == "deposit":
            if first_deposit:
                pools["own"] += x
                first_deposit = False
            else:
                pools["win"] += x  # later deposits were winnings put back in
        elif kind in ("matched", "referral"):
            pools["match" if kind == "matched" else "ref"] += x
        elif kind == "withdrawal":
            rest = x
            for pool in ("win", "own", "match"):
                took = min(pools[pool], rest)
                pools[pool] -= took
                rest -= took
            if rest > 1e-9:  # the platform let more out than real money; it came off the referral credit
                pools["ref"] -= rest
        elif kind == "open":
            fill: Fill = x
            need, drawn = fill.cost, {"own": 0.0, "win": 0.0, "match": 0.0, "ref": 0.0}
            for group in (("own", "win"), ("match",), ("ref",)):  # cash first, then bonus
                have = sum(pools[k] for k in group)
                use = min(have, need)
                for k in group:
                    part = use * pools[k] / have if have else 0.0
                    drawn[k] += part
                    pools[k] -= part
                need -= use
            funding[id(fill)] = drawn
            pos = positions.setdefault((fill.slug, fill.direction), {"qty": 0.0, "take": {}})
            pos["qty"] += fill.qty
            for k, v in drawn.items():
                pos["take"][k] = pos["take"].get(k, 0.0) + v
        else:  # close or payout: money comes back to the pools the stake came from
            if kind == "close":
                fill = x
                key, proceeds = (fill.slug, fill.direction), fill.cost
                pos = positions.get(key)
                frac = (fill.qty / pos["qty"]) if pos and pos["qty"] else 1.0
            else:
                key, proceeds = (x[0], x[1]), x[2]
                pos, frac = positions.get(key), 1.0
            total = sum(pos["take"].values()) if pos else 0.0
            if not pos or not total:
                pools["win"] += proceeds
                continue
            principal = total * frac
            returned = min(proceeds, principal)
            scale = returned / principal if principal else 0.0
            for k, v in pos["take"].items():
                pools["ref" if k == "ref" else "win" if k == "match" else k] += v * frac * scale
            profit = proceeds - returned
            if profit > 0:
                for k, v in pos["take"].items():
                    pools["ref" if k == "ref" else "win"] += profit * v / total
            for k in pos["take"]:
                pos["take"][k] -= pos["take"][k] * frac
            pos["qty"] -= pos["qty"] * frac
    return funding


def _long_price_at_settlement(market: dict[str, Any]) -> Optional[float]:
    """Final price of the contract's long side (0 to 1), from the resolved market."""
    import json

    prices = market.get("outcomePrices")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except ValueError:
            return None
    try:
        return float(prices[0])
    except (TypeError, ValueError, IndexError):
        return None


def build_bets(activities: list[dict]) -> list[dict[str, Any]]:
    """One row per bet: what was backed, what was paid, how it ended, and the result.

    A bet is a position cycle. It ends "sold" (closed before the game finished), "settled"
    (held to the end) or stays "open". The result is cash in minus cash out from the fills,
    plus the final payout for anything held to settlement. The platform's own P&L fields are
    not used because they disagree with the cash on short-side closes.

    Resolutions are matched by market and by the sign of the position that was resolved:
    the resolution's ``side`` is the winning side of the contract, not the holder's side.
    """
    resolutions: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for a in activities:
        if a["type"] == "ACTIVITY_TYPE_POSITION_RESOLUTION":
            r = a["positionResolution"]
            before = r["beforePosition"]
            net = float(before.get("netPositionDecimal") or before.get("netPosition") or 0)
            resolutions[(r["marketSlug"], "short" if net < 0 else "long")].append(r)

    fills = fills_from_activities(activities)
    funding = fund_stakes(activities, fills)
    by_slug_dir: dict[tuple[str, str], list[Fill]] = defaultdict(list)
    for f in fills:
        by_slug_dir[(f.slug, f.direction)].append(f)

    bets: list[dict[str, Any]] = []
    for c in build_cycles(fills):
        window = [
            f for f in by_slug_dir[(c.slug, c.direction)]
            if f.time >= c.opened_at and (c.closed_at is None or f.time <= c.closed_at)
        ]
        cost_in = sum(f.cost for f in window if f.action == "open")
        drawn = {k: sum(funding.get(id(f), {}).get(k, 0.0) for f in window if f.action == "open")
                 for k in ("own", "win", "match", "ref")}
        cash_out = sum(f.cost for f in window if f.action == "close")
        how, ended_at, exit_price, pnl = "open", None, None, None
        if c.closed_at:
            how, ended_at, exit_price = "sold", c.closed_at, c.exit_price
            pnl = cash_out - cost_in
        else:
            match = next(
                (r for r in resolutions.get((c.slug, c.direction), []) if r["updateTime"] >= c.opened_at),
                None,
            )
            if match:
                how, ended_at = "settled", match["updateTime"]
                long_price = _long_price_at_settlement(match.get("market") or {})
                if long_price is not None:
                    held = long_price if c.direction == "long" else 1.0 - long_price
                    pnl = cash_out + c.remaining_qty * held - cost_in
                else:  # no usable final price: fall back to the platform's realized change
                    after = _value((match.get("afterPosition") or {}).get("realized")) or 0.0
                    before_realized = _value(match["beforePosition"].get("realized")) or 0.0
                    pnl = cash_out + (after - before_realized)
        hold = None
        if ended_at:
            hold = (parse_time(ended_at) - parse_time(c.opened_at)).total_seconds() / 60
        bets.append({
            "opened_at": c.opened_at,
            "ended_at": ended_at,
            "league": "combo" if c.kind == "combo" else c.league,
            "kind": c.kind,
            "title": c.title or c.slug,
            "backed": c.backed,
            "legs": c.legs,
            "direction": c.direction,
            "contracts": c.qty_opened,
            "price_paid": c.entry_price,
            "stake": c.entry_cost,
            "multiplier": (c.qty_opened / c.entry_cost) if c.entry_cost else None,  # payout per $1 if it wins
            "own_cash": drawn["own"],  # new money from the trader's own pocket
            "real_cash": drawn["own"] + drawn["win"],  # all real money staked (own plus recycled winnings)
            "bonus_credit": drawn["match"] + drawn["ref"],  # staked from bonus credit
            "fees": c.fees,
            "how_ended": how,
            "exit_price": exit_price,
            "pnl": pnl,
            "return": (pnl / cost_in) if pnl is not None and cost_in else None,
            "hold_minutes": hold,
            "slug": c.slug,
            "bet_key": f"{c.slug}|{c.opened_at}",
        })
    return sorted(bets, key=lambda b: b["opened_at"], reverse=True)


def summarize_bets(bets: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    """Totals per value of ``key`` (e.g. league or kind): bets, stake, result, win rate."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for b in bets:
        groups[b[key] or "unknown"].append(b)
    out = {}
    for name, items in groups.items():
        done = [b for b in items if b["pnl"] is not None]
        wins = [b for b in done if b["pnl"] > 0]
        out[name] = {
            "bets": len(items),
            "stake": sum(b["stake"] for b in items),
            "pnl": sum(b["pnl"] for b in done),
            "decided": len(done),
            "win_rate": len(wins) / len(done) if done else None,
            "avg_price_paid": sum(b["price_paid"] for b in items) / len(items),
        }
    return out

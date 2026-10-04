import pytest

from src.backend.sports.trader import (
    cash_summary,
    entry_orders,
    fills_from_activities,
    market_kind,
    normalize_trade,
)


def trade(intent, side, cost, qty, fee, slug="aec-cfb-monst-idaho-2026-10-02", order="o1", pnl=None):
    t = {
        "createTime": "2026-10-03T02:57:07Z", "marketSlug": slug, "qty": str(int(qty)),
        "qtyDecimal": str(qty), "price": {"value": "0.705"}, "cost": {"value": str(cost)},
        "aggressorExecution": {
            "commissionNotionalCollected": {"value": str(fee)},
            "order": {"id": order, "side": side, "intent": intent},
        },
    }
    if pnl is not None:
        t["realizedPnl"] = {"value": str(pnl)}
    return t


def test_idaho_short_entry_price_is_cost_per_contract_not_listed_price():
    # Real shape: SELL side + BUY_SHORT intent is an entry; listed price 0.705 is Montana State
    f = normalize_trade(trade("ORDER_INTENT_BUY_SHORT", "ORDER_SIDE_SELL", 3.97, 12.84, 0.18))
    assert (f.action, f.direction) == ("open", "short")
    assert f.paid_per_contract == pytest.approx(0.309, abs=0.001)
    assert f.net_price == pytest.approx(0.295, abs=0.001)  # matches the position's avgPx


def test_intents_map_to_open_and_close():
    cases = {
        "ORDER_INTENT_BUY_LONG": ("open", "long"), "ORDER_INTENT_BUY_SHORT": ("open", "short"),
        "ORDER_INTENT_SELL_LONG": ("close", "long"), "ORDER_INTENT_SELL_SHORT": ("close", "short"),
    }
    for intent, expected in cases.items():
        f = normalize_trade(trade(intent, "ORDER_SIDE_BUY", 5, 10, 0))
        assert (f.action, f.direction) == expected
    with pytest.raises(ValueError):
        normalize_trade(trade("ORDER_INTENT_UNDEFINED", "ORDER_SIDE_BUY", 5, 10, 0))


def test_market_kind_from_slug_prefix():
    assert market_kind("caoc-abc") == "combo"
    assert market_kind("astatc-mlb-x-hr") == "prop"
    assert market_kind("aec-mlb-a-b-2026-10-03") == "single"


def test_entry_orders_sum_split_fills_and_skip_closes():
    acts = [{"type": "ACTIVITY_TYPE_TRADE", "trade": t} for t in (
        trade("ORDER_INTENT_BUY_SHORT", "ORDER_SIDE_SELL", 3.97, 12.84, 0.18, order="a"),
        trade("ORDER_INTENT_BUY_SHORT", "ORDER_SIDE_SELL", 1.03, 3.3, 0.04, order="a"),
        trade("ORDER_INTENT_SELL_LONG", "ORDER_SIDE_SELL", 9.0, 20, 0.1, order="b"),
    )]
    orders = entry_orders(fills_from_activities(acts))
    assert list(orders) == ["a"] and orders["a"]["size"] == pytest.approx(5.0)


def change(kind, amount, status="ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED", incentive=None):
    c = {"status": status, "amount": {"value": str(amount)}}
    if incentive:
        c["metadata"] = {"incentive_type": incentive}
    return {"type": kind, "accountBalanceChange": c}


def test_cash_summary_matches_real_account_figures():
    acts = [change("ACTIVITY_TYPE_ACCOUNT_DEPOSIT", 85), change("ACTIVITY_TYPE_REFERRAL_BONUS", 200),
            change("ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL", 297.48),
            change("ACTIVITY_TYPE_ACCOUNT_DEPOSIT", 999, status="ACCOUNT_BALANCE_CHANGE_STATUS_PENDING")]
    s = cash_summary(acts, balance=69.06)
    assert s["deposits"] == 85 and s["bonuses"] == 200 and s["withdrawals"] == 297.48
    assert s["profit_excluding_bonuses"] == pytest.approx(81.54)


def test_cash_summary_adds_open_positions_whose_cost_already_left_the_balance():
    acts = [change("ACTIVITY_TYPE_ACCOUNT_DEPOSIT", 85), change("ACTIVITY_TYPE_REFERRAL_BONUS", 200),
            change("ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL", 297.48)]
    s = cash_summary(acts, balance=69.06, open_positions_value=18.29)
    assert s["profit_excluding_bonuses"] == pytest.approx(99.83)
    assert s["net_cash_out"] == pytest.approx(212.48)
    assert s["total_gain"] == pytest.approx(299.83)


def test_cash_summary_splits_deposit_match_from_referral_bonuses():
    acts = [change("ACTIVITY_TYPE_REFERRAL_BONUS", 50),
            change("ACTIVITY_TYPE_REFERRAL_BONUS", 25, incentive="PROMOTION_DEPOSIT_BONUS"),
            change("ACTIVITY_TYPE_REFERRAL_BONUS", 25, incentive="PROMOTION_DEPOSIT_BONUS")]
    s = cash_summary(acts, balance=0)
    assert s["bonuses"] == 100
    assert s["deposit_match_bonuses"] == 50 and s["referral_bonuses"] == 50


from src.backend.sports.trader import Fill, build_cycles, concurrent_opens


def fill(time, action, qty, cost, fee=0.0, slug="aec-mlb-a-b", direction="long", pnl=None, order="o"):
    return Fill(time=time, slug=slug, kind=market_kind(slug), action=action, direction=direction,
                qty=qty, cost=cost, fee=fee, order_id=order, realized_pnl=pnl)


def test_cycle_entry_exit_prices_and_pnl():
    cycles = build_cycles([
        fill("2026-10-01T10:00:00Z", "open", 20, 3.2, fee=0.2),   # 15c net entry
        fill("2026-10-01T10:40:00Z", "close", 20, 6.0, fee=0.2, pnl=2.6),  # sold at 30c
    ])
    assert len(cycles) == 1
    c = cycles[0]
    assert c.entry_price == pytest.approx(0.15) and c.exit_price == pytest.approx(0.30)
    assert c.remaining_qty == 0 and c.closed_at == "2026-10-01T10:40:00Z"
    assert c.fees == pytest.approx(0.4) and c.realized_pnl == pytest.approx(2.6)


def test_partial_close_stays_open_and_split_entries_average():
    cycles = build_cycles([
        fill("2026-10-01T10:00:00Z", "open", 10, 1.0),
        fill("2026-10-01T10:05:00Z", "open", 10, 2.0),
        fill("2026-10-01T10:30:00Z", "close", 5, 1.5),
    ])
    c = cycles[0]
    assert c.entry_price == pytest.approx(0.15) and c.remaining_qty == pytest.approx(15)
    assert c.closed_at is None and c.realized_pnl is None


def test_new_cycle_after_flat_and_directions_are_separate():
    cycles = build_cycles([
        fill("2026-10-01T10:00:00Z", "open", 10, 1.0),
        fill("2026-10-01T10:10:00Z", "close", 10, 2.0),
        fill("2026-10-01T11:00:00Z", "open", 10, 1.0),
        fill("2026-10-01T11:00:00Z", "open", 10, 4.0, direction="short"),
    ])
    assert len(cycles) == 3
    assert sorted(c.direction for c in cycles) == ["long", "long", "short"]


def test_concurrent_opens_counts_stacking_within_window():
    cycles = build_cycles([
        fill("2026-10-01T10:00:00Z", "open", 10, 1.0, slug="aec-a"),
        fill("2026-10-01T10:10:00Z", "open", 10, 1.0, slug="aec-b"),
        fill("2026-10-01T15:00:00Z", "open", 10, 1.0, slug="aec-c"),
    ])
    assert concurrent_opens(cycles, cycles[0]) == 1
    assert concurrent_opens(cycles, cycles[2]) == 0


def test_parse_time_handles_nanoseconds_and_short_stamps():
    from src.backend.sports.trader import parse_time

    assert parse_time("2026-10-03T19:12:43.518455305Z") == parse_time("2026-10-03T19:12:43.518455Z")
    assert parse_time("2026-10-01T10:00:00Z").hour == 10


def test_summarize_results_from_cash_pnl():
    from src.backend.sports.trader import summarize_results

    bets = [
        {"how_ended": "sold", "kind": "single", "league": "mlb", "pnl": 3.0, "stake": 5.0, "hold_minutes": 30},
        {"how_ended": "sold", "kind": "single", "league": "mlb", "pnl": -1.5, "stake": 5.0, "hold_minutes": 20},
        {"how_ended": "settled", "kind": "combo", "league": "combo", "pnl": -5.0, "stake": 5.0, "hold_minutes": 300},
        {"how_ended": "open", "kind": "single", "league": "cfb", "pnl": None, "stake": 5.0, "hold_minutes": None},
    ]
    r = summarize_results(bets)
    assert r["sold"]["n"] == 2 and r["sold"]["win_rate"] == 0.5 and r["sold"]["net"] == pytest.approx(1.5)
    assert r["settled"]["n"] == 1 and r["settled"]["net"] == -5.0 and r["open"] == 1
    assert r["all"]["n"] == 3 and r["all"]["net"] == pytest.approx(-3.5)
    assert r["by_kind"]["combo"]["net"] == -5.0 and r["by_league"]["mlb"]["n"] == 2
    assert r["all"]["best"] == 3.0 and r["all"]["worst"] == -5.0
    combo_bets = [{"how_ended": "settled", "kind": "combo", "league": "combo", "legs": n, "pnl": p,
                   "stake": 5.0, "hold_minutes": 60} for n, p in ((3, 20.0), (3, -5.0), (4, -5.0))]
    legs = summarize_results(combo_bets)["by_legs"]
    assert legs["3"]["n"] == 2 and legs["3"]["win_rate"] == 0.5 and legs["4"]["wins"] == 0


def raw_trade(order, intent, side, cost, qty, fee, time, slug="aec-cfb-monst-idaho-2026-10-02",
              title="Montana State vs. Idaho", outcome="Vandals", pnl=None):
    t = {
        "createTime": time, "marketSlug": slug, "qty": str(int(qty)), "qtyDecimal": str(qty),
        "price": {"value": "0.705"}, "cost": {"value": str(cost)},
        "aggressorExecution": {
            "commissionNotionalCollected": {"value": str(fee)},
            "order": {"id": order, "side": side, "intent": intent,
                      "marketMetadata": {"title": title, "outcome": outcome}},
        },
    }
    if pnl is not None:
        t["realizedPnl"] = {"value": str(pnl)}
    return {"type": "ACTIVITY_TYPE_TRADE", "trade": t}


def test_build_bets_covers_sold_settled_and_open():
    from src.backend.sports.trader import build_bets, summarize_bets

    acts = [
        # sold: bought 20 Vandals for $6.20 incl. $0.20 fee, sold for $9.00 with $2.80 P&L
        raw_trade("a", "ORDER_INTENT_BUY_SHORT", "ORDER_SIDE_SELL", 6.2, 20, 0.2, "2026-10-03T02:57:00Z"),
        raw_trade("a2", "ORDER_INTENT_SELL_SHORT", "ORDER_SIDE_BUY", 9.0, 20, 0.0, "2026-10-03T03:20:00Z", pnl=2.8),
        # settled: held to the end, resolution carries the result
        raw_trade("b", "ORDER_INTENT_BUY_LONG", "ORDER_SIDE_BUY", 5.0, 16, 0.2, "2026-10-02T20:00:00Z",
                  slug="aec-mlb-a-b-2026-10-02", title="A vs. B", outcome="Aces"),
        {"type": "ACTIVITY_TYPE_POSITION_RESOLUTION", "positionResolution": {
            "marketSlug": "aec-mlb-a-b-2026-10-02", "side": "POSITION_RESOLUTION_SIDE_SHORT",  # winning side, not ours
            "updateTime": "2026-10-03T03:00:00Z", "market": {"outcomePrices": '["1","0"]'},
            "beforePosition": {"netPosition": "16", "realized": {"value": "0"}},
            "afterPosition": {"realized": {"value": "99"}}}},
        # open: never closed, no resolution
        raw_trade("c", "ORDER_INTENT_BUY_LONG", "ORDER_SIDE_BUY", 4.0, 10, 0.1, "2026-10-03T12:00:00Z",
                  slug="aec-nfl-x-y-2026-10-04", title="X vs. Y", outcome="Xs"),
    ]
    bets = {b["slug"]: b for b in build_bets(acts)}
    sold = bets["aec-cfb-monst-idaho-2026-10-02"]
    assert sold["how_ended"] == "sold" and sold["backed"] == "Vandals" and sold["league"] == "cfb"
    # cash result: 9.00 came back for 6.20 paid, regardless of the platform's own P&L field
    assert sold["price_paid"] == pytest.approx(0.30) and sold["pnl"] == pytest.approx(2.8)
    assert sold["hold_minutes"] == pytest.approx(23)
    assert sold["multiplier"] == pytest.approx(20 / 6.2)  # 20 contracts pay $20 against $6.20 staked
    settled = bets["aec-mlb-a-b-2026-10-02"]
    # long contract finished at 1, so 16 contracts pay $16 against $5.00 paid
    assert settled["how_ended"] == "settled" and settled["pnl"] == pytest.approx(11.0)
    assert bets["aec-nfl-x-y-2026-10-04"]["how_ended"] == "open" and bets["aec-nfl-x-y-2026-10-04"]["pnl"] is None
    assert [b["opened_at"][:10] for b in build_bets(acts)] == ["2026-10-03", "2026-10-03", "2026-10-02"]
    by_league = summarize_bets(list(bets.values()), "league")
    assert by_league["cfb"]["decided"] == 1 and by_league["nfl"]["decided"] == 0


def test_short_side_bet_won_on_cash_even_if_platform_pnl_says_loss():
    from src.backend.sports.trader import build_bets

    # Minnesota: 13.12 contracts for $5.00, closing fills bring back $10.01. The platform's
    # realizedPnl on those closes is negative, but the cash says the bet won.
    acts = [
        raw_trade("m1", "ORDER_INTENT_BUY_SHORT", "ORDER_SIDE_SELL", 4.9988, 13.12, 0.1, "2026-10-03T16:57:54Z",
                  slug="aec-cfb-mich-minnst-2026-10-03", title="Michigan vs. Minnesota", outcome="Golden Gophers"),
        raw_trade("m2", "ORDER_INTENT_SELL_SHORT", "ORDER_SIDE_BUY", 3.45075, 4.53, 0.0, "2026-10-03T19:12:43Z",
                  slug="aec-cfb-mich-minnst-2026-10-03", outcome="Golden Gophers", pnl=-1.04),
        raw_trade("m3", "ORDER_INTENT_SELL_SHORT", "ORDER_SIDE_BUY", 6.55725, 8.59, 0.0, "2026-10-03T19:12:43Z",
                  slug="aec-cfb-mich-minnst-2026-10-03", outcome="Golden Gophers", pnl=-1.95),
    ]
    bet = build_bets(acts)[0]
    assert bet["how_ended"] == "sold" and bet["pnl"] == pytest.approx(5.009, abs=0.01)


def test_fund_stakes_spends_cash_before_bonus_and_marks_own_money():
    from src.backend.sports.trader import build_bets

    acts = [
        {"type": "ACTIVITY_TYPE_ACCOUNT_DEPOSIT", "accountBalanceChange": {
            "status": "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED", "createTime": "2026-09-05T00:00:00Z",
            "updateTime": "2026-09-05T00:00:00Z", "amount": {"value": "10"}}},
        {"type": "ACTIVITY_TYPE_REFERRAL_BONUS", "accountBalanceChange": {
            "status": "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED", "createTime": "2026-09-05T00:00:01Z",
            "updateTime": "2026-09-05T00:00:01Z", "amount": {"value": "50"}, "metadata": {"incentive_type": "REFERRAL"}}},
        raw_trade("a", "ORDER_INTENT_BUY_LONG", "ORDER_SIDE_BUY", 25.0, 100, 0.0, "2026-09-06T10:00:00Z",
                  slug="aec-mlb-a-b-2026-09-06", outcome="Aces"),
    ]
    bet = build_bets(acts)[0]
    assert bet["own_cash"] == pytest.approx(10.0) and bet["real_cash"] == pytest.approx(10.0)
    assert bet["bonus_credit"] == pytest.approx(15.0)  # $25 stake: $10 cash first, $15 from bonus

from datetime import datetime, timedelta
from io import StringIO

import json
from contextlib import redirect_stdout

from scripts.ticket_highs import (
    _above_cost,
    _combo_values,
    _opening_legs,
    _outcome_snapshot_price,
    _percentage_change,
    print_report,
    _range_values,
    _resolve_market_slug,
    _side_high,
    market_slug,
)


def test_market_slug_removes_account_contract_prefix():
    assert market_slug("aec-nfl-kc-lv-2026-10-04") == "nfl-kc-lv-2026-10-04"
    assert market_slug("astatc-mlb-x-y-hr-player-gte1") == "mlb-x-y-hr-player-gte1"


def test_combo_leg_slug_matches_longest_underlying_market_slug():
    assert _resolve_market_slug(
        "asc-mlb-atl-lad-2026-10-04-pos-1pt5",
        ["mlb-atl-lad-2026-10-04", "mlb-atl-lad-2026-10-04-pos"],
    ) == "mlb-atl-lad-2026-10-04-pos"


def test_snapshot_price_uses_the_named_held_outcome():
    outcomes = json.dumps([{"name": "Atlanta", "price": 40}, {"name": "Los Angeles", "price": 60}])

    assert _outcome_snapshot_price(40, outcomes, "Atlanta") == 40
    assert _outcome_snapshot_price(40, outcomes, "Los Angeles") == 60
    assert _outcome_snapshot_price(40, outcomes, "Chicago") is None


def test_combo_legs_are_taken_from_the_ticket_opening_activity():
    leg = {"slug": "aec-mlb-atl-lad-2026-10-01", "outcome": "Atlanta"}
    activity = {
        "type": "ACTIVITY_TYPE_TRADE",
        "trade": {
            "marketSlug": "caoc-ticket",
            "createTime": "2026-10-01T12:00:00Z",
            "comboLegDetails": [leg],
            "aggressorExecution": {
                "order": {"intent": "ORDER_INTENT_BUY_LONG"},
            },
        },
    }
    ticket = {
        "bet_key": "caoc-ticket|2026-10-01T12:00:00Z",
        "slug": "caoc-ticket",
        "kind": "combo",
        "opened_at": "2026-10-01T12:00:00Z",
        "ended_at": None,
    }

    assert _opening_legs([activity], [ticket]) == {ticket["bet_key"]: [leg]}


def test_side_high_uses_the_best_yes_or_no_percentage():
    assert _side_high([20.0, 70.0, 40.0], "long") == 70.0
    assert _side_high([20.0, 70.0, 40.0], "short") == 80.0
    assert _side_high([], "long") is None


def test_only_highs_above_entry_cost_qualify():
    assert _above_cost(65.0, 60.0) is True
    assert _above_cost(60.0, 60.0) is False
    assert _above_cost(None, 60.0) is None


def test_percentage_change_uses_entry_value_as_the_denominator():
    assert _percentage_change(30.0, 20.0) == 50.0
    assert _percentage_change(30.0, 0.0) is None


def test_range_values_includes_only_observations_while_held():
    start = datetime(2026, 10, 1)
    series = ([start, start + timedelta(hours=1), start + timedelta(hours=2)], [10.0, 20.0, 30.0])

    assert _range_values(series, start + timedelta(minutes=30), start + timedelta(hours=1)) == [20.0]


def test_combo_high_uses_synchronized_leg_prices_not_separate_peaks():
    start = datetime(2026, 10, 1)
    first = ([start, start + timedelta(minutes=10)], [20.0, 80.0])
    second = ([start, start + timedelta(minutes=10)], [50.0, 10.0])

    values = _combo_values([first, second], start, start + timedelta(minutes=10))

    assert values == [(start, 10.0), (start + timedelta(minutes=10), 8.0)]
    assert max(value for _, value in values) == 10.0


def test_default_report_shows_legs_for_all_combos_not_only_qualifying_ones():
    report = {
        "median_high_above_cost_percentage": 50.0,
        "tickets_above_cost": 1,
        "tickets_with_history": 2,
        "tickets": 3,
        "ticket_highs": [
            {
                "kind": "combo",
                "slug": "combo-above-cost",
                "opened_at": "2026-10-01T12:00:00Z",
                "paid_percentage": 20.0,
                "high_percentage": 30.0,
                "above_cost": True,
                "change_from_paid_percent": 50.0,
                "legs": [{
                    "outcome": "Team A",
                    "entry_percentage": 40.0,
                    "high_percentage": 60.0,
                    "change_percent": 50.0,
                    "percentage_at_combo_high": 55.0,
                    "change_to_combo_high_percent": 37.5,
                }],
            },
            {
                "kind": "combo",
                "slug": "combo-below-cost",
                "opened_at": "2026-10-01T11:00:00Z",
                "paid_percentage": 10.0,
                "high_percentage": 8.0,
                "above_cost": False,
                "change_from_paid_percent": -20.0,
                "legs": [{
                    "outcome": "Team B",
                    "entry_percentage": 25.0,
                    "high_percentage": 35.0,
                    "change_percent": 40.0,
                    "percentage_at_combo_high": 20.0,
                    "change_to_combo_high_percent": -20.0,
                }],
            },
        ],
    }
    output = StringIO()

    with redirect_stdout(output):
        print_report(report)

    text = output.getvalue()
    assert "combo-above-cost" in text
    assert "combo-below-cost" in text
    assert "Team A" in text
    assert "Team B" in text

import asyncio

import pytest

from src.backend import bet_notes
from src.backend.bet_notes import merge_notes


def bet(key, pnl=1.0):
    return {"bet_key": key, "pnl": pnl, "stake": 5.0, "price_paid": 0.2}


def test_untagged_bets_count_as_analysis_and_vibe_is_applied():
    notes = {"a|t1": {"tag": "vibe", "note": "gut feel", "why_ended": "cut"}}
    merged = merge_notes([bet("a|t1"), bet("b|t2")], notes)
    assert merged[0]["tag"] == "vibe" and merged[0]["note"] == "gut feel" and merged[0]["why_ended"] == "cut"
    assert merged[1]["tag"] == "analysis" and merged[1]["note"] is None


def test_merge_does_not_mutate_the_cached_bets():
    original = [bet("a|t1")]
    merge_notes(original, {"a|t1": {"tag": "vibe"}})
    assert "tag" not in original[0]


def test_save_note_rejects_unknown_values():
    with pytest.raises(ValueError):
        asyncio.run(bet_notes.save_note("a|t", tag="luck"))
    with pytest.raises(ValueError):
        asyncio.run(bet_notes.save_note("a|t", why_ended="whim"))


def test_bet_rows_carry_a_stable_key():
    from src.backend.sports.trader import build_bets

    trade = {
        "createTime": "2026-10-02T20:00:00Z", "marketSlug": "aec-mlb-a-b-2026-10-02", "qty": "16", "qtyDecimal": "16",
        "price": {"value": "0.3"}, "cost": {"value": "5.0"},
        "aggressorExecution": {"commissionNotionalCollected": {"value": "0.2"},
                               "order": {"id": "a", "side": "ORDER_SIDE_BUY", "intent": "ORDER_INTENT_BUY_LONG"}},
    }
    b = build_bets([{"type": "ACTIVITY_TYPE_TRADE", "trade": trade}])[0]
    assert b["bet_key"] == "aec-mlb-a-b-2026-10-02|2026-10-02T20:00:00Z"

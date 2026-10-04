import pytest

from src.backend.account import build_summary


def raw_payload():
    return {
        "balances": {"balances": [{
            "currentBalance": 69.06, "buyingPower": 69.06, "displayedCash": 0,
            "displayedBonus": 69.06, "bonusHold": 77.40, "availableToWithdraw": 0,
            "pendingWithdrawals": [],
        }]},
        "positions": {"positions": {"caoc-abc": {
            "marketSlug": "caoc-abc", "netPosition": "102", "cost": {"value": "10.0"},
            "cashValue": {"value": "8.9475"}, "avgPx": {"value": "0.098"},
            "marketMetadata": {"title": "Combo", "outcome": "Yes"},
            "comboLegDetails": [{"title": "A vs. B", "outcome": "Over", "state": "COMBO_LEG_STATE_WON"}],
        }}},
        "activities": [
            {"type": "ACTIVITY_TYPE_ACCOUNT_DEPOSIT", "accountBalanceChange": {
                "status": "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED", "amount": {"value": "10"}}},
            {"type": "ACTIVITY_TYPE_ACCOUNT_WITHDRAWAL", "accountBalanceChange": {
                "status": "ACCOUNT_BALANCE_CHANGE_STATUS_COMPLETED", "amount": {"value": "30"}}},
        ],
    }


def test_balance_fields_and_withdraw_model():
    s = build_summary(raw_payload())["balance"]
    assert s["bonus_hold"] == 77.40 and s["available_to_withdraw"] == 0
    assert s["model_withdrawable"] == 0  # balance 69.06 is below the 77.40 hold
    raw = raw_payload()
    raw["balances"]["balances"][0]["currentBalance"] = 100.0
    assert build_summary(raw)["balance"]["model_withdrawable"] == pytest.approx(22.60)


def test_open_positions_are_summed_and_added_to_gain():
    s = build_summary(raw_payload())
    assert s["open_positions"]["count"] == 1 and s["open_positions"]["value"] == pytest.approx(8.9475)
    assert s["open_positions"]["items"][0]["legs"][0]["state"] == "WON"
    # withdrawals 30 + balance 69.06 + open 8.9475 - deposits 10
    assert s["cash_flows"]["total_gain"] == pytest.approx(98.0075)


def test_empty_activity_is_safe():
    raw = raw_payload(); raw["activities"] = []
    s = build_summary(raw)
    assert s["trading"]["all"]["n"] == 0 and s["trading"]["total_fills"] == 0

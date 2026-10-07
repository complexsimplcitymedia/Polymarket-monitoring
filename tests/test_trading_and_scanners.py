import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def test_opportunity_scan_persists_parlays_without_weather(monkeypatch):
    from src.backend.extras import opportunity_hunter

    parlay = {
        "edge_pct": 6.0,
        "parlay_id": "parlay_test",
        "category": "NFL",
        "title": "Team A vs Team B",
        "payout_multiplier": "2x",
        "legs_count": 2,
        "estimated_joint_prob": 0.5,
        "combined_implied_prob": 0.44,
        "recommendation": "BUY",
        "legs": [{"token_id": "token"}],
        "synthetic_cost_per_dollar": 0.25,
    }
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
    )
    session.commit = AsyncMock()
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)

    discover_parlays = AsyncMock(return_value=[parlay])
    monkeypatch.setattr(
        opportunity_hunter, "discover_parlay_candidates", discover_parlays
    )
    monkeypatch.setattr(
        opportunity_hunter, "async_session_factory", lambda: session_context
    )
    monkeypatch.setattr(opportunity_hunter.settings, "AUTO_TRADE_ENABLED", False)

    results = asyncio.run(opportunity_hunter.run_opportunity_scan())

    discover_parlays.assert_awaited_once()
    assert [item["category"] for item in results] == ["PARLAY"]
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def test_weather_tables_are_not_registered_in_metadata():
    from src.backend.models import Base

    assert "weather_history" not in Base.metadata.tables
    assert "weather_anomalies" not in Base.metadata.tables
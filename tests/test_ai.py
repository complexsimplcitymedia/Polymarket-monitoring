import pytest

from src.backend.ai import EmptyAnswer, extract_answer, format_context, format_snapshot


def snap(**kw):
    base = {"league": "cfb", "game_id": "1", "away_team": "Temple", "home_team": "South Florida", "away_score": 17, "home_score": 13,
            "detail": "0:51 - 4th", "possession": "South Florida", "away_price": 0.97, "home_price": 0.03, "home_win_prob": 0.01,
            "away_rush_carries": 36, "away_rush_yards": 182, "home_rush_carries": 34, "home_rush_yards": 113,
            "poly_score": "17-13", "ts_score": None, "ncaa_score": "17-13"}
    return {**base, **kw}


def test_snapshot_line_has_score_price_and_box():
    line = format_snapshot(snap())
    assert "Temple 17 @ South Florida 13" in line and "home 3%" in line
    assert "away rush 182y/36 carries" in line and "polymarket=17-13" in line and "thescore" not in line


def test_context_sections_only_when_there_is_data():
    text = format_context([snap()], [{"period": 4, "clock": "0:51", "text": "Pass complete for 21 yards", "yards": 21}],
                          [{"slug": "cfb-templ-sfl", "outcome": "South Florida", "from_price": 0.08, "to_price": 0.03, "window_ms": 2500}], [])
    assert "RECENT PLAYS" in text and "21 yds" in text and "PRICE JUMPS" in text and "8% -> 3% in 2500 ms" in text
    assert "ACTIVE ALERTS" not in text
    assert "No live games" in format_context([], [], [], [])


def test_answer_uses_reasoning_text_when_content_is_empty():
    assert extract_answer({"choices": [{"message": {"content": "  Hello "}}]}) == "Hello"
    assert extract_answer({"choices": [{"message": {"content": "", "reasoning_content": "thinking out loud"}}]}) == "thinking out loud"
    with pytest.raises(EmptyAnswer):
        extract_answer({"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})

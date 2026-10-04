import json

from src.backend.polymarket.outcomes import parse_outcomes
from src.backend.polymarket.schemas import MarketOut


def test_parses_names_and_percentages():
    out = parse_outcomes('["Florida", "Missouri"]', '["0.325", "0.675"]')
    assert out == [{"name": "Florida", "price": 32.5}, {"name": "Missouri", "price": 67.5}]


def test_bad_or_missing_data_gives_empty_list():
    assert parse_outcomes("", "") == []
    assert parse_outcomes('["A","B"]', '["0.5"]') == []  # mismatched lengths
    assert parse_outcomes('["A","B"]', '["x","0.5"]') == []
    assert parse_outcomes('["A","B"]', '["1.5","-0.5"]') == []
    assert parse_outcomes("not json", "[]") == []


def test_market_out_exposes_outcomes_but_not_the_raw_json():
    m = MarketOut(id="1", slug="s", title="Florida vs. Missouri", yes_percentage=32.5,
                  outcomes_json=json.dumps(parse_outcomes('["Florida","Missouri"]', '["0.325","0.675"]')))
    dumped = m.model_dump()
    assert dumped["outcomes"][1]["name"] == "Missouri" and "outcomes_json" not in dumped
    assert MarketOut(id="1", slug="s", title="t").outcomes == []

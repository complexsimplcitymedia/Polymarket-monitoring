"""Outcome names and prices for a market, kept together so a card can say which team is which."""

import json
from typing import Any


def parse_outcomes(outcomes: Any, prices: Any) -> list[dict[str, Any]]:
    """[{"name": "Florida", "price": 32.0}, ...] with price as a percentage (0-100).

    Polymarket sends both fields as JSON-encoded lists of strings. Missing, malformed or
    mismatched data gives an empty list so callers can fall back to a plain Yes/No display.
    """
    def decode(raw: Any) -> list[Any]:
        if isinstance(raw, list):
            return raw
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return value if isinstance(value, list) else []

    names, values = decode(outcomes), decode(prices)
    if not names or len(names) != len(values):
        return []
    parsed = []
    for name, value in zip(names, values):
        try:
            price = float(value)
        except (TypeError, ValueError):
            return []
        if not 0 <= price <= 1:
            return []
        parsed.append({"name": str(name), "price": round(price * 100, 2)})
    return parsed

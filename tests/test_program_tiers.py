import asyncio

import pytest

from src.backend.program_tiers import tier_key, validate


def test_key_combines_league_and_team():
    assert tier_key("cfb", "25") == "cfb:25"


def test_validate_accepts_one_to_five_and_clearing():
    for tier in (1, 3, 5, None):
        validate("cfb", tier)


@pytest.mark.parametrize("league,tier", [("cfb", 0), ("cfb", 6), ("cfb", -1), ("soccer", 3), ("hockey", None)])
def test_validate_rejects_bad_values(league, tier):
    with pytest.raises(ValueError):
        validate(league, tier)


def test_save_tier_rejects_before_touching_the_database():
    from src.backend.program_tiers import save_tier

    with pytest.raises(ValueError):
        asyncio.run(save_tier("cfb", "25", 9))

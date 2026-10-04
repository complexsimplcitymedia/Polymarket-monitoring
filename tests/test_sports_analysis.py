from types import SimpleNamespace

import pytest

from src.backend.sports.analysis import (
    accuracy,
    brier_score,
    compare_predictors,
    market_brier,
    log_loss,
)


def pick(model, game, p, outcome, price=None):
    return SimpleNamespace(
        predictor=model, game_id=game, question="home wins", probability=p,
        market_price=price, outcome=outcome,
    )


def test_perfect_and_worst_brier():
    assert brier_score([(1.0, 1), (0.0, 0)]) == 0
    assert brier_score([(0.0, 1), (1.0, 0)]) == 1


def test_coin_flip_log_loss():
    assert log_loss([(0.5, 1), (0.5, 0)]) == pytest.approx(0.6931, abs=1e-4)


def test_log_loss_clamps_certainty():
    assert log_loss([(0.0, 1)]) < 40  # finite, not inf


def test_accuracy_threshold():
    assert accuracy([(0.6, 1), (0.4, 0), (0.7, 0), (0.2, 1)]) == 0.5


def test_market_brier_compares_to_crowd():
    mine, crowd, n = market_brier([pick("me", "g1", 0.8, 1, price=0.5)])
    assert n == 1 and mine == pytest.approx(0.04) and crowd == pytest.approx(0.25)


def test_market_brier_skips_unpriced_and_unsettled():
    assert market_brier([pick("me", "g1", 0.6, 1), pick("me", "g2", 0.6, None, 0.4)]) == (None, None, 0)


def test_compare_uses_common_games_and_ranks_by_brier():
    picks = [
        pick("me", "g1", 0.9, 1), pick("me", "g2", 0.9, 0), pick("me", "g3", 0.9, 1),
        pick("qwen", "g1", 0.7, 1), pick("qwen", "g2", 0.3, 0),
    ]
    scores = compare_predictors(picks)
    assert [s.predictor for s in scores] == ["qwen", "me"]
    assert all(s.n == 2 for s in scores)  # g3 dropped: qwen never picked it


def test_unsettled_only_returns_nothing():
    assert compare_predictors([pick("m", "g1", 0.6, None)]) == []

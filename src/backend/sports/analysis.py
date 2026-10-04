"""Scoring and comparison of binary predictions.

Pure functions, no database access. A prediction is a (probability, outcome) pair
where probability is P(yes) and outcome is 1 or 0.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol

_EPS = 1e-15


class Scorable(Protocol):
    predictor: str
    game_id: str
    question: str
    probability: float
    market_price: Optional[float]
    outcome: Optional[int]


@dataclass
class PredictorScore:
    predictor: str
    n: int
    accuracy: float
    brier: float
    log_loss: float
    market_brier: Optional[float] = None  # market's Brier on the same priced picks
    predictor_brier_priced: Optional[float] = None
    n_priced: int = 0
    calibration: list[dict] = field(default_factory=list)


def brier_score(pairs: list[tuple[float, int]]) -> float:
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def log_loss(pairs: list[tuple[float, int]]) -> float:
    total = 0.0
    for p, y in pairs:
        p = min(max(p, _EPS), 1 - _EPS)
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(pairs)


def accuracy(pairs: list[tuple[float, int]]) -> float:
    return sum((p >= 0.5) == bool(y) for p, y in pairs) / len(pairs)


def calibration_bins(pairs: list[tuple[float, int]], bins: int = 10) -> list[dict]:
    """Bucket picks by predicted probability; compare mean prediction to hit rate."""
    buckets: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for p, y in pairs:
        buckets[min(int(p * bins), bins - 1)].append((p, y))
    return [
        {
            "range": (i / bins, (i + 1) / bins),
            "n": len(rows),
            "mean_predicted": sum(p for p, _ in rows) / len(rows),
            "observed_rate": sum(y for _, y in rows) / len(rows),
        }
        for i, rows in sorted(buckets.items())
    ]


def market_brier(picks: Iterable[Scorable]) -> tuple[Optional[float], Optional[float], int]:
    """Brier of the predictor vs the market on picks that carry a market price.

    Returns (predictor_brier, market_brier, n). Predictor below market means the
    predictor beat the crowd on those games.
    """
    mine: list[tuple[float, int]] = []
    crowd: list[tuple[float, int]] = []
    for p in picks:
        if p.outcome is None or p.market_price is None or not 0 < p.market_price < 1:
            continue
        mine.append((p.probability, p.outcome))
        crowd.append((p.market_price, p.outcome))
    if not mine:
        return None, None, 0
    return brier_score(mine), brier_score(crowd), len(mine)


def score_predictor(predictor: str, picks: list[Scorable], bins: int = 10) -> Optional[PredictorScore]:
    settled = [p for p in picks if p.outcome is not None]
    if not settled:
        return None
    pairs = [(p.probability, p.outcome) for p in settled]
    mine_priced, crowd, n_priced = market_brier(settled)
    return PredictorScore(
        predictor=predictor,
        n=len(pairs),
        accuracy=accuracy(pairs),
        brier=brier_score(pairs),
        log_loss=log_loss(pairs),
        market_brier=crowd,
        predictor_brier_priced=mine_priced,
        n_priced=n_priced,
        calibration=calibration_bins(pairs, bins),
    )


def compare_predictors(picks: Iterable[Scorable], common_only: bool = True) -> list[PredictorScore]:
    """Score every predictor, best (lowest Brier) first.

    With ``common_only`` each predictor is scored only on the (game, question) pairs that
    every predictor has settled, so predictors that skip hard games are not flattered.
    """
    by_predictor: dict[str, list[Scorable]] = defaultdict(list)
    for p in picks:
        if p.outcome is not None:
            by_predictor[p.predictor].append(p)
    if common_only and len(by_predictor) > 1:
        keysets = [{(p.game_id, p.question) for p in rows} for rows in by_predictor.values()]
        common = set.intersection(*keysets)
        by_predictor = {
            m: [p for p in rows if (p.game_id, p.question) in common]
            for m, rows in by_predictor.items()
        }
    scores = [s for m, rows in by_predictor.items() if (s := score_predictor(m, rows))]
    return sorted(scores, key=lambda s: s.brier)

"""Kelly criterion position sizing for parlay bets."""

import math

from src.parlay_rules.models import SizingResult


def kelly_fraction(win_prob: float, payout_mult: float) -> float:
    """
    Full Kelly fraction: f* = (bp - q) / b
    where b = net payout (mult - 1), p = win prob, q = 1 - p.
    """
    if payout_mult <= 1.0 or win_prob <= 0 or win_prob >= 1.0:
        return 0.0
    b = payout_mult - 1.0
    p = win_prob
    q = 1.0 - p
    f = (b * p - q) / b
    return max(0.0, f)


def compute_sizing(
    joint_prob: float,
    payout_multiplier: float,
    bankroll: float = 100.0,
    kelly_scale: float = 0.5,
    max_fraction: float = 0.10,
) -> SizingResult:
    """
    Compute position size using fractional Kelly criterion.

    Args:
        joint_prob: Estimated true joint probability of the parlay.
        payout_multiplier: Gross payout per $1 wagered (e.g. 4.0 = 4x).
        bankroll: Total available bankroll in USD.
        kelly_scale: Fraction of Kelly to use (0.5 = half-Kelly, the safe default).
        max_fraction: Hard cap on bankroll fraction per bet.
    """
    full_k = kelly_fraction(joint_prob, payout_multiplier)
    half_k = full_k * kelly_scale
    capped = min(half_k, max_fraction)
    stake = round(bankroll * capped, 2)

    ev = joint_prob * payout_multiplier * stake - stake
    ror = 0.0
    if capped > 0 and joint_prob < 1.0:
        log_loss = math.log(1.0 - capped) if capped < 1.0 else -50.0
        n_for_ruin = -math.log(bankroll) / abs(log_loss) if log_loss != 0 else float("inf")
        ror = min(100.0, max(0.0, (1.0 - joint_prob) ** max(1, int(n_for_ruin)) * 100))

    return SizingResult(
        kelly_fraction=round(full_k, 4),
        half_kelly_fraction=round(half_k, 4),
        recommended_stake=stake,
        max_loss=stake,
        expected_profit=round(ev, 2),
        risk_of_ruin_pct=round(ror, 2),
    )

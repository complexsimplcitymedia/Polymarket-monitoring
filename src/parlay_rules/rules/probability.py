"""Probability and expected-value rules."""

import math

from src.parlay_rules.models import ParlayCandidate, RuleResult
from src.parlay_rules.rules.base import Rule


class MinLegProbabilityRule(Rule):
    """Reject parlays containing legs below a minimum implied probability."""

    def __init__(self, min_prob: float = 0.05):
        self._min = min_prob

    @property
    def name(self) -> str:
        return "min_leg_probability"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        violations = [
            leg.title for leg in candidate.legs if leg.implied_prob < self._min
        ]
        if violations:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=0.0,
                reason=f"{len(violations)} leg(s) below {self._min*100:.0f}% floor",
                details={"violations": violations},
            )
        min_price = min(leg.implied_prob for leg in candidate.legs)
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=min(100.0, (min_price / self._min) * 50),
            reason=f"All legs above {self._min*100:.0f}% floor (min={min_price*100:.1f}%)",
        )


class MaxLegProbabilityRule(Rule):
    """Flag parlays where every leg is >95% — negligible payout."""

    def __init__(self, max_prob: float = 0.95):
        self._max = max_prob

    @property
    def name(self) -> str:
        return "max_leg_probability"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        all_above = all(leg.implied_prob > self._max for leg in candidate.legs)
        if all_above:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=10.0,
                reason=f"All legs above {self._max*100:.0f}% — negligible multiplier",
            )
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=80.0,
            reason="Payout mix has meaningful multiplier potential",
        )


class EVThresholdRule(Rule):
    """
    Reject parlays whose expected value is below threshold.

    EV% = (joint_prob * payout_multiplier - 1) * 100
    A positive EV means the true probability of all legs hitting, times the
    payout, exceeds the cost.
    """

    def __init__(self, min_ev_pct: float = 25.0, correlation_boost: float = 1.35):
        self._min_ev = min_ev_pct
        self._corr_boost = correlation_boost

    @property
    def name(self) -> str:
        return "ev_threshold"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        indep = candidate.independent_prob
        joint_est = min(0.95, indep * self._corr_boost) if candidate.correlations else indep
        payout = candidate.payout_multiplier
        ev_pct = (joint_est * payout - 1.0) * 100.0

        passed = ev_pct >= self._min_ev
        score = min(100.0, max(0.0, ev_pct / self._min_ev * 50)) if self._min_ev > 0 else 50.0

        return RuleResult(
            rule_name=self.name,
            passed=passed,
            score=score,
            reason=f"EV={ev_pct:+.1f}% (threshold={self._min_ev}%)",
            details={
                "ev_pct": round(ev_pct, 2),
                "joint_prob_estimate": round(joint_est, 4),
                "independent_prob": round(indep, 4),
                "payout_multiplier": round(payout, 2),
            },
        )


class JointProbabilityFloorRule(Rule):
    """
    Reject parlays where the joint probability is astronomically low.
    A 5-leg parlay of 50% events = 3.1% joint — usually not worth the risk.
    """

    def __init__(self, min_joint_prob: float = 0.02):
        self._floor = min_joint_prob

    @property
    def name(self) -> str:
        return "joint_probability_floor"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        jp = candidate.independent_prob
        if jp < self._floor:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=max(0.0, jp / self._floor * 50),
                reason=f"Joint prob {jp*100:.2f}% below {self._floor*100:.1f}% floor",
                details={"joint_prob": round(jp, 4)},
            )
        score = min(100.0, math.log10(jp / self._floor + 1) * 60)
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=score,
            reason=f"Joint prob {jp*100:.2f}% above floor",
        )

"""Combo structure rules — anchor-multiplier strategy validation."""

from src.parlay_rules.models import LegRole, ParlayCandidate, RuleResult
from src.parlay_rules.rules.base import Rule


class AnchorMultiplierRule(Rule):
    """
    Validate the anchor-multiplier combo strategy.

    The user's approach: stack 2+ high-probability anchors (>=85%) as the
    "sure things" with one or more underdog multipliers (<=40%) for payout
    leverage. The anchors carry the combo; the multiplier gives the edge.

    Passing criteria:
    - At least 1 anchor (>=85%)
    - At least 1 multiplier (<=40%) OR at least 1 neutral (40-85%)
    - Combined anchor probability >= 70% (product of anchor legs)
    """

    def __init__(
        self,
        min_anchors: int = 1,
        min_anchor_combined_prob: float = 0.70,
    ):
        self._min_anchors = min_anchors
        self._min_anchor_prob = min_anchor_combined_prob

    @property
    def name(self) -> str:
        return "anchor_multiplier_structure"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        anchors = candidate.anchors
        multipliers = candidate.multipliers
        neutrals = [leg for leg in candidate.legs if leg.role == LegRole.NEUTRAL]

        if len(anchors) < self._min_anchors:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=20.0,
                reason=f"Need {self._min_anchors}+ anchor legs (>=85%), found {len(anchors)}",
                details={
                    "anchors": len(anchors),
                    "multipliers": len(multipliers),
                    "neutrals": len(neutrals),
                },
            )

        if not multipliers and not neutrals:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=30.0,
                reason="All legs are anchors — no multiplier for payout leverage",
            )

        anchor_prob = 1.0
        for a in anchors:
            anchor_prob *= a.implied_prob

        if anchor_prob < self._min_anchor_prob:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=40.0,
                reason=(
                    f"Combined anchor probability {anchor_prob*100:.1f}% "
                    f"below {self._min_anchor_prob*100:.0f}% floor"
                ),
            )

        mult_odds = [f"{m.title} @ {m.price*100:.0f}%" for m in multipliers]
        score = min(100.0, anchor_prob * 100 + len(multipliers) * 10)

        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=score,
            reason=(
                f"{len(anchors)} anchor(s) ({anchor_prob*100:.1f}% combined) + "
                f"{len(multipliers)} multiplier(s)"
            ),
            details={
                "anchor_combined_prob": round(anchor_prob, 4),
                "multiplier_legs": mult_odds,
                "payout_multiplier": round(candidate.payout_multiplier, 2),
            },
        )


class MaxLegsRule(Rule):
    """Cap the number of legs to keep the joint probability realistic."""

    def __init__(self, max_legs: int = 6):
        self._max = max_legs

    @property
    def name(self) -> str:
        return "max_legs"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        n = len(candidate.legs)
        if n > self._max:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=10.0,
                reason=f"{n} legs exceeds {self._max}-leg cap",
            )
        if n < 2:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=0.0,
                reason="Parlay requires at least 2 legs",
            )
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=90.0,
            reason=f"{n} legs within limit",
        )


class LegDiversityRule(Rule):
    """
    Prefer parlays where legs aren't all the same market type.
    Stacking three weather bets in the same city is just one bet with extra steps.
    """

    @property
    def name(self) -> str:
        return "leg_diversity"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        ids = [leg.market_id for leg in candidate.legs]
        unique = len(set(ids))
        if unique < len(ids):
            dupes = len(ids) - unique
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=20.0,
                reason=f"{dupes} duplicate market(s) — not a true parlay",
            )
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=90.0,
            reason=f"All {unique} legs target distinct markets",
        )

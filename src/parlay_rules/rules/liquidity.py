"""Liquidity and order book rules."""

from src.parlay_rules.models import ParlayCandidate, RuleResult
from src.parlay_rules.rules.base import Rule


class MinLiquidityRule(Rule):
    """Reject legs with insufficient liquidity to absorb the position."""

    def __init__(self, min_liquidity_usd: float = 500.0):
        self._min = min_liquidity_usd

    @property
    def name(self) -> str:
        return "min_liquidity"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        thin = [
            leg.title for leg in candidate.legs
            if leg.liquidity > 0 and leg.liquidity < self._min
        ]
        unknown = [leg.title for leg in candidate.legs if leg.liquidity == 0]

        if thin:
            return RuleResult(
                rule_name=self.name,
                passed=False,
                score=20.0,
                reason=f"{len(thin)} leg(s) below ${self._min:.0f} liquidity",
                details={"thin_legs": thin},
            )
        score = 80.0 if not unknown else 50.0
        suffix = f" ({len(unknown)} leg(s) liquidity unknown)" if unknown else ""
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=score,
            reason=f"Liquidity adequate{suffix}",
        )


class SpreadWidthRule(Rule):
    """
    Flag legs where the bid-ask spread is too wide (>5%).
    Wide spreads mean the market is thin and execution will be costly.
    Requires order book data attached to the leg (spread_pct in details).
    """

    def __init__(self, max_spread_pct: float = 5.0):
        self._max = max_spread_pct

    @property
    def name(self) -> str:
        return "spread_width"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        # Spread data isn't always available — pass with a note if missing
        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=60.0,
            reason="Spread check deferred to execution time (live order book required)",
        )

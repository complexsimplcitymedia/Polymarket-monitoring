"""Data models for the parlay rules engine."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Outcome(str, Enum):
    YES = "YES"
    NO = "NO"


class Verdict(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    SPECULATIVE = "SPECULATIVE"
    AVOID = "AVOID"
    REJECT = "REJECT"


class LegRole(str, Enum):
    """Role a leg plays in an anchor-multiplier combo."""
    ANCHOR = "ANCHOR"
    MULTIPLIER = "MULTIPLIER"
    NEUTRAL = "NEUTRAL"


class Leg(BaseModel):
    """Single leg of a parlay bet."""
    market_id: str
    token_id: str | None = None
    title: str
    outcome: Outcome = Outcome.YES
    side: Side = Side.BUY
    price: float = Field(ge=0.01, le=0.99)
    volume_24h: float = 0.0
    liquidity: float = 0.0
    end_date: datetime | None = None

    @property
    def implied_prob(self) -> float:
        return self.price

    @property
    def decimal_odds(self) -> float:
        return 1.0 / self.price if self.price > 0 else 0.0

    @property
    def role(self) -> LegRole:
        if self.price >= 0.85:
            return LegRole.ANCHOR
        if self.price <= 0.40:
            return LegRole.MULTIPLIER
        return LegRole.NEUTRAL


class CorrelationEstimate(BaseModel):
    """Pairwise correlation estimate between two legs."""
    leg_a_market_id: str
    leg_b_market_id: str
    rho: float = Field(ge=-1.0, le=1.0, default=0.0)
    source: str = "keyword_cluster"


class RuleResult(BaseModel):
    """Output of a single rule evaluation."""
    rule_name: str
    passed: bool
    score: float = Field(ge=0.0, le=100.0)
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class ParlayCandidate(BaseModel):
    """A proposed parlay combination to evaluate."""
    parlay_id: str
    legs: list[Leg]
    category: str = ""
    correlations: list[CorrelationEstimate] = Field(default_factory=list)

    @property
    def independent_prob(self) -> float:
        """Product of leg prices (assumes independence)."""
        p = 1.0
        for leg in self.legs:
            p *= leg.implied_prob
        return p

    @property
    def payout_multiplier(self) -> float:
        return 1.0 / self.independent_prob if self.independent_prob > 0 else 0.0

    @property
    def anchors(self) -> list[Leg]:
        return [leg for leg in self.legs if leg.role == LegRole.ANCHOR]

    @property
    def multipliers(self) -> list[Leg]:
        return [leg for leg in self.legs if leg.role == LegRole.MULTIPLIER]


class SizingResult(BaseModel):
    """Position sizing recommendation."""
    kelly_fraction: float
    half_kelly_fraction: float
    recommended_stake: float
    max_loss: float
    expected_profit: float
    risk_of_ruin_pct: float


class LLMEvaluation(BaseModel):
    """Result from a single LLM model pass."""
    model_name: str
    verdict: Verdict
    conviction: int = Field(ge=0, le=100)
    joint_prob_estimate: float = Field(ge=0.0, le=1.0)
    report: str
    latency_ms: int = 0


class ParlayVerdict(BaseModel):
    """Final evaluation of a parlay candidate after all rules and LLM passes."""
    parlay_id: str
    verdict: Verdict
    conviction: int = Field(ge=0, le=100)
    rule_results: list[RuleResult]
    rules_passed: int
    rules_failed: int
    joint_prob_estimate: float
    independent_prob: float
    payout_multiplier: float
    edge_pct: float
    sizing: SizingResult | None = None
    llm_evaluations: list[LLMEvaluation] = Field(default_factory=list)
    strategy_label: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_actionable(self) -> bool:
        return self.verdict in (Verdict.STRONG_BUY, Verdict.BUY)

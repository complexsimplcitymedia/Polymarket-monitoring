"""Pre-built strategy templates for common parlay patterns."""

from src.parlay_rules.rules import (
    AnchorMultiplierRule,
    CorrelationAdjustmentRule,
    DecouplingRiskRule,
    EVThresholdRule,
    JointProbabilityFloorRule,
    LegDiversityRule,
    MaxLegProbabilityRule,
    MaxLegsRule,
    MinLegProbabilityRule,
    MinLiquidityRule,
    Rule,
    SpreadWidthRule,
)


def anchor_multiplier_rules(
    min_ev_pct: float = 25.0,
    min_liquidity: float = 500.0,
    max_legs: int = 5,
) -> list[Rule]:
    """
    The user's primary strategy: stack high-probability anchors (>=85%)
    with one or more underdog multipliers (<=40%) for leveraged payout.

    Typical combo: 2 anchors at 97% + 1 multiplier at 30% = 2.82x * ~95% anchor
    probability * 30% multiplier = ~28% joint, paying 3.5x on a ~$5 stake.
    """
    return [
        MaxLegsRule(max_legs=max_legs),
        LegDiversityRule(),
        MinLegProbabilityRule(min_prob=0.03),
        MaxLegProbabilityRule(max_prob=0.99),
        AnchorMultiplierRule(min_anchors=1, min_anchor_combined_prob=0.70),
        JointProbabilityFloorRule(min_joint_prob=0.01),
        EVThresholdRule(min_ev_pct=min_ev_pct),
        MinLiquidityRule(min_liquidity_usd=min_liquidity),
        CorrelationAdjustmentRule(),
        DecouplingRiskRule(),
    ]


def conservative_rules() -> list[Rule]:
    """
    Conservative strategy: higher anchor floor, lower max legs, stricter EV.
    For weather-style bets where the model has a strong edge.
    """
    return [
        MaxLegsRule(max_legs=3),
        LegDiversityRule(),
        MinLegProbabilityRule(min_prob=0.05),
        MaxLegProbabilityRule(max_prob=0.95),
        AnchorMultiplierRule(min_anchors=1, min_anchor_combined_prob=0.80),
        JointProbabilityFloorRule(min_joint_prob=0.03),
        EVThresholdRule(min_ev_pct=40.0),
        MinLiquidityRule(min_liquidity_usd=1000.0),
        CorrelationAdjustmentRule(),
    ]


def aggressive_rules() -> list[Rule]:
    """
    Aggressive strategy: lower floors, more legs allowed, lower EV bar.
    For fast-moving sports markets where information advantage is high.
    """
    return [
        MaxLegsRule(max_legs=6),
        LegDiversityRule(),
        MinLegProbabilityRule(min_prob=0.02),
        AnchorMultiplierRule(min_anchors=1, min_anchor_combined_prob=0.50),
        JointProbabilityFloorRule(min_joint_prob=0.005),
        EVThresholdRule(min_ev_pct=10.0, correlation_boost=1.50),
        MinLiquidityRule(min_liquidity_usd=200.0),
        SpreadWidthRule(max_spread_pct=8.0),
        CorrelationAdjustmentRule(positive_boost=1.50),
        DecouplingRiskRule(),
    ]

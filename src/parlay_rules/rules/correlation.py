"""Correlation and decoupling risk rules."""

from src.parlay_rules.models import ParlayCandidate, RuleResult
from src.parlay_rules.rules.base import Rule

THEMATIC_KEYWORDS: dict[str, list[str]] = {
    "macro_fed": ["fed", "interest rate", "rate cut", "inflation", "cpi", "recession", "gdp"],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "solana", "crypto", "etf"],
    "us_politics": [
        "trump", "biden", "harris", "election", "senate", "house", "cabinet", "veto",
    ],
    "tech_ai": ["openai", "gemini", "anthropic", "nvidia", "apple", "spacex", "starship", "ai"],
    "sports_mlb": ["mlb", "yankees", "dodgers", "mets", "braves", "orioles", "padres", "astros"],
    "sports_nfl": ["nfl", "chiefs", "eagles", "ravens", "lions", "49ers", "cowboys"],
    "sports_tennis": ["atp", "wta", "tennis", "djokovic", "alcaraz", "sinner", "swiatek"],
    "weather": ["temperature", "weather", "degrees", "fahrenheit", "high temp"],
}


def _detect_cluster(title: str) -> str | None:
    lower = title.lower()
    for cluster, kws in THEMATIC_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return cluster
    return None


class CorrelationAdjustmentRule(Rule):
    """
    Detect thematic correlation between legs and adjust joint probability.

    Positively correlated legs (same macro cluster) have a higher true joint
    probability than independence assumes, which means the market underprices
    the parlay — that's edge.
    """

    def __init__(self, positive_boost: float = 1.35, negative_penalty: float = 0.80):
        self._boost = positive_boost
        self._penalty = negative_penalty

    @property
    def name(self) -> str:
        return "correlation_adjustment"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        clusters = [_detect_cluster(leg.title) for leg in candidate.legs]
        known = [c for c in clusters if c is not None]

        if len(known) < 2:
            return RuleResult(
                rule_name=self.name,
                passed=True,
                score=50.0,
                reason="Insufficient thematic signal for correlation estimate",
                details={"clusters": clusters},
            )

        unique = set(known)
        if len(unique) == 1:
            adj = self._boost
            label = f"Positive correlation detected ({known[0]})"
        else:
            adj = 1.0
            label = f"Legs span {len(unique)} clusters — near-independent"

        adjusted_prob = min(0.95, candidate.independent_prob * adj)
        edge = (adjusted_prob - candidate.independent_prob) * 100

        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=min(100.0, 50 + edge * 5),
            reason=label,
            details={
                "clusters": clusters,
                "adjustment_factor": adj,
                "adjusted_joint_prob": round(adjusted_prob, 4),
                "edge_from_correlation_pct": round(edge, 2),
            },
        )


class DecouplingRiskRule(Rule):
    """
    Flag parlays where legs could decouple — one resolves YES while another
    fails despite being in the same cluster.

    High-anchor + low-multiplier combos across different domains are actually
    safer from decoupling since they're independent by construction.
    """

    @property
    def name(self) -> str:
        return "decoupling_risk"

    def evaluate(self, candidate: ParlayCandidate) -> RuleResult:
        anchors = candidate.anchors
        multipliers = candidate.multipliers

        if not anchors or not multipliers:
            return RuleResult(
                rule_name=self.name,
                passed=True,
                score=60.0,
                reason="No anchor-multiplier split — decoupling N/A",
            )

        anchor_clusters = {_detect_cluster(a.title) for a in anchors} - {None}
        mult_clusters = {_detect_cluster(m.title) for m in multipliers} - {None}
        overlap = anchor_clusters & mult_clusters

        if overlap:
            return RuleResult(
                rule_name=self.name,
                passed=True,
                score=70.0,
                reason=f"Anchor and multiplier share cluster(s) {overlap} — correlated fate",
                details={"shared_clusters": list(overlap)},
            )

        return RuleResult(
            rule_name=self.name,
            passed=True,
            score=85.0,
            reason="Anchor and multiplier are in different domains — independent risk",
        )

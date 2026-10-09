"""Tests for the parlay rules engine."""


from src.parlay_rules.engine import ParlayEngine
from src.parlay_rules.models import (
    Leg,
    LegRole,
    Outcome,
    ParlayCandidate,
    Side,
    Verdict,
)
from src.parlay_rules.sizing import compute_sizing, kelly_fraction
from src.parlay_rules.strategies import (
    aggressive_rules,
    anchor_multiplier_rules,
    conservative_rules,
)


def _make_leg(title: str, price: float, market_id: str = "") -> Leg:
    return Leg(
        market_id=market_id or title.replace(" ", "_")[:20],
        title=title,
        price=price,
        outcome=Outcome.YES,
        side=Side.BUY,
    )


def _make_candidate(legs: list[Leg], category: str = "test") -> ParlayCandidate:
    return ParlayCandidate(
        parlay_id="test_1",
        legs=legs,
        category=category,
    )


class TestLegRole:
    def test_anchor(self):
        leg = _make_leg("Sure thing", 0.95)
        assert leg.role == LegRole.ANCHOR

    def test_multiplier(self):
        leg = _make_leg("Long shot", 0.10)
        assert leg.role == LegRole.MULTIPLIER

    def test_neutral(self):
        leg = _make_leg("Coin flip", 0.55)
        assert leg.role == LegRole.NEUTRAL


class TestParlayCandidate:
    def test_independent_prob(self):
        c = _make_candidate([
            _make_leg("A", 0.90),
            _make_leg("B", 0.80),
        ])
        assert abs(c.independent_prob - 0.72) < 0.001

    def test_payout_multiplier(self):
        c = _make_candidate([
            _make_leg("A", 0.50),
            _make_leg("B", 0.50),
        ])
        assert abs(c.payout_multiplier - 4.0) < 0.01

    def test_anchors_and_multipliers(self):
        c = _make_candidate([
            _make_leg("Anchor 1", 0.97),
            _make_leg("Anchor 2", 0.92),
            _make_leg("Multiplier", 0.30),
        ])
        assert len(c.anchors) == 2
        assert len(c.multipliers) == 1


class TestKellySizing:
    def test_positive_ev(self):
        f = kelly_fraction(0.60, 2.0)
        assert f > 0

    def test_negative_ev(self):
        f = kelly_fraction(0.20, 2.0)
        assert f == 0.0

    def test_edge_case_zero_prob(self):
        f = kelly_fraction(0.0, 5.0)
        assert f == 0.0

    def test_compute_sizing(self):
        s = compute_sizing(
            joint_prob=0.30,
            payout_multiplier=4.0,
            bankroll=100.0,
            kelly_scale=0.5,
        )
        assert s.recommended_stake > 0
        assert s.recommended_stake <= 10.0
        assert s.max_loss == s.recommended_stake


class TestAnchorMultiplierCombo:
    """Test the user's primary strategy: anchors + multiplier."""

    def test_classic_combo_passes(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = _make_candidate([
            _make_leg("HAN match winner Yes", 0.98),
            _make_leg("Catry match winner Yes", 0.97),
            _make_leg("Sekulic match winner Yes", 0.40),
        ])
        verdict = engine.evaluate(candidate)
        assert verdict.rules_passed > verdict.rules_failed
        assert verdict.payout_multiplier > 2.0

    def test_all_anchors_rejected(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = _make_candidate([
            _make_leg("Sure thing 1", 0.96),
            _make_leg("Sure thing 2", 0.97),
            _make_leg("Sure thing 3", 0.98),
        ])
        verdict = engine.evaluate(candidate)
        # Should fail anchor_multiplier_structure (no multiplier)
        failed_rules = [r.rule_name for r in verdict.rule_results if not r.passed]
        assert "anchor_multiplier_structure" in failed_rules

    def test_single_leg_rejected(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = ParlayCandidate(
            parlay_id="single",
            legs=[_make_leg("Only one", 0.50)],
        )
        verdict = engine.evaluate(candidate)
        assert verdict.verdict in (Verdict.REJECT, Verdict.AVOID)

    def test_duplicate_markets_rejected(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = _make_candidate([
            Leg(market_id="same_market", title="A Yes", price=0.90),
            Leg(market_id="same_market", title="A No", price=0.10),
        ])
        verdict = engine.evaluate(candidate)
        failed_rules = [r.rule_name for r in verdict.rule_results if not r.passed]
        assert "leg_diversity" in failed_rules


class TestCorrelation:
    def test_same_cluster_boosts(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = _make_candidate(
            [
                _make_leg("Bitcoin hits 100k", 0.90),
                _make_leg("Ethereum ETF approved", 0.70),
                _make_leg("Solana breaks $300", 0.30),
            ],
            category="Crypto",
        )
        verdict = engine.evaluate(candidate)
        corr_rule = next(
            (r for r in verdict.rule_results if r.rule_name == "correlation_adjustment"),
            None,
        )
        assert corr_rule is not None
        assert "Positive correlation" in corr_rule.reason

    def test_cross_cluster_independent(self):
        engine = ParlayEngine(rules=anchor_multiplier_rules())
        candidate = _make_candidate([
            _make_leg("Bitcoin hits 100k", 0.90),
            _make_leg("Trump wins election", 0.30),
        ])
        verdict = engine.evaluate(candidate)
        corr_rule = next(
            (r for r in verdict.rule_results if r.rule_name == "correlation_adjustment"),
            None,
        )
        assert corr_rule is not None
        assert "independent" in corr_rule.reason.lower() or "cluster" in corr_rule.reason.lower()


class TestStrategies:
    def test_conservative_is_stricter(self):
        conservative = conservative_rules()
        aggressive = aggressive_rules()
        # Conservative has fewer max legs
        max_legs_c = next(
            r for r in conservative if r.name == "max_legs"
        )
        max_legs_a = next(
            r for r in aggressive if r.name == "max_legs"
        )
        assert max_legs_c._max < max_legs_a._max

    def test_all_strategies_have_ev_rule(self):
        for rules in [anchor_multiplier_rules(), conservative_rules(), aggressive_rules()]:
            names = [r.name for r in rules]
            assert "ev_threshold" in names


class TestEngineConfiguration:
    def test_require_all_rules(self):
        engine = ParlayEngine(
            rules=anchor_multiplier_rules(),
            require_all_rules=True,
        )
        candidate = _make_candidate([
            _make_leg("A", 0.95),
            _make_leg("B", 0.95),
            _make_leg("C", 0.95),
        ])
        verdict = engine.evaluate(candidate)
        assert verdict.verdict == Verdict.REJECT

    def test_custom_bankroll(self):
        engine = ParlayEngine(bankroll=500.0)
        candidate = _make_candidate([
            _make_leg("Anchor", 0.90),
            _make_leg("Mult", 0.30),
        ])
        verdict = engine.evaluate(candidate)
        if verdict.sizing:
            assert verdict.sizing.recommended_stake <= 500.0 * 0.10


class TestVerdictProperties:
    def test_actionable(self):
        engine = ParlayEngine()
        candidate = _make_candidate([
            _make_leg("Strong anchor", 0.95),
            _make_leg("Good multiplier", 0.25),
        ])
        verdict = engine.evaluate(candidate)
        if verdict.verdict in (Verdict.STRONG_BUY, Verdict.BUY):
            assert verdict.is_actionable
        else:
            assert not verdict.is_actionable

    def test_edge_calculation(self):
        engine = ParlayEngine()
        candidate = _make_candidate([
            _make_leg("A", 0.90),
            _make_leg("B", 0.30),
        ])
        verdict = engine.evaluate(candidate)
        # Edge = (joint_est * payout - 1) * 100
        assert isinstance(verdict.edge_pct, float)

"""
Core parlay rules engine.

Evaluates parlay candidates against a configurable rule chain, optionally
runs gated LLM evaluation, and produces a final verdict with sizing.
"""

import logging

from src.parlay_rules.models import (
    LLMEvaluation,
    ParlayCandidate,
    ParlayVerdict,
    RuleResult,
    Verdict,
)
from src.parlay_rules.rules.base import Rule
from src.parlay_rules.sizing import compute_sizing
from src.parlay_rules.strategies import anchor_multiplier_rules

logger = logging.getLogger(__name__)


class ParlayEngine:
    """
    Configurable rules engine for parlay evaluation.

    Runs a chain of Rule instances against each candidate, computes sizing,
    and optionally calls the gated LLM evaluation pipeline.
    """

    def __init__(
        self,
        rules: list[Rule] | None = None,
        bankroll: float = 100.0,
        kelly_scale: float = 0.5,
        max_bet_fraction: float = 0.10,
        require_all_rules: bool = False,
        min_pass_ratio: float = 0.6,
    ):
        self.rules = rules or anchor_multiplier_rules()
        self.bankroll = bankroll
        self.kelly_scale = kelly_scale
        self.max_bet_fraction = max_bet_fraction
        self.require_all_rules = require_all_rules
        self.min_pass_ratio = min_pass_ratio

    def evaluate(
        self,
        candidate: ParlayCandidate,
        llm_results: list[LLMEvaluation] | None = None,
    ) -> ParlayVerdict:
        """
        Run all rules, compute sizing, and produce a verdict.

        Pass llm_results from evaluation.evaluate_with_llm() if LLM gating
        was performed. Otherwise the verdict is rules-only.
        """
        results: list[RuleResult] = []
        for rule in self.rules:
            try:
                r = rule.evaluate(candidate)
                results.append(r)
            except Exception as e:
                results.append(RuleResult(
                    rule_name=rule.name,
                    passed=False,
                    score=0.0,
                    reason=f"Rule error: {e}",
                ))

        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        total = passed + failed
        pass_ratio = passed / total if total > 0 else 0.0

        # Determine joint probability from correlation rule if available
        joint_est = candidate.independent_prob
        for r in results:
            if r.rule_name == "correlation_adjustment" and "adjusted_joint_prob" in r.details:
                joint_est = r.details["adjusted_joint_prob"]
                break

        # Override with LLM joint probability if both models agree
        if llm_results and len(llm_results) >= 2:
            probs = [e.joint_prob_estimate for e in llm_results if e.joint_prob_estimate > 0]
            if len(probs) >= 2:
                joint_est = sum(probs) / len(probs)

        payout = candidate.payout_multiplier
        edge_pct = (joint_est * payout - 1.0) * 100.0

        # Compute verdict from rules + LLM consensus
        verdict = self._compute_verdict(
            pass_ratio, edge_pct, results, llm_results or []
        )

        # Sizing only for actionable verdicts
        sizing = None
        if verdict in (Verdict.STRONG_BUY, Verdict.BUY, Verdict.SPECULATIVE):
            sizing = compute_sizing(
                joint_prob=joint_est,
                payout_multiplier=payout,
                bankroll=self.bankroll,
                kelly_scale=self.kelly_scale,
                max_fraction=self.max_bet_fraction,
            )

        conviction = self._compute_conviction(results, llm_results or [])

        # Label the strategy
        strategy = "anchor-multiplier" if candidate.anchors and candidate.multipliers else "custom"

        return ParlayVerdict(
            parlay_id=candidate.parlay_id,
            verdict=verdict,
            conviction=conviction,
            rule_results=results,
            rules_passed=passed,
            rules_failed=failed,
            joint_prob_estimate=round(joint_est, 4),
            independent_prob=round(candidate.independent_prob, 4),
            payout_multiplier=round(payout, 2),
            edge_pct=round(edge_pct, 2),
            sizing=sizing,
            llm_evaluations=llm_results or [],
            strategy_label=strategy,
        )

    def _compute_verdict(
        self,
        pass_ratio: float,
        edge_pct: float,
        rules: list[RuleResult],
        llm: list[LLMEvaluation],
    ) -> Verdict:
        if self.require_all_rules and any(not r.passed for r in rules):
            return Verdict.REJECT

        if pass_ratio < self.min_pass_ratio:
            return Verdict.REJECT

        # Hard rejection if EV or structure rules fail
        critical_rules = {"ev_threshold", "anchor_multiplier_structure", "max_legs"}
        critical_fails = [r for r in rules if r.rule_name in critical_rules and not r.passed]
        if critical_fails:
            return Verdict.AVOID

        # LLM consensus
        if llm:
            llm_verdicts = [e.verdict for e in llm]
            if all(v == Verdict.AVOID for v in llm_verdicts):
                return Verdict.AVOID
            if all(v == Verdict.STRONG_BUY for v in llm_verdicts):
                return Verdict.STRONG_BUY
            if any(v == Verdict.AVOID for v in llm_verdicts):
                return Verdict.SPECULATIVE

        if edge_pct >= 50.0 and pass_ratio >= 0.8:
            return Verdict.STRONG_BUY
        if edge_pct >= 25.0 and pass_ratio >= 0.6:
            return Verdict.BUY
        if edge_pct >= 10.0:
            return Verdict.SPECULATIVE
        if edge_pct > 0:
            return Verdict.SPECULATIVE

        return Verdict.AVOID

    def _compute_conviction(
        self,
        rules: list[RuleResult],
        llm: list[LLMEvaluation],
    ) -> int:
        rule_scores = [r.score for r in rules if r.passed]
        rule_avg = sum(rule_scores) / len(rule_scores) if rule_scores else 30.0

        if llm:
            llm_avg = sum(e.conviction for e in llm) / len(llm)
            # Weighted: 40% rules, 60% LLM
            return int(rule_avg * 0.4 + llm_avg * 0.6)

        return int(rule_avg)

    async def evaluate_with_llm(
        self,
        candidate: ParlayCandidate,
        ollama_base_url: str = "http://100.110.82.53:11434",
        first_model: str = "qwen2.5:7b",
        second_model: str = "deepseek-r1:latest",
    ) -> ParlayVerdict:
        """
        Full pipeline: rules evaluation, then gated LLM evaluation.
        """
        from src.parlay_rules.evaluation import evaluate_with_llm

        # Run rules first
        preliminary = self.evaluate(candidate)

        # Only invoke LLM if rules pass at threshold
        if preliminary.verdict in (Verdict.REJECT, Verdict.AVOID):
            return preliminary

        llm_results = await evaluate_with_llm(
            candidate,
            ollama_base_url=ollama_base_url,
            first_model=first_model,
            second_model=second_model,
        )

        return self.evaluate(candidate, llm_results=llm_results)

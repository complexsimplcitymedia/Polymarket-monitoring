"""
Gated dual-model LLM evaluation.

Sequential pipeline: Qwen-2.5 first pass, then DeepSeek-R1 confirmation
if the parlay passes the EV threshold. Both models run on the local Ollama
instance (node 06) with keep_alive=-1 for zero cold-start.
"""

import re
import time

import httpx

from src.parlay_rules.models import LLMEvaluation, ParlayCandidate, Verdict


def _build_prompt(candidate: ParlayCandidate) -> str:
    leg_lines = "\n".join(
        f"- Leg {i+1}: {leg.title} ({leg.outcome.value} @ {leg.price*100:.0f}%)"
        for i, leg in enumerate(candidate.legs)
    )
    return (
        "You are an Enterprise Quantitative Prediction Market Strategist.\n"
        f"Evaluate this {len(candidate.legs)}-leg parlay:\n\n"
        f"{leg_lines}\n\n"
        f"Category: {candidate.category}\n"
        f"Independent implied probability: {candidate.independent_prob*100:.1f}%\n"
        f"Payout multiplier: {candidate.payout_multiplier:.2f}x\n\n"
        "Provide a concise analysis (under 200 words):\n"
        "1. Correlation between legs\n"
        "2. True joint probability estimate (0-100%)\n"
        "3. Final verdict: STRONG BUY, BUY, SPECULATIVE, or AVOID\n"
        "4. Conviction score (0-100)\n"
    )


def _parse_verdict(text: str) -> tuple[Verdict, int, float]:
    upper = text.upper()
    if "STRONG BUY" in upper:
        verdict = Verdict.STRONG_BUY
        default_score = 88
    elif "AVOID" in upper:
        verdict = Verdict.AVOID
        default_score = 25
    elif "SPECULATIVE" in upper:
        verdict = Verdict.SPECULATIVE
        default_score = 60
    elif "BUY" in upper:
        verdict = Verdict.BUY
        default_score = 75
    else:
        verdict = Verdict.SPECULATIVE
        default_score = 55

    score_match = re.search(r"conviction[:\s]*(\d{1,3})", text, re.IGNORECASE)
    conviction = int(score_match.group(1)) if score_match else default_score
    conviction = max(0, min(100, conviction))

    prob_match = re.search(r"joint\s*prob[a-z]*[:\s]*(\d{1,3})%", text, re.IGNORECASE)
    joint_prob = float(prob_match.group(1)) / 100.0 if prob_match else 0.0

    return verdict, conviction, joint_prob


def _strip_think_tags(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned or text


async def _call_ollama(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    num_predict: int = 800,
    temperature: float = 0.3,
) -> tuple[str, int]:
    t0 = time.monotonic()
    resp = await client.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": num_predict, "temperature": temperature},
        },
    )
    latency = int((time.monotonic() - t0) * 1000)

    if resp.status_code != 200:
        raise RuntimeError(f"{model} returned HTTP {resp.status_code}")

    data = resp.json()
    raw = (data.get("response") or "").strip()
    thinking = (data.get("thinking") or "").strip()
    cleaned = _strip_think_tags(raw)
    if not cleaned and thinking:
        cleaned = thinking
    if not cleaned:
        raise RuntimeError(f"{model} returned empty response")

    return cleaned, latency


async def evaluate_with_llm(
    candidate: ParlayCandidate,
    ollama_base_url: str = "http://100.110.82.53:11434",
    first_model: str = "qwen2.5:7b",
    second_model: str = "deepseek-r1:latest",
    ev_gate_pct: float = 25.0,
    timeout: float = 180.0,
) -> list[LLMEvaluation]:
    """
    Gated sequential LLM evaluation.

    Pass 1 (Qwen-2.5): Always runs. Quick structural assessment.
    Pass 2 (DeepSeek-R1): Only runs if Pass 1 returns BUY or STRONG_BUY
    and the parlay's EV exceeds the gate threshold.
    """
    prompt = _build_prompt(candidate)
    results: list[LLMEvaluation] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Pass 1: Qwen-2.5
        try:
            text, latency = await _call_ollama(
                client, ollama_base_url, first_model, prompt
            )
            verdict, conviction, joint_prob = _parse_verdict(text)
            results.append(LLMEvaluation(
                model_name=first_model,
                verdict=verdict,
                conviction=conviction,
                joint_prob_estimate=joint_prob,
                report=text,
                latency_ms=latency,
            ))
        except Exception as e:
            results.append(LLMEvaluation(
                model_name=first_model,
                verdict=Verdict.SPECULATIVE,
                conviction=50,
                joint_prob_estimate=0.0,
                report=f"Evaluation error: {e}",
            ))

        # Gate check: only proceed to Pass 2 if Pass 1 is positive
        pass1 = results[0]
        pass1_positive = pass1.verdict in (Verdict.STRONG_BUY, Verdict.BUY)

        indep = candidate.independent_prob
        payout = candidate.payout_multiplier
        ev_pct = (indep * 1.35 * payout - 1.0) * 100.0
        ev_above_gate = ev_pct >= ev_gate_pct

        if not (pass1_positive and ev_above_gate):
            return results

        # Pass 2: DeepSeek-R1 confirmation
        try:
            text, latency = await _call_ollama(
                client, ollama_base_url, second_model, prompt, num_predict=1200
            )
            verdict, conviction, joint_prob = _parse_verdict(text)
            results.append(LLMEvaluation(
                model_name=second_model,
                verdict=verdict,
                conviction=conviction,
                joint_prob_estimate=joint_prob,
                report=text,
                latency_ms=latency,
            ))
        except Exception as e:
            results.append(LLMEvaluation(
                model_name=second_model,
                verdict=Verdict.SPECULATIVE,
                conviction=50,
                joint_prob_estimate=0.0,
                report=f"Evaluation error: {e}",
            ))

    return results

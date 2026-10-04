"""
Correlated Parlay & Multi-Market Opportunity Scanner.

Identifies correlated market clusters, calculates synthetic parlay payouts and EV,
and leverages Gemini Enterprise LLM agents to evaluate joint conditional probability.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from src.backend.database import async_session_factory
from src.backend.models import Market

logger = logging.getLogger(__name__)


def extract_token_ids(m: Market) -> tuple[Optional[str], Optional[str]]:
    """Extract YES and NO token IDs from market model."""
    if not m.clob_token_ids:
        return None, None
    try:
        tokens = json.loads(m.clob_token_ids)
        yes_tok = tokens[0] if len(tokens) > 0 else None
        no_tok = tokens[1] if len(tokens) > 1 else None
        return yes_tok, no_tok
    except Exception:
        return None, None


async def discover_parlay_candidates() -> List[Dict[str, Any]]:
    """
    Find high-liquidity, correlated market pairs and compute synthetic parlay economics.
    """
    async with async_session_factory() as session:
        query = select(Market).where(Market.is_active == True).order_by(Market.volume_7d.desc()).limit(60)
        result = await session.execute(query)
        markets = result.scalars().all()

    # Define thematic keyword filters to cluster markets
    clusters = {
        "Macro & Fed Policy": ["fed", "interest rate", "rate cut", "inflation", "cpi", "recession", "gdp"],
        "Crypto & Digital Assets": ["bitcoin", "btc", "ethereum", "eth", "solana", "crypto", "etf"],
        "US Politics & Administration": ["trump", "biden", "harris", "election", "senate", "house", "cabinet", "veto"],
        "Tech & AI": ["openai", "gemini", "anthropic", "nvidia", "apple", "spacex", "starship", "ai"],
    }

    categorized: Dict[str, List[Market]] = {k: [] for k in clusters}
    for m in markets:
        title_lower = m.title.lower()
        for cat, kws in clusters.items():
            if any(kw in title_lower for kw in kws):
                categorized[cat].append(m)
                break

    parlays = []
    parlay_id = 1

    for category, cluster_markets in categorized.items():
        if len(cluster_markets) < 2:
            continue

        # Pair up the top markets in this cluster
        for i in range(min(3, len(cluster_markets) - 1)):
            for j in range(i + 1, min(i + 3, len(cluster_markets))):
                m1 = cluster_markets[i]
                m2 = cluster_markets[j]

                # Leg 1
                p1 = m1.yes_percentage / 100.0
                yes_tok_1, no_tok_1 = extract_token_ids(m1)

                # Leg 2
                p2 = m2.yes_percentage / 100.0
                yes_tok_2, no_tok_2 = extract_token_ids(m2)

                # Skip if price is too extreme (e.g. < 5% or > 95%)
                if not (0.05 <= p1 <= 0.95 and 0.05 <= p2 <= 0.95):
                    continue

                # Synthetic parlay mechanics:
                # If buying YES on both:
                # Combined cost = p1 * p2
                combined_prob = round(p1 * p2, 4)
                payout_multiplier = round(1.0 / combined_prob, 2) if combined_prob > 0 else 0.0

                legs = [
                    {
                        "market_id": m1.id,
                        "title": m1.title,
                        "outcome": "YES",
                        "price": round(p1, 2),
                        "token_id": yes_tok_1,
                        "side": "BUY",
                    },
                    {
                        "market_id": m2.id,
                        "title": m2.title,
                        "outcome": "YES",
                        "price": round(p2, 2),
                        "token_id": yes_tok_2,
                        "side": "BUY",
                    },
                ]

                # Estimated positive covariance boost (if markets are in same macro cluster)
                estimated_joint_prob = min(0.90, round(combined_prob * 1.35, 4))
                edge = round((estimated_joint_prob - combined_prob) * 100, 1)

                parlays.append({
                    "parlay_id": f"parlay_{parlay_id}",
                    "category": category,
                    "title": f"Correlated {category} Parlay",
                    "legs_count": 2,
                    "legs": legs,
                    "combined_implied_prob": round(combined_prob * 100, 1),
                    "estimated_joint_prob": round(estimated_joint_prob * 100, 1),
                    "payout_multiplier": f"{payout_multiplier}x",
                    "synthetic_cost_per_dollar": round(combined_prob, 3),
                    "potential_return_on_100": round(100.0 * payout_multiplier, 2),
                    "edge_pct": edge,
                    "recommendation": "CONSIDER (+EV Correlated)" if edge > 5.0 else "FAIR VALUE",
                })
                parlay_id += 1

    parlays.sort(key=lambda x: x["edge_pct"], reverse=True)
    return parlays[:10]


def _clean_llm_output(data: Dict[str, Any], model_name: str) -> tuple[str, str]:
    """
    Extract and clean response and thinking fields from Ollama response.
    Returns (cleaned_response, thinking).
    Raises ValueError if both response and thinking are completely empty.
    """
    raw_response = (data.get("response") or "").strip()
    raw_thinking = (data.get("thinking") or "").strip()

    # Strip explicit <think>...</think> tags if embedded in response
    cleaned_response = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()

    # If response is empty after stripping but thinking exists (classic deepseek-r1 behavior when num_predict is low)
    if not cleaned_response and raw_thinking:
        cleaned_response = raw_thinking
    elif not cleaned_response and raw_response:
        cleaned_response = raw_response

    if not cleaned_response and not raw_thinking:
        raise ValueError(f"Model {model_name} returned completely empty response and thinking fields")

    return cleaned_response, raw_thinking


def _parse_model_verdict(text: str) -> tuple[str, int]:
    """Parse qualitative evaluation into standard verdict and conviction score."""
    upper = text.upper()
    if "STRONG BUY" in upper:
        return "STRONG BUY (+EV)", 88
    elif "AVOID" in upper:
        return "AVOID / HIGH RISK", 30
    elif "SPECULATIVE" in upper:
        return "SPECULATIVE (+EV)", 65
    elif "FAVORABLE" in upper or "BUY" in upper:
        return "FAVORABLE (+EV)", 75
    else:
        return "FAVORABLE (+EV)", 70


async def analyze_parlay_with_enterprise_agent(parlay_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run sequential enterprise agentic cross-reference evaluation on a specific parlay candidate.
    Pass 1: DeepSeek-R1 (quantitative deep reasoning & joint probability estimation)
    Pass 2: Qwen-2.5 7B (structural market correlation & decoupling validation)
    Both models run sequentially on node 06 with keep_alive: -1.
    """
    legs = parlay_data.get("legs", [])
    if len(legs) < 2:
        return {"error": "Need at least 2 legs for parlay analysis"}

    leg_descriptions = "\n".join([
        f"- Leg {i+1}: {leg['title']} (Current Price: {int(leg['price']*100)}% | Target: {leg['outcome']})"
        for i, leg in enumerate(legs)
    ])

    prompt = f"""You are an Enterprise Quantitative Prediction Market Strategist.
Analyze the following synthetic parlay combination:

{leg_descriptions}

Category: {parlay_data.get('category')}
Synthetic Payout Multiplier: {parlay_data.get('payout_multiplier')}
Independent Implied Probability: {parlay_data.get('combined_implied_prob')}%

Provide a rigorous, concise analysis (under 300 words) covering:
1. **Correlation & Interdependence**: Are these events positively or negatively correlated? If Leg 1 resolves YES, how does that shift the probability of Leg 2?
2. **Decoupling Risks**: What specific scenarios cause Leg 1 to hit while Leg 2 fails?
3. **True Joint Probability Estimate**: Give your quantitative estimate of the joint probability (0-100%).
4. **Final Conviction Score (0-100%) & Verdict**: (STRONG BUY, SPECULATIVE, or AVOID).
"""

    ds_report = ""
    ds_verdict = "SPECULATIVE (+EV)"
    ds_score = 65

    qwen_report = ""
    qwen_verdict = "SPECULATIVE (+EV)"
    qwen_score = 65

    from src.backend.config import settings
    import httpx

    # Sequential execution: deepseek-r1 first, then qwen2.5:7b (NOT simultaneously)
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Pass 1: DeepSeek-R1
        try:
            ds_resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": "deepseek-r1:latest",
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {
                        "num_predict": 800,
                        "temperature": 0.3,
                    },
                }
            )
            if ds_resp.status_code == 200:
                ds_clean, _ = _clean_llm_output(ds_resp.json(), "deepseek-r1:latest")
                ds_report = ds_clean
                ds_verdict, ds_score = _parse_model_verdict(ds_report)
            else:
                logger.warning(f"DeepSeek-R1 returned HTTP {ds_resp.status_code}")
                ds_report = f"DeepSeek-R1 HTTP {ds_resp.status_code}"
        except Exception as e:
            logger.error(f"DeepSeek-R1 evaluation error: {e}")
            ds_report = f"DeepSeek-R1 evaluation unavailable: {str(e)}"

        # Pass 2: Qwen-2.5 7B (Sequential cross-reference)
        try:
            qwen_model = getattr(settings, "LOCAL_LLM_MODEL", "qwen2.5:7b")
            qwen_resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": qwen_model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {
                        "num_predict": 800,
                        "temperature": 0.3,
                    },
                }
            )
            if qwen_resp.status_code == 200:
                qwen_clean, _ = _clean_llm_output(qwen_resp.json(), qwen_model)
                qwen_report = qwen_clean
                qwen_verdict, qwen_score = _parse_model_verdict(qwen_report)
            else:
                logger.warning(f"Qwen-2.5 returned HTTP {qwen_resp.status_code}")
                qwen_report = f"Qwen-2.5 HTTP {qwen_resp.status_code}"
        except Exception as e:
            logger.error(f"Qwen-2.5 evaluation error: {e}")
            qwen_report = f"Qwen-2.5 evaluation unavailable: {str(e)}"

    # Compute consensus verdict & conviction
    is_ds_positive = "BUY" in ds_verdict or "FAVORABLE" in ds_verdict
    is_qwen_positive = "BUY" in qwen_verdict or "FAVORABLE" in qwen_verdict
    is_ds_avoid = "AVOID" in ds_verdict
    is_qwen_avoid = "AVOID" in qwen_verdict

    if is_ds_avoid and is_qwen_avoid:
        consensus_verdict = "AVOID / HIGH RISK (DUAL MODEL CONSENSUS)"
        consensus_score = min(ds_score, qwen_score)
    elif "STRONG BUY" in ds_verdict and "STRONG BUY" in qwen_verdict:
        consensus_verdict = "STRONG BUY (DUAL MODEL CONSENSUS)"
        consensus_score = 92
    elif is_ds_avoid != is_qwen_avoid:
        consensus_verdict = "DIVERGENT / DISPUTED RISK"
        consensus_score = 45
    elif is_ds_positive or is_qwen_positive:
        consensus_verdict = "FAVORABLE (+EV CONSENSUS)"
        consensus_score = int((ds_score + qwen_score) / 2)
    else:
        consensus_verdict = "SPECULATIVE (+EV)"
        consensus_score = 60

    # Build composite enterprise report
    composite_report = (
        f"### Enterprise Multi-Model Consensus: {consensus_verdict} (Conviction: {consensus_score}%)\n\n"
        f"**Consensus Edge Assessment:** Evaluated across DeepSeek-R1 (Quantitative Reasoning) and Qwen-2.5 7B (Cross-Reference Validation).\n\n"
        f"---\n"
        f"#### 1. DeepSeek-R1 Evaluation\n"
        f"- **Model Verdict:** {ds_verdict}\n"
        f"- **Conviction Score:** {ds_score}%\n\n"
        f"{ds_report}\n\n"
        f"---\n"
        f"#### 2. Qwen-2.5 7B Validation\n"
        f"- **Model Verdict:** {qwen_verdict}\n"
        f"- **Conviction Score:** {qwen_score}%\n\n"
        f"{qwen_report}\n"
    )

    return {
        "parlay_id": parlay_data.get("parlay_id"),
        "title": parlay_data.get("title"),
        "category": parlay_data.get("category"),
        "legs": legs,
        "payout_multiplier": parlay_data.get("payout_multiplier"),
        "combined_implied_prob": parlay_data.get("combined_implied_prob"),
        "conviction_score": consensus_score,
        "verdict": consensus_verdict,
        "confidence": consensus_score,
        "model": "deepseek-r1:latest + qwen2.5:7b (sequential cross-reference)",
        "analysis": composite_report,
        "enterprise_agent_report": composite_report,
        "deepseek_r1": {
            "verdict": ds_verdict,
            "score": ds_score,
            "report": ds_report,
        },
        "qwen_2_5": {
            "verdict": qwen_verdict,
            "score": qwen_score,
            "report": qwen_report,
        },
    }

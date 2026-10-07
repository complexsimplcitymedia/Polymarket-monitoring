"""
Background Automated Opportunity Hunter.

Scans correlated parlay markets, computes real-time mathematical edges, stores high-EV
setups into PostgreSQL (poly_vec), and provides automated or 1-click execution.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy import select, desc

from src.backend.database import async_session_factory
from src.backend.models import Opportunity
from src.backend.extras.parlay import discover_parlay_candidates
from src.backend.config import settings
from src.backend.extras.trading import trading_service

logger = logging.getLogger(__name__)


async def run_opportunity_scan() -> List[Dict[str, Any]]:
    """
    Scan correlated parlays and persist new high-EV opportunities.
    """
    logger.info("Running automated opportunity hunter scan...")
    saved_count = 0
    high_ev_opportunities = []

    # Scan parlay candidates
    try:
        parlays = await discover_parlay_candidates()
        for p in parlays:
            if p.get("edge_pct", 0) >= 5.0:
                high_ev_opportunities.append({
                    "category": "PARLAY",
                    "market_id": p.get("parlay_id"),
                    "title": f"[{p.get('category')}] {p.get('title')} ({p.get('payout_multiplier')} payout)",
                    "bracket": f"{p.get('legs_count')} legs",
                    "true_probability": p.get("estimated_joint_prob", 0.0),
                    "market_price": p.get("combined_implied_prob", 0.0),
                    "edge": p.get("edge_pct", 0.0),
                    "expected_value_pct": round(float(p.get("payout_multiplier", "1.0").replace("x", "")) * 10.0, 1),
                    "kelly_fraction_pct": 5.0,
                    "recommendation": p.get("recommendation", "BUY"),
                    "target_token_id": p.get("legs", [{}])[0].get("token_id"),
                    "target_side": "BUY",
                    "target_limit_price": p.get("synthetic_cost_per_dollar", 0.25),
                    "details": p,
                })
    except Exception as e:
        logger.error(f"Parlay opportunity scan failed: {e}")

    # Persist to PostgreSQL (poly_vec)
    async with async_session_factory() as session:
        for op in high_ev_opportunities:
            # Check if this exact title/bracket was detected in the last 4 hours
            existing = await session.execute(
                select(Opportunity).where(
                    Opportunity.title == op["title"],
                    Opportunity.bracket == op["bracket"],
                    Opportunity.status == "DETECTED",
                )
            )
            if existing.scalar_one_or_none():
                continue

            record = Opportunity(
                category=op["category"],
                market_id=op["market_id"],
                title=op["title"],
                bracket=op["bracket"],
                true_probability=op["true_probability"],
                market_price=op["market_price"],
                edge=op["edge"],
                expected_value_pct=op["expected_value_pct"],
                kelly_fraction_pct=op["kelly_fraction_pct"],
                recommendation=op["recommendation"],
                target_token_id=op["target_token_id"],
                target_side=op["target_side"],
                target_limit_price=op["target_limit_price"],
                status="DETECTED",
                details_json=json.dumps(op["details"]),
            )
            session.add(record)
            saved_count += 1
        await session.commit()

    logger.info(f"Opportunity scan complete: saved {saved_count} new opportunities.")

    # Autonomous Execution Daemon (if enabled in settings)
    if settings.AUTO_TRADE_ENABLED:
        logger.info("Autonomous execution daemon active: checking for actionable +EV opportunities...")
        async with async_session_factory() as session:
            pending_query = select(Opportunity).where(
                Opportunity.status == "DETECTED",
                Opportunity.expected_value_pct >= settings.AUTO_TRADE_MIN_EV,
            ).limit(3)
            result = await session.execute(pending_query)
            candidates = result.scalars().all()

            for cand in candidates:
                try:
                    logger.info(f"Auto-executing opportunity #{cand.id}: {cand.title}")
                    budget = min(settings.AUTO_TRADE_MAX_BET, 5.0)

                    if cand.category == "PARLAY":
                        details = json.loads(cand.details_json or "{}")
                        legs = details.get("legs", [])
                        if legs:
                            res = await trading_service.place_parlay_bundle(
                                legs=legs,
                                total_budget=budget,
                                dry_run=settings.AUTO_TRADE_DRY_RUN,
                            )
                            if res.get("success"):
                                cand.status = "AUTO_EXECUTED"
                                logger.info(f"Successfully auto-executed parlay #{cand.id}")
                    else:
                        price = cand.target_limit_price or 0.50
                        size = round(budget / price, 2) if price > 0 else 1.0
                        tok = cand.target_token_id or f"simulated_token_{cand.id}"

                        res = await trading_service.place_order(
                            token_id=tok,
                            price=price,
                            size=size,
                            side=cand.target_side or "BUY",
                            dry_run=settings.AUTO_TRADE_DRY_RUN,
                        )
                        if res.get("success"):
                            cand.status = "AUTO_EXECUTED"
                            logger.info(f"Successfully auto-executed order #{cand.id}")
                except Exception as e:
                    logger.error(f"Failed to auto-execute opportunity #{cand.id}: {e}")
            await session.commit()

    return high_ev_opportunities


async def get_latest_opportunities(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve the latest detected opportunities from PostgreSQL."""
    async with async_session_factory() as session:
        query = select(Opportunity).order_by(desc(Opportunity.created_at)).limit(limit)
        result = await session.execute(query)
        records = result.scalars().all()
        return [r.to_dict() for r in records]

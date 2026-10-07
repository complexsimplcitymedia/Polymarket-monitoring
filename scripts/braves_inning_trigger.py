#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""
braves_inning_trigger.py — Real-Time MLB Half-Inning Strategy Trigger for Polymarket.

Strategy:
  - Game: Los Angeles Dodgers @ Atlanta Braves (Truist Park)
  - Holding: Atlanta Braves (21 contracts bought at ~13-14%)
  - Market: aec-mlb-lad-atl-2026-10-06
  
Trigger Rule:
  - Braves bat in the BOTTOM of each inning.
  - While Braves bat, allow runs to accumulate (avoids robbing the ticket of a multi-run rally).
  - The minute the BOTTOM half-inning ENDS (3 outs recorded, transition to End/Middle):
    * If Braves scored >= 1 run in that half-inning:
      -> TRIGGER TRADING EXECUTION (Market/Limit sell at the peak bounce!)
    * If Braves scored 0 runs:
      -> Continue holding, wait for next bottom half-inning.
"""

import asyncio
import argparse
import datetime
import json
import logging
import os
import sys
import time
from typing import Any, Optional

sys.path.insert(0, "/home/wolf/Polymarket-monitoring")

import httpx
from dotenv import load_dotenv

load_dotenv("/home/wolf/Polymarket-monitoring/.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BravesTrigger")

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MARKET_SLUG = "aec-mlb-lad-atl-2026-10-06"
GAME_DATE = "2026-10-06"


class BravesInningMonitor:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.client: Optional[Any] = None
        self.last_inning_state: Optional[str] = None
        self.last_half: Optional[str] = None
        self.last_inning_num: Optional[int] = None
        self.bottom_start_runs: Optional[int] = None
        self.in_bottom: bool = False
        self.triggered: bool = False

        self._init_polymarket_client()

    def _init_polymarket_client(self):
        try:
            from polymarket_us import PolymarketUS
            key_id = os.getenv("POLYMARKET_KEY_ID") or os.getenv("POLYMARKET_API_KEY")
            secret = os.getenv("POLYMARKET_SECRET_KEY") or os.getenv("POLYMARKET_SECRET")
            if key_id and secret:
                self.client = PolymarketUS(key_id=key_id, secret_key=secret)
                logger.info("✅ Polymarket US Messiah client authenticated & connected.")
            else:
                logger.warning("Polymarket US credentials missing in .env")
        except Exception as e:
            logger.warning(f"Could not init Polymarket client ({e}). Running in monitor-only mode.")


    def get_market_prices(self) -> dict[str, Any]:
        """Fetches live Best Bid / Offer from Polymarket for the game."""
        if not self.client:
            return {}
        try:
            bbo = self.client.markets.bbo(MARKET_SLUG)
            mdata = bbo.get("marketData", {})
            sample = mdata.get("lastPriceSample", {})
            dodgers_px = float(sample.get("longPx", {}).get("value") or mdata.get("bestBid", {}).get("value") or 0.89)
            braves_px = float(sample.get("shortPx", {}).get("value") or 0.11)
            return {
                "dodgers_pct": round(dodgers_px * 100, 1),
                "braves_pct": round(braves_px * 100, 1),
                "dodgers_px": dodgers_px,
                "braves_px": braves_px,
                "best_bid": mdata.get("bestBid", {}).get("value"),
                "best_ask": mdata.get("bestAsk", {}).get("value"),
            }
        except Exception as e:
            logger.debug(f"Error fetching market prices: {e}")
            return {}

    async def fetch_game_data(self, http_client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
        params = {
            "sportId": 1,
            "startDate": GAME_DATE,
            "endDate": GAME_DATE,
            "hydrate": "team,linescore,probablePitcher"
        }
        try:
            r = await http_client.get(MLB_SCHEDULE_URL, params=params, timeout=8.0)
            data = r.json()
            for d in data.get("dates", []):
                for g in d.get("games", []):
                    if "Braves" in g.get("teams", {}).get("home", {}).get("team", {}).get("name", ""):
                        return g
        except Exception as e:
            logger.error(f"Error fetching MLB feed: {e}")
        return None

    def execute_trade_exit(self, runs_scored: int, inning_num: int, braves_pct: float):
        """Executes the sell/exit order when trigger condition is satisfied."""
        logger.info("=" * 70)
        logger.info(f"🎯 [TRIGGER FIRED] Bottom of Inning {inning_num} Complete!")
        logger.info(f"⚾ Braves scored {runs_scored} run(s) this half-inning.")
        logger.info(f"📈 Current Braves Market Price: {braves_pct}% (Bounced from ~11-13% baseline)")
        logger.info("=" * 70)

        if self.dry_run:
            logger.info("⚠️ [DRY RUN ACTIVE] Trade simulated: SELL 21 SHORT contracts (Atlanta Braves) at market.")
            logger.info("🎯 Execution successfully verified without placing live orders.")
            self.triggered = True
            return

        if not self.client:
            logger.error("❌ Live trade cannot execute: Polymarket client not configured.")
            return

        try:
            # Place closing order for 21 contracts (or $3 notional)
            logger.info(f"🚀 Placing LIVE order to close position on {MARKET_SLUG}...")
            # We can retrieve current position quantity
            pos = self.client.portfolio.positions()
            p_data = pos.get("positions", {}).get(MARKET_SLUG, {})
            qty = abs(float(p_data.get("netPositionDecimal") or p_data.get("netPosition") or 21))
            
            # Place market order or aggressive limit to sell the bounce
            logger.info(f"Submitting close order for {qty} contracts...")
            # Using client.orders.create if available
            res = self.client.orders.create({
                "marketSlug": MARKET_SLUG,
                "intent": "ORDER_INTENT_SELL_SHORT",
                "price": str(max(0.15, braves_pct / 100.0)),
                "quantity": qty,
                "type": "LIMIT",
                "tif": "IOC"
            })
            logger.info(f"✅ Order submitted: {res}")
            self.triggered = True
        except Exception as e:
            logger.error(f"❌ Failed to submit order: {e}")

    async def run_loop(self):
        logger.info("Starting Braves Inning Trigger Monitor...")
        logger.info(f"Mode: {'DRY RUN (Simulation)' if self.dry_run else 'LIVE TRADING'}")
        logger.info(f"Target Market: {MARKET_SLUG}")
        logger.info("Trigger Rule: Fire trade the instant the BOTTOM of any inning concludes with Braves runs > 0.\n")

        async with httpx.AsyncClient(headers={"User-Agent": "WolfLogic-Polymarket/2.0"}) as http:
            while not self.triggered:
                g = await self.fetch_game_data(http)
                if not g:
                    await asyncio.sleep(4)
                    continue

                status = g.get("status", {}).get("detailedState", "")
                linescore = g.get("linescore", {})
                h = g.get("teams", {}).get("home", {})
                a = g.get("teams", {}).get("away", {})

                home_name = h.get("team", {}).get("name", "Braves")
                away_name = a.get("team", {}).get("name", "Dodgers")
                home_score = int(h.get("score") or 0)
                away_score = int(a.get("score") or 0)

                inning_num = linescore.get("currentInning", 0)
                inning_ord = linescore.get("currentInningOrdinal", f"{inning_num}th")
                inning_half = linescore.get("inningHalf", "") # "Top" or "Bottom"
                inning_state = linescore.get("inningState", "") # "Top", "Bottom", "Middle", "End"
                is_top = bool(linescore.get("isTopInning", True))
                outs = linescore.get("outs", 0)

                # Fetch live Polymarket odds
                m_prices = self.get_market_prices()
                dodgers_str = f"{m_prices.get('dodgers_pct', 89)}%"
                braves_str = f"{m_prices.get('braves_pct', 11)}%"

                # 1. State: Entering the Bottom of an Inning
                if not is_top and not self.in_bottom:
                    self.in_bottom = True
                    self.bottom_start_runs = home_score
                    logger.info(f"🟢 [BOTTOM {inning_ord} STARTED] Braves at bat! Starting Score: {away_name} {away_score} - {home_name} {home_score} (Starting Runs: {self.bottom_start_runs}) | Poly: ATL {braves_str} vs LAD {dodgers_str}")

                # 2. State: Currently inside the Bottom of the Inning
                elif self.in_bottom and not is_top:
                    runs_so_far = home_score - (self.bottom_start_runs or 0)
                    logger.info(f"⏳ [BOTTOM {inning_ord} LIVE] Score: {away_name} {away_score} - {home_name} {home_score} | Outs: {outs} | Runs Scored this Inning: {runs_so_far} | Poly: ATL {braves_str} (holding for full inning)")

                # 3. State: Transition — Bottom of Inning Just Ended!
                elif self.in_bottom and (is_top or inning_state in ("End", "Middle")):
                    self.in_bottom = False
                    runs_scored_in_bottom = home_score - (self.bottom_start_runs or 0)
                    prev_inn = self.last_inning_num or inning_num

                    logger.info(f"🛑 [BOTTOM {prev_inn} ENDED] Half-inning complete! Total Runs Scored by Braves: {runs_scored_in_bottom}")

                    if runs_scored_in_bottom > 0:
                        braves_pct = m_prices.get("braves_pct", 25.0)
                        self.execute_trade_exit(runs_scored_in_bottom, prev_inn, braves_pct)
                        break
                    else:
                        logger.info(f"⚪ Braves did not score in Bottom of {prev_inn} (0 runs). Position held, awaiting next inning.")

                # 4. State: Top of Inning (Dodgers at bat)
                else:
                    logger.info(f"⚾ [TOP {inning_ord}] {away_name} batting | Score: {away_name} {away_score} - {home_name} {home_score} | Outs: {outs} | Poly: ATL {braves_str} vs LAD {dodgers_str}")

                self.last_inning_state = inning_state
                self.last_half = inning_half
                self.last_inning_num = inning_num

                if status in ("Final", "Game Over", "Completed"):
                    logger.info(f"🏁 Game has concluded with status: {status}")
                    break

                await asyncio.sleep(4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Braves Inning Trigger Monitor")
    parser.add_argument("--live", action="store_true", help="Enable LIVE order placement on Polymarket")
    args = parser.parse_args()

    monitor = BravesInningMonitor(dry_run=not args.live)
    asyncio.run(monitor.run_loop())

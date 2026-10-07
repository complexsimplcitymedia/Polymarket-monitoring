"""Monero Polymarket Monitor & Gemini Execution Guard.

Monitors Polymarket for Monero price prediction markets (e.g. > $600),
evaluates order book depth/spreads, and uses Gemini as a valuation ceiling guard.
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional, List
import httpx
from dotenv import load_dotenv

# Load environment
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("monero-guard")

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
CLOB_API_BASE = "https://clob.polymarket.com"


class MoneroMarketGuard:
    def __init__(self, poll_interval_sec: int = 30, max_ceiling_price: float = 0.35):
        self.poll_interval = poll_interval_sec
        self.max_ceiling_price = max_ceiling_price
        self.client = httpx.Client(timeout=15.0)

    def search_markets(self, query: str = "monero") -> List[Dict[str, Any]]:
        """Search Polymarket public search for matching events."""
        try:
            res = self.client.get(GAMMA_SEARCH_URL, params={"q": query})
            if res.status_code != 200:
                logger.error(f"Failed to query Gamma API: {res.status_code} - {res.text}")
                return []
            data = res.json()
            return data.get("events", [])
        except Exception as e:
            logger.error(f"Search request exception: {e}")
            return []

    def get_order_book(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Fetch order book from CLOB API for a given token."""
        try:
            res = self.client.get(f"{CLOB_API_BASE}/book", params={"token_id": token_id})
            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            logger.warning(f"Could not fetch CLOB book for {token_id}: {e}")
            return None

    def evaluate_with_gemini(self, market_info: Dict[str, Any], best_ask: float, spread: float) -> Dict[str, Any]:
        """Use Gemini to evaluate pricing and recommend whether to enter."""
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            return {"allow_entry": best_ask <= self.max_ceiling_price, "reason": "No Gemini API key, using static ceiling"}

        prompt = f"""
You are an algorithmic prediction market execution guard.
A prediction market for Monero has been detected on Polymarket:
- Market Title: {market_info.get('question')}
- Description: {market_info.get('description', '')[:300]}
- Current Best Ask (Yes price): ${best_ask:.3f}
- Current Spread: ${spread:.3f}
- Default Max Price Ceiling: ${self.max_ceiling_price:.3f}

Evaluate whether buying 'Yes' at ${best_ask:.3f} offers positive expected value or if the book is too thin/overpriced.
Output valid JSON in exactly this format:
{{
  "recommended_ceiling": <float, e.g. 0.30>,
  "allow_entry": <true or false>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<brief 1-2 sentence explanation>"
}}
"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            res = self.client.post(url, json=payload, timeout=10.0)
            if res.status_code == 200:
                text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
            else:
                # Fallback to model gemini-1.5-flash if needed
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                res_fb = self.client.post(fallback_url, json=payload, timeout=10.0)
                if res_fb.status_code == 200:
                    text = res_fb.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
        except Exception as e:
            logger.warning(f"Gemini evaluation error: {e}")

        return {"allow_entry": best_ask <= self.max_ceiling_price, "reasoning": "Fallback static rule"}

    def run_check(self) -> Dict[str, Any]:
        """Perform a single detection pass."""
        logger.info("Polling Polymarket Gamma API for Monero markets...")
        events = self.search_markets("monero")
        
        target_600_markets = []
        active_monero_markets = []

        for ev in events:
            title = ev.get("title", "")
            for m in ev.get("markets", []):
                q = m.get("question", "")
                active = m.get("active", False)
                closed = m.get("closed", False)
                
                if active and not closed:
                    active_monero_markets.append((ev, m))
                    if "600" in q or "600" in title:
                        target_600_markets.append((ev, m))

        logger.info(f"Found {len(active_monero_markets)} active Monero market(s).")
        for ev, m in active_monero_markets:
            q = m.get("question")
            prices = m.get("outcomePrices")
            spread = m.get("spread", 0.0)
            best_ask = m.get("bestAsk", 0.0)
            logger.info(f"  -> Active: '{q}' | Yes/No: {prices} | Best Ask: ${best_ask} | Spread: ${spread}")

        if target_600_markets:
            logger.info(f"🎯 TARGET DETECTED! Found {len(target_600_markets)} market(s) with '600'!")
            for ev, m in target_600_markets:
                best_ask = float(m.get("bestAsk") or 0.0)
                spread = float(m.get("spread") or 0.0)
                decision = self.evaluate_with_gemini(m, best_ask, spread)
                logger.info(f"Gemini Guard Decision: {decision}")
            return {"status": "TARGET_FOUND", "markets": target_600_markets}
        else:
            logger.info("ℹ️ No 'Monero > 600' market deployed yet. Will keep monitoring.")
            return {"status": "WAITING_FOR_DEPLOYMENT", "active_monero_count": len(active_monero_markets)}


def main():
    guard = MoneroMarketGuard(poll_interval_sec=30)
    # Run once or loop
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        logger.info("Starting continuous monitor loop (Ctrl+C to stop)...")
        try:
            while True:
                guard.run_check()
                time.sleep(guard.poll_interval)
        except KeyboardInterrupt:
            logger.info("Monitor loop stopped by user.")
    else:
        guard.run_check()


if __name__ == "__main__":
    main()

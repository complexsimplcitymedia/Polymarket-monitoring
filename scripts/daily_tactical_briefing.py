#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""
daily_tactical_briefing.py
Automated daily DeepSeek sports intelligence briefing for Wolf of PolyMarket.
Executes once daily (early morning) to pull ESPN analyst consensus, injury reports,
and team news, evaluating blowout/shutout probability and identifying Polymarket alpha.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
import httpx
import psycopg2
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("daily-briefing")

# Load environment
load_dotenv('/home/wolf/Polymarket-monitoring/.env')
NANOGPT_API_KEY = os.environ.get('NANOGPT_API_KEY', '')

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "dbname": "poly_db",
    "user": "wolf",
    "password": "wolfpoly2026"
}

REPORTS_DIR = "/home/wolf/Polymarket-monitoring/reports"
ALEXANDRIA_EMBED_URL = "http://100.110.82.97:8006/mcp"

ESPN_LEAGUES = [
    ("football", "nfl"),
    ("baseball", "mlb"),
    ("basketball", "nba"),
    ("football", "college-football")
]

def fetch_espn_news():
    """Fetch recent headlines, injury notes, and analyst previews across all major sports."""
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Wolf-Logic-Intelligence/1.0)"}
    
    with httpx.Client(timeout=15.0, headers=headers) as client:
        for sport, league in ESPN_LEAGUES:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/news?limit=10"
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("articles", []):
                        headline = item.get("headline", "")
                        desc = item.get("description", "")
                        pub = item.get("published", "")
                        if headline:
                            articles.append(f"[{league.upper()}] {headline} ({pub}): {desc}")
            except Exception as e:
                logger.warning(f"Failed to fetch ESPN {league} news: {e}")
                
    return articles

def fetch_active_poly_markets():
    """Retrieve top active sports markets from poly_db."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, yes_percentage, volume_24h 
                FROM markets 
                WHERE (title ILIKE '%vs%' OR title ILIKE '%win%') 
                ORDER BY volume_24h DESC NULLS LAST 
                LIMIT 25;
            """)
            rows = cur.fetchall()
            return [f"- Market: {r[1]} | Implied Win%: {r[2]}% | 24h Vol: ${r[3]:,.0f}" for r in rows if r[2] is not None]
    except Exception as e:
        logger.error(f"Failed to fetch active markets from DB: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def generate_deepseek_briefing(espn_feed, poly_markets):
    """Run comprehensive deep analysis through DeepSeek via NanoGPT."""
    if not NANOGPT_API_KEY:
        raise ValueError("NANOGPT_API_KEY is not set.")

    news_text = "\n".join(espn_feed) if espn_feed else "No fresh ESPN feed retrieved."
    markets_text = "\n".join(poly_markets) if poly_markets else "No active sports markets fetched."

    prompt = f"""You are the Chief Quantitative Sports & Prediction Market Analyst for 'Wolf of PolyMarket Powered by Wolf Logic'.
Perform a comprehensive, institutional morning tactical briefing. Take your time to thoroughly connect all narrative lines, injury wires, and betting mechanics.

### 1. ESPN COMMENTATOR CONSENSUS & MEDIA NARRATIVES
- Who are the ESPN/analyst consensus picks to win upcoming matchups, and what specific reasoning are they giving?
- Where is media consensus overreacting or underestimating matchup realities?

### 2. INJURIES & ROSTER INTEGRITY (CRITICAL DETAIL)
- Detail every key player injury, inactive status, questionable tag, or IR stint (starting QBs, lead RBs, offensive line anchors, rotation aces, star defenders).
- How does the loss of each key player fundamentally disrupt scheme efficiency, pass protection, or red-zone execution?

### 3. BLOWOUT & SHUTOUT PROBABILITY MATRIX
- Identify any matchup with high blowout or shutout probability.
- Evaluate ace pitching dominance, collapsed offensive lines, gassed bullpens, or back-to-back fatigue.

### 4. POLYMARKET ALPHA & ACTIONABLE TRADES
- List the top 5 highest-conviction trades on Polymarket sports binary contracts (Moneylines, Spreads, Team Totals).
- Provide the exact stance (BUY YES, BUY NO, FADE), the market trigger, and the edge.

CURRENT LIVE SPORTS WIRE:
{news_text}

ACTIVE POLYMARKET SPREADS & LIQUIDITY:
{markets_text}
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are the Wolf of All Streets Lead Analyst. Institutional quality, razor-sharp edge, zero fluff, high-conviction quantitative reasoning."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2500
    }

    logger.info("Dispatching daily briefing request to DeepSeek...")
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            "https://nano-gpt.com/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {NANOGPT_API_KEY}", "Content-Type": "application/json"},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

def save_report(report_content):
    """Save report to filesystem and poly_db."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_file = os.path.join(REPORTS_DIR, f"morning_briefing_{today_str}.md")
    latest_file = os.path.join(REPORTS_DIR, "latest_briefing.md")

    header = f"# WOLF OF POLYMARKET — MORNING TACTICAL BRIEFING\n**Date:** {today_str} | **Engine:** DeepSeek • Powered by Wolf Logic\n\n---\n\n"
    full_text = header + report_content

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(full_text)
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(full_text)

    logger.info(f"Saved briefing to {report_file} and {latest_file}")

    # Store in poly_db app_state for instant UI lookup
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_briefings (
                    id SERIAL PRIMARY KEY,
                    report_date DATE UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                );
            """)
            cur.execute("""
                INSERT INTO daily_briefings (report_date, content)
                VALUES (%s, %s)
                ON CONFLICT (report_date) DO UPDATE SET content = EXCLUDED.content;
            """, (today_str, full_text))
            conn.commit()
            logger.info("Stored briefing in poly_db table 'daily_briefings'.")
    except Exception as e:
        logger.error(f"Failed to persist briefing into poly_db: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

def main():
    logger.info("Starting Daily Tactical Briefing generation...")
    espn_feed = fetch_espn_news()
    poly_markets = fetch_active_poly_markets()
    logger.info(f"Fetched {len(espn_feed)} news items and {len(poly_markets)} market lines.")
    
    report = generate_deepseek_briefing(espn_feed, poly_markets)
    save_report(report)
    logger.info("Morning tactical briefing complete.")

if __name__ == "__main__":
    main()

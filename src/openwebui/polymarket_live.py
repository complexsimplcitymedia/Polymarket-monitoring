"""
title: Polymarket Live Feed
author: Wolf Logic
version: 0.1.0
description: Persistent tunnel into poly_db — every model sees live game state, prices, plays, and alerts automatically.
"""

import psycopg2
from datetime import datetime, timedelta
from typing import Optional

DB_DSN = "host=100.110.82.54 port=5433 dbname=poly_db user=wolf password=wolfpoly2026"

TAILNET_BACKEND = "http://100.110.82.54:8001"


def _conn():
    return psycopg2.connect(DB_DSN)


def _pct(v) -> str:
    if v is None:
        return "?"
    return f"{v * 100:.0f}%"


class Tools:
    def __init__(self):
        pass

    def live_games(self) -> str:
        """
        Get all live games with their latest scores, prices, and game state.
        Call this whenever the user asks about live games, scores, prices, or what's happening right now.
        """
        since = datetime.utcnow() - timedelta(minutes=20)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT ON (league, game_id)
                        league, game_id, away_team, away_score, home_team, home_score,
                        detail, possession, away_price, home_price, home_win_prob,
                        away_rush_yards, away_rush_carries, home_rush_yards, home_rush_carries,
                        created_at
                    FROM game_snapshots
                    WHERE created_at > %s
                    ORDER BY league, game_id, id DESC
                """, (since,))
                rows = cur.fetchall()

        if not rows:
            return "No live games with a reading in the last 20 minutes."

        lines = ["LIVE GAMES (latest reading):"]
        for r in rows:
            (league, gid, at, asc, ht, hsc, detail, poss,
             ap, hp, hwp, ary, arc, hry, hrc, ts) = r
            line = f"[{league} game {gid}] {at} {asc} @ {ht} {hsc}"
            if detail:
                line += f" | {detail}"
            if poss:
                line += f" | ball: {poss}"
            line += f" | price away {_pct(ap)} home {_pct(hp)} | home win prob {_pct(hwp)}"
            box = []
            if arc:
                box.append(f"away rush {ary}y/{arc} carries")
            if hrc:
                box.append(f"home rush {hry}y/{hrc} carries")
            if box:
                line += f" | {'; '.join(box)}"
            lines.append(line)
        return "\n".join(lines)

    def recent_plays(self, game_id: Optional[str] = None, limit: int = 20) -> str:
        """
        Get the most recent plays/pitches from live games.
        Call this when the user asks what just happened, recent plays, or the action in a game.
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                if game_id:
                    cur.execute("""
                        SELECT league, game_id, period, clock, text, yards, happened_at
                        FROM game_plays
                        WHERE game_id = %s
                        ORDER BY id DESC LIMIT %s
                    """, (game_id, limit))
                else:
                    cur.execute("""
                        SELECT league, game_id, period, clock, text, yards, happened_at
                        FROM game_plays
                        ORDER BY id DESC LIMIT %s
                    """, (limit,))
                rows = cur.fetchall()

        if not rows:
            return "No recent plays recorded."

        lines = ["RECENT PLAYS (newest first):"]
        for league, gid, period, clock, text, yards, ts in rows:
            yard_str = f" ({yards} yds)" if yards is not None else ""
            lines.append(f"- [{league} {gid}] q{period or '?'} {clock or ''} {text}{yard_str}")
        return "\n".join(lines)

    def price_jumps(self, limit: int = 10) -> str:
        """
        Get recent price jumps — 5+ point moves detected in under 5 seconds.
        These often mean market makers reacted to a play before the score feed updated.
        Call this when the user asks about price movement, sudden changes, or market reactions.
        """
        since = datetime.utcnow() - timedelta(minutes=30)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT slug, outcome, from_price, to_price, window_ms, created_at
                    FROM price_jumps
                    WHERE created_at > %s
                    ORDER BY id DESC LIMIT %s
                """, (since, limit))
                rows = cur.fetchall()

        if not rows:
            return "No price jumps in the last 30 minutes."

        lines = ["RECENT PRICE JUMPS (market reacting):"]
        for slug, outcome, fp, tp, wms, ts in rows:
            lines.append(f"- {slug} {outcome}: {fp*100:.0f}% -> {tp*100:.0f}% in {wms}ms")
        return "\n".join(lines)

    def active_alerts(self) -> str:
        """
        Get currently active alerts — trailing longshots, rush edges, rush anomalies.
        Call this when the user asks about alerts, opportunities, or what looks interesting.
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT title, team, margin, market_price, kind, status, created_at
                    FROM alerts
                    WHERE status = 'active'
                    ORDER BY id DESC LIMIT 15
                """)
                rows = cur.fetchall()

        if not rows:
            return "No active alerts right now."

        lines = ["ACTIVE ALERTS:"]
        for title, team, margin, price, kind, status, ts in rows:
            lines.append(f"- [{kind}] {title} | {team} margin {margin} price {_pct(price)}")
        return "\n".join(lines)

    def market_ticks(self, slug: str, limit: int = 20) -> str:
        """
        Get recent price ticks from the Polymarket WebSocket for a specific market slug.
        Call this when the user asks about price history or tick-by-tick movement for a market.
        """
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT outcome, price, poly_ts, created_at
                    FROM market_ticks
                    WHERE slug = %s
                    ORDER BY id DESC LIMIT %s
                """, (slug, limit))
                rows = cur.fetchall()

        if not rows:
            return f"No ticks found for slug '{slug}'."

        lines = [f"RECENT TICKS for {slug} (newest first):"]
        for outcome, price, pts, ts in rows:
            lines.append(f"- {outcome}: {price*100:.1f}% at {pts or ts}")
        return "\n".join(lines)

    def game_context(self, game_id: str) -> str:
        """
        Get everything about a specific game: latest snapshot, recent plays, price jumps, and alerts.
        Call this when the user is focused on one specific game and wants the full picture.
        """
        parts = [
            self.live_games(),
            self.recent_plays(game_id=game_id),
            self.price_jumps(),
            self.active_alerts(),
        ]
        return "\n\n".join(parts)

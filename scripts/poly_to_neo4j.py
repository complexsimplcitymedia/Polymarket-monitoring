#!/home/wolf/miniconda3/envs/messiah/bin/python3
"""poly_db -> Neo4j bridge (Polymarket graph projection).

Projects the Polymarket-monitoring SQL state into the Wolf-Logic Neo4j instance
on VM4 (bolt://100.110.82.54:8687) as a SEPARATE graph namespace.

ISOLATION CONTRACT (hard)
- Every node this bridge creates carries the ``PM`` label (:PMMarket, :PMGame,
  ...). The Alexandria memory graph uses Memory/User/Namespace/Tag and is never
  read or written here. Neo4j Community allows one database, so separation is by
  label namespace, and this bridge touches only PM* labels.
- One-way: SQL is the system of record. This never writes back to poly_db.
- Idempotent: every write is a MERGE on a stable id, so re-runs are safe.
- Weather is intentionally NOT projected (out of scope: non-binary, noise).

Graph model
    (:PMMarket {id, slug, title, volume_7d, yes_percentage, is_active, last_updated})
    (:PMGame   {key, league, game_id, market_slug, home_team, away_team})
    (:PMTeam   {name, league})
    (:PMPrediction {id, sport, game_id, question, predictor, probability, outcome})
    (:PMAlert  {id, kind, sport, game_id, team, gap, status, created_at})
    (:PMPriceJump {id, slug, outcome, from_price, to_price, delta, window_ms, source_ts})

    (:PMGame)-[:HOME_TEAM]->(:PMTeam)
    (:PMGame)-[:AWAY_TEAM]->(:PMTeam)
    (:PMGame)-[:TRACKS]->(:PMMarket)         (matched on market_slug -> slug)
    (:PMPrediction)-[:ABOUT]->(:PMGame)
    (:PMAlert)-[:ON_GAME]->(:PMGame)
    (:PMPriceJump)-[:IN_MARKET]->(:PMMarket) (matched on slug)

Usage:
    python scripts/poly_to_neo4j.py                 # full incremental sync
    python scripts/poly_to_neo4j.py --limit-jumps 500
    python scripts/poly_to_neo4j.py --verify        # isolation + counts only
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent.parent


def _load_env() -> dict:
    env = {}
    envfile = REPO / ".env"
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV = _load_env()

PG = {
    "host": os.getenv("POLY_PG_HOST", "127.0.0.1"),
    "port": int(os.getenv("POLY_PG_PORT", "5433")),
    "dbname": "poly_db",
    "user": "wolf",
    "password": os.getenv("POLY_PG_PASSWORD") or _ENV.get("POLY_PG_PASSWORD", ""),
}


def _neo4j_password() -> str:
    if os.getenv("NEO4J_PASSWORD"):
        return os.environ["NEO4J_PASSWORD"]
    for p in ("/home/wolf/7474-neo4j/secrets/neo4j.env",):
        f = Path(p)
        if f.exists():
            txt = f.read_text()
            if "neo4j/" in txt:
                return txt.split("neo4j/", 1)[1].strip()
    sys.exit("NEO4J_PASSWORD not set and no secret file found")


NEO4J = {
    "uri": os.getenv("NEO4J_URI", "bolt://100.110.82.54:8687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": _neo4j_password(),
}

CONSTRAINTS = [
    "CREATE CONSTRAINT pm_market_id IF NOT EXISTS FOR (m:PMMarket) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT pm_game_key IF NOT EXISTS FOR (g:PMGame) REQUIRE g.key IS UNIQUE",
    "CREATE CONSTRAINT pm_team_key IF NOT EXISTS FOR (t:PMTeam) REQUIRE t.key IS UNIQUE",
    "CREATE CONSTRAINT pm_pred_id IF NOT EXISTS FOR (p:PMPrediction) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT pm_alert_id IF NOT EXISTS FOR (a:PMAlert) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT pm_jump_id IF NOT EXISTS FOR (j:PMPriceJump) REQUIRE j.id IS UNIQUE",
    "CREATE INDEX pm_market_slug IF NOT EXISTS FOR (m:PMMarket) ON (m.slug)",
    "CREATE INDEX pm_game_league IF NOT EXISTS FOR (g:PMGame) ON (g.league)",
]


def fetch(cur, sql, args=None):
    cur.execute(sql, args or ())
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def build(limit_jumps: int, batch: int) -> dict:
    pg = psycopg2.connect(**PG)
    drv = GraphDatabase.driver(NEO4J["uri"], auth=(NEO4J["user"], NEO4J["password"]))
    stats = {}

    with pg.cursor() as cur, drv.session() as s:
        for stmt in CONSTRAINTS:
            s.run(stmt)

        # Markets
        markets = fetch(cur, """
            SELECT id, slug, title, volume_7d, yes_percentage, is_active,
                   to_char(last_updated,'YYYY-MM-DD\"T\"HH24:MI:SS') AS last_updated
            FROM markets
        """)
        for i in range(0, len(markets), batch):
            s.run("""
                UNWIND $rows AS r
                MERGE (m:PMMarket {id: r.id})
                SET m.slug=toLower(r.slug), m.title=r.title, m.volume_7d=r.volume_7d,
                    m.yes_percentage=r.yes_percentage, m.is_active=r.is_active,
                    m.last_updated=r.last_updated
            """, rows=markets[i:i + batch])
        stats["markets"] = len(markets)

        # Games (distinct league+game_id), latest attributes
        games = fetch(cur, """
            SELECT DISTINCT ON (league, game_id)
                   league, game_id, market_slug, home_team, away_team
            FROM game_snapshots
            ORDER BY league, game_id, created_at DESC
        """)
        gamerows = [{
            "key": f"{g['league']}:{g['game_id']}", "league": g['league'], "game_id": str(g['game_id']),
            "market_slug": (g['market_slug'] or "").lower(), "home_team": g['home_team'], "away_team": g['away_team'],
        } for g in games]
        for i in range(0, len(gamerows), batch):
            s.run("""
                UNWIND $rows AS r
                MERGE (g:PMGame {key: r.key})
                SET g.league=r.league, g.game_id=r.game_id, g.market_slug=r.market_slug,
                    g.home_team=r.home_team, g.away_team=r.away_team
            """, rows=gamerows[i:i + batch])
        stats["games"] = len(gamerows)

        # Teams from games
        teams = {}
        for g in games:
            for name in (g["home_team"], g["away_team"]):
                if name:
                    teams[f"{g['league']}:{name}"] = {"key": f"{g['league']}:{name}", "name": name, "league": g["league"]}
        trows = list(teams.values())
        for i in range(0, len(trows), batch):
            s.run("""
                UNWIND $rows AS r
                MERGE (t:PMTeam {key: r.key})
                SET t.name=r.name, t.league=r.league
            """, rows=trows[i:i + batch])
        stats["teams"] = len(trows)

        # Game -> Team / Market edges
        s.run("""
            UNWIND $rows AS r
            MATCH (g:PMGame {key: r.key})
            MERGE (ht:PMTeam {key: r.home_key}) ON CREATE SET ht.name=r.home_name, ht.league=r.league
            MERGE (at:PMTeam {key: r.away_key}) ON CREATE SET at.name=r.away_name, at.league=r.league
            MERGE (g)-[:HOME_TEAM]->(ht)
            MERGE (g)-[:AWAY_TEAM]->(at)
        """, rows=[{
            "key": f"{g['league']}:{g['game_id']}", "league": g['league'],
            "home_key": f"{g['league']}:{g['home_team']}", "home_name": g['home_team'],
            "away_key": f"{g['league']}:{g['away_team']}", "away_name": g['away_team'],
        } for g in games if g['home_team'] and g['away_team']])

        s.run("""
            UNWIND $rows AS r
            MATCH (g:PMGame {key: r.key})
            MATCH (m:PMMarket {slug: r.slug})
            MERGE (g)-[:TRACKS]->(m)
        """, rows=[{"key": f"{g['league']}:{g['game_id']}", "slug": (g['market_slug'] or '').lower()}
                   for g in games if g['market_slug']])

        # Predictions
        preds = fetch(cur, """
            SELECT id, sport, game_id, question, predictor, probability, outcome,
                   to_char(created_at,'YYYY-MM-DD\"T\"HH24:MI:SS') AS created_at
            FROM predictions
        """)
        s.run("""
            UNWIND $rows AS r
            MERGE (p:PMPrediction {id: r.id})
            SET p.sport=r.sport, p.game_id=r.game_id, p.question=r.question,
                p.predictor=r.predictor, p.probability=r.probability, p.outcome=r.outcome,
                p.created_at=r.created_at
        """, rows=[{**p, "id": str(p["id"]), "game_id": str(p["game_id"])} for p in preds])
        stats["predictions"] = len(preds)

        # Alerts
        alerts = fetch(cur, """
            SELECT id, kind, sport, game_id, team, gap, status,
                   to_char(created_at,'YYYY-MM-DD\"T\"HH24:MI:SS') AS created_at
            FROM alerts
        """)
        s.run("""
            UNWIND $rows AS r
            MERGE (a:PMAlert {id: r.id})
            SET a.kind=r.kind, a.sport=r.sport, a.game_id=r.game_id, a.team=r.team,
                a.gap=r.gap, a.status=r.status, a.created_at=r.created_at
        """, rows=[{**a, "id": str(a["id"]), "game_id": str(a["game_id"])} for a in alerts])
        stats["alerts"] = len(alerts)

        # Price jumps (the signal rows), most recent N
        jumps = fetch(cur, f"""
            SELECT id, slug, outcome, from_price, to_price, delta, window_ms,
                   to_char(source_ts,'YYYY-MM-DD\"T\"HH24:MI:SS') AS source_ts
            FROM price_jumps
            ORDER BY id DESC LIMIT {int(limit_jumps)}
        """)
        s.run("""
            UNWIND $rows AS r
            MERGE (j:PMPriceJump {id: r.id})
            SET j.slug=toLower(r.slug), j.outcome=r.outcome, j.from_price=r.from_price,
                j.to_price=r.to_price, j.delta=r.delta, j.window_ms=r.window_ms, j.source_ts=r.source_ts
        """, rows=[{**j, "id": str(j["id"])} for j in jumps])
        s.run("""
            UNWIND $rows AS r
            MATCH (j:PMPriceJump {id: r.id}) MATCH (m:PMMarket {slug: r.slug})
            MERGE (j)-[:IN_MARKET]->(m)
        """, rows=[{"id": str(j["id"]), "slug": (j['slug'] or '').lower()} for j in jumps if j['slug']])
        stats["price_jumps"] = len(jumps)

    pg.close()
    drv.close()
    return stats


def verify() -> None:
    drv = GraphDatabase.driver(NEO4J["uri"], auth=(NEO4J["user"], NEO4J["password"]))
    with drv.session() as s:
        print("PM node counts:")
        for rec in s.run("""
            MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH 'PM')
            RETURN labels(n) AS l, count(*) AS c ORDER BY c DESC
        """):
            print(f"  {rec['l']}: {rec['c']}")
        print("PM rel counts:")
        for rec in s.run("""
            MATCH (a)-[r]->(b)
            WHERE any(l IN labels(a) WHERE l STARTS WITH 'PM')
              AND any(l IN labels(b) WHERE l STARTS WITH 'PM')
            RETURN type(r) AS t, count(*) AS c ORDER BY c DESC
        """):
            print(f"  {rec['t']}: {rec['c']}")
        mem = s.run("MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH 'PM') RETURN count(n) AS c").single()["c"]
        pm = s.run("MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH 'PM') RETURN count(n) AS c").single()["c"]
        cross = s.run("""
            MATCH (a)-[r]->(b)
            WHERE any(l IN labels(a) WHERE l STARTS WITH 'PM')
              AND NOT any(l IN labels(b) WHERE l STARTS WITH 'PM')
            RETURN count(r) AS c
        """).single()["c"]
        print(f"ISOLATION: non-PM (Alexandria) nodes = {mem:,}   PM nodes = {pm:,}   cross-graph rels = {cross}")
    drv.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="poly_db -> Neo4j bridge")
    ap.add_argument("--limit-jumps", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=1000)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if args.verify:
        verify()
    else:
        st = build(args.limit_jumps, args.batch)
        print("bridged:", ", ".join(f"{k}={v}" for k, v in st.items()))
        verify()

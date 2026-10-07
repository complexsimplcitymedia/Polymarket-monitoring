import time
import json
import logging
import urllib.request
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("poly-embedder")

# Using the public domain routed to VM-01 (100.110.82.52:11434)
OLLAMA_URL = "https://ollama.wolflogic-ai.com/api/embeddings"
MODEL_NAME = "qwen3-embedding:0.6b"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "dbname": "poly_db",
    "user": "wolf",
    "password": "wolfpoly2026"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def fetch_embedding(text: str):
    payload = json.dumps({"model": MODEL_NAME, "prompt": text[:2000]}).encode('utf-8')
    req = urllib.request.Request(
        OLLAMA_URL, 
        data=payload, 
        headers={"Content-Type": "application/json", "User-Agent": "PolyEmbedder/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        return data.get("embedding")

def process_unembedded_markets(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, title, COALESCE(description, '') FROM markets WHERE embedding IS NULL LIMIT 25;")
        rows = cur.fetchall()
        if not rows:
            return 0
        
        for mid, title, desc in rows:
            text = f"{title}. {desc}".strip()
            try:
                emb = fetch_embedding(text)
                if emb:
                    cur.execute("UPDATE markets SET embedding = %s WHERE id = %s;", (emb, mid))
                    cur.execute("""
                        INSERT INTO polymarket_intelligence_memory (source_table, source_id, title, content, category, embedding, metadata)
                        VALUES ('markets', %s, %s, %s, 'markets', %s, %s);
                    """, (mid, title, text, emb, json.dumps({"source": "markets"})))
            except Exception as e:
                logger.error(f"Failed to embed market {mid}: {e}")
        conn.commit()
        return len(rows)

def process_unembedded_news(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, title, COALESCE(description, '') FROM news_articles WHERE embedding IS NULL LIMIT 25;")
        rows = cur.fetchall()
        if not rows:
            return 0
        
        for nid, title, desc in rows:
            text = f"{title}. {desc}".strip()
            try:
                emb = fetch_embedding(text)
                if emb:
                    cur.execute("UPDATE news_articles SET embedding = %s WHERE id = %s;", (emb, nid))
                    cur.execute("""
                        INSERT INTO polymarket_intelligence_memory (source_table, source_id, title, content, category, embedding, metadata)
                        VALUES ('news_articles', %s, %s, %s, 'news', %s, %s);
                    """, (str(nid), title, text, emb, json.dumps({"source": "news_articles"})))
            except Exception as e:
                logger.error(f"Failed to embed news {nid}: {e}")
        conn.commit()
        return len(rows)

def main():
    logger.info(f"Starting Poly-Embedder (Model: {MODEL_NAME}) via {OLLAMA_URL}...")
    while True:
        try:
            conn = get_db()
            while True:
                m_count = process_unembedded_markets(conn)
                n_count = process_unembedded_news(conn)
                if m_count == 0 and n_count == 0:
                    time.sleep(3)
                else:
                    logger.info(f"Batch embedded: {m_count} markets, {n_count} news articles.")
        except Exception as e:
            logger.error(f"Worker iteration error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

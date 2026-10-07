import http from "node:http";
import { URL } from "node:url";
import { connect } from "./db.js";

const PORT = Number(process.env.API_PORT ?? 8000);
const PYTHON_BACKEND = "http://100.110.82.54:8001";
const pool = connect();

// In-memory caches for upstream APIs
let statusCache = { data: null, at: 0 };
let marketsCache = { data: [], at: 0 };
const tradesCache = new Map(); // id -> { data, at }
const holdersCache = new Map();
const historyCache = new Map();

async function getCachedMarkets() {
  if (Date.now() - marketsCache.at < 30_000 && marketsCache.data.length) {
    return marketsCache.data;
  }
  try {
    const { rows } = await pool.query(
      `SELECT id, slug, title, volume_24h, volume_7d, liquidity, yes_percentage, outcomes_json AS outcomes, is_active, end_date, image_url, last_updated 
       FROM markets WHERE is_active ORDER BY volume_24h DESC LIMIT 50`
    );
    marketsCache = { data: rows, at: Date.now() };
    return rows;
  } catch (err) {
    console.error("Failed to query top markets:", err.message);
    return marketsCache.data;
  }
}

async function getMatchups() {
  try {
    const { rows: snapshots } = await pool.query(`
      SELECT DISTINCT ON (league, game_id)
        league, game_id, market_slug, home_team, away_team,
        home_score, away_score, period, seconds_left, possession,
        home_price, away_price, home_win_prob,
        ts_score, ts_clock, ncaa_score, ncaa_clock, poly_score,
        created_at
      FROM game_snapshots
      WHERE created_at > now() - interval '6 hours'
      ORDER BY league, game_id, created_at DESC
    `);
    return snapshots;
  } catch (err) {
    console.error("Failed to query matchups:", err.message);
    return [];
  }
}

// Fallback proxy to Python uvicorn backend for unhandled endpoints
function proxyToPython(req, res) {
  const options = {
    hostname: "100.110.82.54",
    port: 8001,
    path: req.url,
    method: req.method,
    headers: { ...req.headers, host: "100.110.82.54:8001" },
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  proxyReq.on("error", (err) => {
    res.writeHead(502, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Upstream backend unavailable", message: err.message }));
  });

  req.pipe(proxyReq, { end: true });
}

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const pathname = parsedUrl.pathname;

  // CORS Headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  try {
    // 1. Health Check
    if (pathname === "/api/health" || pathname === "/health") {
      res.setHeader("Content-Type", "application/json");
      res.writeHead(200);
      res.end(JSON.stringify({ status: "ok", engine: "nodejs-v22-native", timestamp: new Date().toISOString() }));
      return;
    }

    // 2. Polymarket Status Check
    if (pathname === "/api/status/polymarket") {
      res.setHeader("Content-Type", "application/json");
      if (Date.now() - statusCache.at < 30_000 && statusCache.data) {
        res.writeHead(200);
        res.end(JSON.stringify(statusCache.data));
        return;
      }
      try {
        const resp = await fetch("https://status.polymarket.com/api/v2/summary.json");
        const json = await resp.json();
        const payload = {
          overall: json.status?.description ?? "All Systems Operational",
          indicator: json.status?.indicator ?? "none",
          updated_at: json.page?.updated_at ?? new Date().toISOString(),
          components: json.components ?? [],
          incidents: json.incidents ?? [],
          scheduled_maintenances: json.scheduled_maintenances ?? [],
        };
        statusCache = { data: payload, at: Date.now() };
        res.writeHead(200);
        res.end(JSON.stringify(payload));
        return;
      } catch (e) {
        res.writeHead(200);
        res.end(JSON.stringify({ overall: "Operational", indicator: "none", error: e.message }));
        return;
      }
    }

    // 3. Markets Status
    if (pathname === "/api/markets/status") {
      res.setHeader("Content-Type", "application/json");
      const { rows } = await pool.query(
        `SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_active) AS active, MAX(last_updated) AS last_sync FROM markets`
      );
      res.writeHead(200);
      res.end(JSON.stringify({
        total_markets: Number(rows[0]?.total ?? 0),
        active_markets: Number(rows[0]?.active ?? 0),
        last_sync: rows[0]?.last_sync ?? new Date().toISOString(),
        status: "healthy",
      }));
      return;
    }

    // 4. Top 50 Markets
    if (pathname === "/api/markets/top50" || pathname === "/api/markets") {
      res.setHeader("Content-Type", "application/json");
      const markets = await getCachedMarkets();
      res.writeHead(200);
      res.end(JSON.stringify({ markets, count: markets.length }));
      return;
    }

    // 5. Live Sports Matchups
    if (pathname === "/api/sports/matchups" || pathname === "/api/scanners/cfb/live") {
      res.setHeader("Content-Type", "application/json");
      const matchups = await getMatchups();
      res.writeHead(200);
      res.end(JSON.stringify({ matchups, count: matchups.length, updated_at: new Date().toISOString() }));
      return;
    }

    // 6. Market Trades (GET /api/markets/{id}/trades)
    const tradesMatch = pathname.match(/^\/api\/markets\/([^/]+)\/trades$/);
    if (tradesMatch) {
      res.setHeader("Content-Type", "application/json");
      const id = decodeURIComponent(tradesMatch[1]);
      
      // Check cache (10s)
      if (tradesCache.has(id) && Date.now() - tradesCache.get(id).at < 10_000) {
        res.writeHead(200);
        res.end(JSON.stringify(tradesCache.get(id).data));
        return;
      }

      try {
        // Query Polymarket Data API v2 directly from Node.js
        const resp = await fetch(`https://data-api.polymarket.com/v2/trades?condition=${encodeURIComponent(id)}&limit=100`);
        let data = [];
        if (resp.ok) {
          data = await resp.json();
        } else {
          // Fallback to market_ticks in database
          const { rows } = await pool.query(
            `SELECT * FROM market_ticks WHERE asset_id = $1 OR slug = $1 ORDER BY created_at DESC LIMIT 50`,
            [id]
          );
          data = rows;
        }
        const payload = { trades: data, count: data.length, market_id: id };
        tradesCache.set(id, { data: payload, at: Date.now() });
        res.writeHead(200);
        res.end(JSON.stringify(payload));
        return;
      } catch (e) {
        res.writeHead(200);
        res.end(JSON.stringify({ trades: [], count: 0, error: e.message }));
        return;
      }
    }

    // 7. Market Holders (GET /api/markets/{id}/holders)
    const holdersMatch = pathname.match(/^\/api\/markets\/([^/]+)\/holders$/);
    if (holdersMatch) {
      res.setHeader("Content-Type", "application/json");
      const id = decodeURIComponent(holdersMatch[1]);

      if (holdersCache.has(id) && Date.now() - holdersCache.get(id).at < 30_000) {
        res.writeHead(200);
        res.end(JSON.stringify(holdersCache.get(id).data));
        return;
      }

      try {
        const resp = await fetch(`https://data-api.polymarket.com/v2/holders?market=${encodeURIComponent(id)}`);
        let data = { holders: [] };
        if (resp.ok) {
          data = await resp.json();
        }
        holdersCache.set(id, { data, at: Date.now() });
        res.writeHead(200);
        res.end(JSON.stringify(data));
        return;
      } catch (e) {
        res.writeHead(200);
        res.end(JSON.stringify({ holders: [], error: e.message }));
        return;
      }
    }

    // 8. Market Price History (GET /api/markets/{id}/history)
    const historyMatch = pathname.match(/^\/api\/markets\/([^/]+)\/history$/);
    if (historyMatch) {
      res.setHeader("Content-Type", "application/json");
      const id = decodeURIComponent(historyMatch[1]);

      if (historyCache.has(id) && Date.now() - historyCache.get(id).at < 30_000) {
        res.writeHead(200);
        res.end(JSON.stringify(historyCache.get(id).data));
        return;
      }

      try {
        const resp = await fetch(`https://clob.polymarket.com/prices-history?market=${encodeURIComponent(id)}&interval=1d&fidelity=60`);
        let data = { history: [] };
        if (resp.ok) {
          data = await resp.json();
        }
        historyCache.set(id, { data, at: Date.now() });
        res.writeHead(200);
        res.end(JSON.stringify(data));
        return;
      } catch (e) {
        res.writeHead(200);
        res.end(JSON.stringify({ history: [], error: e.message }));
        return;
      }
    }

    // 9. Market News (GET /api/news/{id} or /api/news)
    const newsMatch = pathname.match(/^\/api\/news(?:\/([^/]+))?$/);
    if (newsMatch) {
      res.setHeader("Content-Type", "application/json");
      const id = newsMatch[1] ? decodeURIComponent(newsMatch[1]) : null;
      let query = `SELECT * FROM news_articles ORDER BY published_at DESC LIMIT 20`;
      let params = [];
      if (id) {
        query = `SELECT * FROM news_articles WHERE market_id = $1 OR market_id IN (SELECT id FROM markets WHERE slug = $1) ORDER BY published_at DESC LIMIT 20`;
        params = [id];
      }
      try {
        const { rows } = await pool.query(query, params);
        res.writeHead(200);
        res.end(JSON.stringify({ articles: rows, total: rows.length, market_id: id }));
        return;
      } catch (e) {
        res.writeHead(200);
        res.end(JSON.stringify({ articles: [], total: 0, market_id: id }));
        return;
      }
    }

    // 10. Market Stats (GET /api/markets/{id}/stats)
    const statsMatch = pathname.match(/^\/api\/markets\/([^/]+)\/stats$/);
    if (statsMatch) {
      res.setHeader("Content-Type", "application/json");
      const identifier = decodeURIComponent(statsMatch[1]);
      const { rows } = await pool.query(
        `SELECT volume_24h, volume_7d, liquidity, yes_percentage, last_updated FROM markets WHERE id = $1 OR slug = $1 LIMIT 1`,
        [identifier]
      );
      res.writeHead(200);
      res.end(JSON.stringify(rows[0] ?? { volume_24h: 0, liquidity: 0, yes_percentage: 50 }));
      return;
    }

    // 11. Market Detail (GET /api/markets/{id})
    const marketMatch = pathname.match(/^\/api\/markets\/([^/]+)$/);
    if (marketMatch) {
      res.setHeader("Content-Type", "application/json");
      const identifier = decodeURIComponent(marketMatch[1]);
      const { rows } = await pool.query(
        `SELECT * FROM markets WHERE id = $1 OR slug = $1 LIMIT 1`,
        [identifier]
      );
      if (!rows.length) {
        res.writeHead(404);
        res.end(JSON.stringify({ error: "Market not found" }));
        return;
      }
      res.writeHead(200);
      res.end(JSON.stringify(rows[0]));
      return;
    }

    // 12. Route Probes & Latency Config
    if (pathname === "/api/routes/health") {
      res.setHeader("Content-Type", "application/json");
      res.writeHead(200);
      res.end(JSON.stringify({
        theScore: "https://api.thescore.com",
        mlbStats: "https://statsapi.mlb.com/api/v1",
        gamma: "https://gamma-api.polymarket.com",
        clob: "https://clob.polymarket.com",
        engine: "nodejs-fast-pipe",
      }));
      return;
    }

    // 13. Fallback to Python backend for any complex state/account endpoint
    proxyToPython(req, res);
  } catch (err) {
    console.error("Server Error:", err);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Internal Server Error", message: err.message }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[Node API Engine] Blazing-fast Node.js HTTP service listening on port ${PORT}`);
});

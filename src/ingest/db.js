import pg from "pg";

const COLUMNS = new Set([
  "league", "game_id", "market_slug", "detail", "period", "seconds_left", "possession", "home_team", "away_team",
  "home_rank", "away_rank", "home_score", "away_score", "home_price", "away_price", "home_win_prob", "box_json", "poly_score", "poly_period", "poly_elapsed", "poly_updated_at", "ts_score", "ts_clock", "ts_updated_at", "ncaa_score", "ncaa_clock", "poly_ms", "espn_ms", "ts_ms",
  ...["home", "away"].flatMap((s) => ["first_downs", "total_yards", "pass_yards", "rush_carries", "rush_yards", "turnovers",
    "third_down", "possession_time", "ypc_allowed"].map((c) => `${s}_${c}`)),
]);

export function connect() {
  const url = (process.env.DATABASE_URL ?? "").replace("+asyncpg", "");
  if (!url) throw new Error("DATABASE_URL is not set");
  return new pg.Pool({ connectionString: url, max: 4 });
}

/** Sports markets (slug, title) the live games are matched against. */
export async function loadMarkets(pool) {
  const { rows } = await pool.query(
    `SELECT slug, title FROM markets WHERE is_active AND (slug LIKE 'cfb-%' OR slug LIKE 'nfl-%' OR slug LIKE 'mlb-%')`,
  );
  return rows.filter((r) => r.title.includes(" vs. ") && !r.title.includes(":") && !r.slug.includes("-spread-") && !r.slug.includes("-total-"));
}

export async function insertSnapshots(pool, rows) {
  for (const row of rows) {
    const keys = Object.keys(row).filter((k) => COLUMNS.has(k));
    const sql = `INSERT INTO game_snapshots (${keys.join(",")}) VALUES (${keys.map((_, i) => `$${i + 1}`).join(",")})`;
    await pool.query(sql, keys.map((k) => row[k]));
  }
}

/** Remove readings older than `days`. */
export const purge = (pool, days = 30) =>
  pool.query(`DELETE FROM game_snapshots WHERE created_at < now() - ($1 || ' days')::interval`, [String(days)]);

const TICK_COLS = ["source_ts", "asset_id", "slug", "outcome", "event_type", "best_bid", "best_ask", "price", "last_trade", "lag_ms"];

/** Insert price ticks in one statement. */
export async function insertTicks(pool, rows) {
  if (!rows.length) return;
  const params = [];
  const values = rows.map((r) => `(${TICK_COLS.map((c) => { params.push(r[c] ?? null); return `$${params.length}`; }).join(",")})`);
  await pool.query(`INSERT INTO market_ticks (${TICK_COLS.join(",")}) VALUES ${values.join(",")}`, params);
}

export const purgeTicks = (pool, days = 7) =>
  pool.query(`DELETE FROM market_ticks WHERE created_at < now() - ($1 || ' days')::interval`, [String(days)]);

const JUMP_COLS = ["source_ts", "asset_id", "slug", "outcome", "from_price", "to_price", "delta", "window_ms", "lag_ms"];

export async function insertJumps(pool, rows) {
  if (!rows.length) return;
  const params = [];
  const values = rows.map((r) => `(${JUMP_COLS.map((c) => { params.push(r[c] ?? null); return `$${params.length}`; }).join(",")})`);
  await pool.query(`INSERT INTO price_jumps (${JUMP_COLS.join(",")}) VALUES ${values.join(",")}`, params);
}

const PLAY_COLS = ["league", "game_id", "play_id", "seq", "period", "clock", "kind", "text", "happened_at", "yards",
  "scoring", "turnover", "home_score", "away_score"];

/** Insert plays; ones already stored are skipped. */
export async function insertPlays(pool, league, gameId, plays) {
  if (!plays.length) return;
  const params = [];
  const values = plays.map((p) => `(${PLAY_COLS.map((c) => {
    params.push(c === "league" ? league : c === "game_id" ? gameId : p[c] ?? null);
    return `$${params.length}`;
  }).join(",")})`);
  await pool.query(`INSERT INTO game_plays (${PLAY_COLS.join(",")}) VALUES ${values.join(",")} ON CONFLICT DO NOTHING`, params);
}

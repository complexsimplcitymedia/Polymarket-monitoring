// Lane 2: hold Polymarket's WebSocket open and write every price change to SQL with exact times.
// Runs anywhere that can reach the database (it is meant to run in London, next to the exchange).
import { PriceStream } from "./stream.js";
import { getJson } from "./espn.js";
import { JumpDetector } from "./jumps.js";
import { connect, insertJumps, insertTicks, loadMarkets, purgeTicks } from "./db.js";

// Tick rows are written in batches this far apart (latest change per outcome). 250 = near live; 300000 = every 5 minutes.
const FLUSH_MS = Number(process.env.TICKS_FLUSH_MS ?? 250);
const REFRESH_MS = Number(process.env.TICKS_REFRESH_MS ?? 600_000);
const GAMMA_EVENTS = "https://gamma-api.polymarket.com/events";

const pool = connect();
const log = (...a) => console.log(new Date().toISOString().slice(11, 23), ...a);
const info = new Map();     // asset id -> { slug, outcome }
const pending = new Map();  // asset id -> row waiting for the next flush
const lastWritten = new Map();
const detector = new JumpDetector({
  windowMs: Number(process.env.JUMP_WINDOW_MS ?? 5000), threshold: Number(process.env.JUMP_POINTS ?? 5) / 100,
});
const jumps = [];
let written = 0;
let seen = 0;

const stream = new PriceStream((id, book, ts, kind) => {
  const meta = info.get(id);
  const price = book.price;
  seen++;
  if (!meta || price === null) return;
  const jump = detector.observe(id, price, ts);
  if (jump) {
    log(`JUMP ${meta.slug} ${meta.outcome} ${(jump.from * 100).toFixed(1)} -> ${(jump.to * 100).toFixed(1)} in ${jump.windowMs} ms`);
    jumps.push({ source_ts: new Date(ts).toISOString(), asset_id: id, slug: meta.slug, outcome: meta.outcome,
      from_price: jump.from, to_price: jump.to, delta: jump.delta, window_ms: jump.windowMs, lag_ms: Date.now() - ts });
  }
  const key = `${book.bestBid}|${book.bestAsk}|${price}|${book.last}`;
  if (lastWritten.get(id) === key) return;
  lastWritten.set(id, key);
  pending.set(id, {
    source_ts: new Date(ts).toISOString(), asset_id: id, slug: meta.slug, outcome: meta.outcome, event_type: kind,
    best_bid: book.bestBid, best_ask: book.bestAsk, price, last_trade: book.last, lag_ms: Date.now() - ts,
  });
}, log);

/** Slugs for games from yesterday to tomorrow (UTC), read from the date at the end of the slug. */
const wanted = (slug) => {
  const m = slug.match(/(\d{4}-\d{2}-\d{2})$/);
  if (!m) return false;
  const d = Date.parse(m[1]);
  const today = Date.parse(new Date().toISOString().slice(0, 10));
  return d >= today - 86_400_000 && d <= today + 86_400_000;
};

async function refresh() {
  const slugs = (await loadMarkets(pool)).map((m) => m.slug).filter(wanted);
  let tokens = 0;
  for (let i = 0; i < slugs.length; i += 8) {
    await Promise.all(slugs.slice(i, i + 8).map(async (slug) => {
      try {
        const [event] = (await getJson(`${GAMMA_EVENTS}?slug=${encodeURIComponent(slug)}&_=${Date.now()}`)) ?? [];
        const m = (event?.markets ?? []).find((x) => x.slug === slug);
        if (!m || m.closed) return;
        const outcomes = JSON.parse(m.outcomes), ids = JSON.parse(m.clobTokenIds);
        ids.forEach((id, k) => info.set(id, { slug, outcome: outcomes[k] }));
        stream.subscribe(ids);
        tokens += ids.length;
      } catch { /* a slow answer for one game must not stop the rest */ }
    }));
  }
  log(`watching ${info.size} outcomes across ${slugs.length} games (${tokens} resolved this pass)`);
}

// Jumps are signals, so they are written within a second whatever the tick batch window is.
async function flushJumps() {
  if (!jumps.length) return;
  await insertJumps(pool, jumps.splice(0)).catch((e) => log("jump write failed:", e.message));
}

async function flush() {
  if (!pending.size) return;
  const rows = [...pending.values()];
  pending.clear();
  try { await insertTicks(pool, rows); written += rows.length; } catch (e) { log("write failed:", e.message); }
}

async function main() {
  log("ticks worker up");
  await refresh().catch((e) => log("refresh failed:", e.message));
  stream.start();
  setInterval(flush, FLUSH_MS);
  setInterval(flushJumps, 1000);
  setInterval(() => refresh().catch((e) => log("refresh failed:", e.message)), REFRESH_MS);
  setInterval(() => purgeTicks(pool).catch(() => {}), 3_600_000);
  setInterval(() => { log(`messages ${seen}, rows written ${written}`); seen = 0; written = 0; }, 60_000);
}
main();

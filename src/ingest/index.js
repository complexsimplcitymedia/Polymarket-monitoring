import "./server.js";
// Real-time layer: poll live games and prices, write a reading to SQL whenever something changed.
import { candidateSlugs, outcomePrices, priceFor } from "./names.js";
import { LEAGUES, fetchScoreboards, fetchSummary, getJson, homeWinProb, boxColumns, polyColumns, timed, footballWeek } from "./espn.js";
import { espnPlays, mlbPlays, newPlays } from "./plays.js";
import { fetchNcaa, findContest, ncaaColumns } from "./ncaa.js";
import { fetchLinescore, fetchMlbLive, linescoreExtras } from "./mlb.js";
import { fetchTheScore, findEvent, tsColumns } from "./thescore.js";
import { connect, insertPlays, insertSnapshots, loadMarkets, purge } from "./db.js";

const LIVE_MS = Number(process.env.INGEST_LIVE_MS ?? 10_000);   // ESPN's own cache is 6-10 s, so faster is wasted
const IDLE_MS = Number(process.env.INGEST_IDLE_MS ?? 60_000);   // nothing live
const SUMMARY_MS = Number(process.env.INGEST_SUMMARY_MS ?? 20_000); // box score refresh per game
const GAMMA_EVENTS = "https://gamma-api.polymarket.com/events";

const pool = connect();
let markets = [];
let marketsAt = 0;
const summaries = new Map(); // `${league}:${id}` -> { at, data }
const slugs = new Map();     // `${league}:${id}` -> slug (found once, kept)
const playsSeen = new Map(); // `${league}:${id}` -> Set of play ids already stored
const last = new Map();      // `${league}:${id}` -> state string of the last written reading

const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

async function refreshMarkets() {
  if (Date.now() - marketsAt < 300_000 && markets.length) return;
  try { markets = await loadMarkets(pool); marketsAt = Date.now(); } catch (e) { log("markets load failed:", e.message); }
}

// Polymarket's gamma API sits behind a CDN that caches each URL for up to 5 minutes (max-age=300), so every request
// carries a throwaway parameter to get the live record. One event call returns both the score and the market prices.
const fresh = (url) => `${url}${url.includes("?") ? "&" : "?"}_=${Date.now()}`;

async function eventFor(league, game) {
  const key = `${league}:${game.id}`;
  const tried = slugs.has(key) ? [slugs.get(key)] : candidateSlugs(game.home.name, game.away.name, markets).slice(0, 2);
  for (const slug of tried) {
    try {
      const [[event], ms] = await timed(async () => (await getJson(fresh(`${GAMMA_EVENTS}?slug=${encodeURIComponent(slug)}`))) ?? []);
      const markets = [...(event?.markets ?? [])].sort((a, b) => (b.slug === slug) - (a.slug === slug));
      for (const m of markets) {
        const prices = outcomePrices(m, game.home.name, game.away.name);
        if (prices) { slugs.set(key, slug); return { slug, prices, event, ms }; }
      }
    } catch { /* one slow answer must not stop the cycle */ }
  }
  return null;
}

async function summaryFor(league, game) {
  const key = `${league}:${game.id}`;
  const hit = summaries.get(key);
  if (hit && Date.now() - hit.at < SUMMARY_MS) return hit.data;
  const [data, ms] = await timed(() => fetchSummary(league, game.id));
  summaries.set(key, { at: Date.now(), data, ms });
  return data;
}

const stateOf = (r) => [r.home_score, r.away_score, r.period, Math.floor((r.seconds_left ?? 0) / 15), r.possession,
  Math.round((r.home_price ?? 0) * 100), Math.round((r.away_price ?? 0) * 100), r.home_rush_carries, r.away_rush_carries, r.poly_score, r.poly_elapsed, r.ts_score, r.ts_clock, r.ncaa_score, r.ncaa_clock].join("|");

async function readGame(league, game, tsEvents, tsMs = null, ncaa = []) {
  const market = await eventFor(league, game);
  if (!market) return null; // no market: no reason to spend a box score call
  const event = market.event;
  if (league === "mlb") return readMlb(game, market);
  const summary = await summaryFor(league, game).catch(() => ({}));
  const espnMs = summaries.get(`${league}:${game.id}`)?.ms ?? null;
  await savePlays(league, game, espnPlays(summary));
  return {
    league, game_id: game.id, market_slug: market.slug, detail: game.detail, period: game.period,
    seconds_left: game.secondsLeft, possession: game.possession,
    home_team: game.home.name, away_team: game.away.name, home_rank: game.home.rank, away_rank: game.away.rank,
    home_score: game.home.score, away_score: game.away.score,
    home_price: priceFor(market.prices, game.home.name), away_price: priceFor(market.prices, game.away.name),
    home_win_prob: homeWinProb(summary), ...boxColumns(summary), ...polyColumns(event), poly_ms: market.ms, espn_ms: espnMs, ts_ms: tsMs,
    ...tsColumns(findEvent(tsEvents, game.home.name, game.away.name)),
    ...(league === "cfb" ? ncaaColumns(findContest(ncaa, game.home.name, game.away.name)) : {}),
  };
}

async function savePlays(league, game, plays) {
  const key = `${league}:${game.id}`;
  if (!playsSeen.has(key)) playsSeen.set(key, new Set());
  const fresh = newPlays(plays, playsSeen.get(key));
  if (fresh.length) await insertPlays(pool, league, game.id, fresh).catch((e) => log("plays write failed:", e.message));
}

async function readMlb(game, market) {
  getJson(`https://statsapi.mlb.com/api/v1.1/game/${game.id}/feed/live`)
    .then((feed) => savePlays("mlb", game, mlbPlays(feed))).catch(() => {});
  const [ls, ms] = await timed(() => fetchLinescore(game.id)).catch(() => [null, null]);
  const home = ls?.teams?.home?.runs ?? game.home.score, away = ls?.teams?.away?.runs ?? game.away.score;
  const extras = ls ? linescoreExtras(ls) : game.mlb;
  const half = ls?.inningHalf ?? game.mlb?.half ?? "";
  return {
    league: "mlb", game_id: game.id, market_slug: market.slug,
    detail: ls?.currentInning ? `${half} ${ls.currentInning}, ${ls.outs ?? 0} out` : game.detail,
    period: ls?.currentInning ?? game.period, seconds_left: null, possession: null,
    home_team: game.home.name, away_team: game.away.name, home_rank: null, away_rank: null,
    home_score: home, away_score: away,
    home_price: priceFor(market.prices, game.home.name), away_price: priceFor(market.prices, game.away.name),
    home_win_prob: null, box_json: JSON.stringify({ mlb: extras }),
    ...polyColumns(market.event), poly_ms: market.ms, espn_ms: ms,
  };
}

let cycles = 0;
async function cycle() {
  await refreshMarkets();
  // Load-balance APIs: ask each league's own provider + theScore in parallel (freshest wins),
  // ESPN only breaks ties. Spreads the load so one crowded door never stalls a cycle.
  const live = (await Promise.all(Object.keys(LEAGUES).map(async (l) => (await fetchScoreboards(l).catch(() => [])).map((g) => [l, g])))).flat();
  live.push(...(await fetchMlbLive().catch(() => [])).map((g) => ["mlb", g]));
  const [ncaa, ts] = await Promise.all([
    live.some(([l]) => l === "cfb") ? fetchNcaa(footballWeek()) : Promise.resolve([]),
    Promise.all(Object.keys(LEAGUES).map(async (l) => {
      const [list, ms] = await timed(() => fetchTheScore(l));
      return [l, list, ms];
    })),
  ]);
  const tsMs = Object.fromEntries(ts.map(([l, , ms]) => [l, ms]));
  const tsLists = Object.fromEntries(ts.map(([l, list]) => [l, list]));
  const readings = (await Promise.all(live.map(([l, g]) => readGame(l, g, l === "mlb" ? [] : tsLists[l] ?? [], tsMs[l], ncaa).catch((e) => { log(`game ${g.id}:`, e.message); return null; })))).filter(Boolean);
  const fresh = readings.filter((r) => { const k = `${r.league}:${r.game_id}`; const s = stateOf(r); if (last.get(k) === s) return false; last.set(k, s); return true; });
  if (fresh.length) await insertSnapshots(pool, fresh);
  if (++cycles % 6 === 0) log(`live ${live.length}, with market ${readings.length}, written ${fresh.length}`);
  if (cycles % 360 === 0) await purge(pool).catch(() => {});
  return live.length;
}

async function main() {
  log(`ingest up (live ${LIVE_MS} ms, idle ${IDLE_MS} ms)`);
  for (;;) {
    let liveCount = 0;
    try { liveCount = await cycle(); } catch (e) { log("cycle failed:", e.message); }
    await new Promise((r) => setTimeout(r, liveCount ? LIVE_MS : IDLE_MS));
  }
}
main();

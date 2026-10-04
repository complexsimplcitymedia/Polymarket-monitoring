// ESPN scoreboard and box score parsing for the live layer.
const BASE = {
  cfb: "https://site.api.espn.com/apis/site/v2/sports/football/college-football",
  nfl: "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
};
export const LEAGUES = {
  cfb: { base: BASE.cfb, groups: ["80", "81"], prefix: "cfb-" },
  nfl: { base: BASE.nfl, groups: [null], prefix: "nfl-" },
};

/** Run `fn` and return [result, milliseconds it took]. */
export async function timed(fn) {
  const t = performance.now();
  const result = await fn();
  return [result, Math.round(performance.now() - t)];
}

export async function getJson(url, timeoutMs = 8000) {
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs), headers: { "user-agent": "polymarket-ingest" } });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

const teamState = (c) => ({
  id: String(c.team?.id ?? ""),
  name: c.team?.location ?? "",
  score: Number(c.score ?? 0),
  rank: c.curatedRank?.current && c.curatedRank.current !== 99 ? c.curatedRank.current : null,
});

/** Games in `state` ("in" = live, "pre" = not started) from a scoreboard payload. */
export function parseScoreboard(payload, state = "in") {
  const games = [];
  for (const ev of payload.events ?? []) {
    const comp = ev.competitions?.[0];
    if (!comp || comp.status?.type?.state !== state) continue;
    const by = Object.fromEntries((comp.competitors ?? []).map((c) => [c.homeAway, c]));
    if (!by.home || !by.away) continue;
    const ids = Object.fromEntries((comp.competitors ?? []).map((c) => [String(c.id), c.team?.location]));
    games.push({
      id: String(ev.id),
      start: ev.date ?? null,
      detail: comp.status.type.shortDetail ?? "",
      period: Number(comp.status.period ?? 0),
      secondsLeft: comp.status.clock ?? null,
      possession: ids[String(comp.situation?.possession)] ?? null,
      home: teamState(by.home),
      away: teamState(by.away),
    });
  }
  return games;
}

let football_week = null;
/** The college football week number ESPN reports (used to ask NCAA for the same week). */
export const footballWeek = () => football_week;

export async function fetchScoreboards(league, state = "in") {
  const cfg = LEAGUES[league];
  const pages = await Promise.all(
    cfg.groups.map((g) => getJson(`${cfg.base}/scoreboard?limit=200${g ? `&groups=${g}` : ""}`).catch(() => ({ events: [] }))),
  );
  if (league === "cfb") football_week = pages.find((p) => p.week?.number)?.week.number ?? football_week;
  const seen = new Set();
  return pages.flatMap((p) => parseScoreboard(p, state)).filter((g) => !seen.has(g.id) && seen.add(g.id));
}

export const fetchSummary = (league, eventId) => getJson(`${LEAGUES[league].base}/summary?event=${eventId}`);

/** Latest home win probability (0-1) from a summary, or null. */
export function homeWinProb(summary) {
  const wp = summary.winprobability ?? [];
  return wp.length ? wp[wp.length - 1].homeWinPercentage : null;
}

// ESPN box score stat name -> [column suffix, kind]
const BOX = {
  firstDowns: ["first_downs", "int"], totalYards: ["total_yards", "int"], netPassingYards: ["pass_yards", "int"],
  rushingAttempts: ["rush_carries", "int"], rushingYards: ["rush_yards", "int"], turnovers: ["turnovers", "int"],
  thirdDownEff: ["third_down", "str"], possessionTime: ["possession_time", "str"],
};

/** { home_rush_yards: .., away_...: .., box_json } from a summary's box score. */
export function boxColumns(summary) {
  const cols = {};
  const extra = { home: {}, away: {} };
  for (const t of summary.boxscore?.teams ?? []) {
    const side = t.homeAway;
    if (!(side in extra)) continue;
    for (const s of t.statistics ?? []) {
      const spec = BOX[s.name];
      if (!spec) { extra[side][s.name] = s.displayValue; continue; }
      const n = Number.parseFloat(s.displayValue);
      cols[`${side}_${spec[0]}`] = spec[1] === "str" ? String(s.displayValue) : Number.isFinite(n) ? Math.trunc(n) : null;
    }
  }
  cols.box_json = JSON.stringify(extra);
  return cols;
}

/** Polymarket's own reading of a game from its event record (gamma): score "away-home", period, clock, last update. */
export function polyColumns(event) {
  if (!event) return {};
  return {
    poly_score: event.score ?? null, poly_period: event.period ?? null, poly_elapsed: event.elapsed ?? null,
    poly_updated_at: event.updatedAt ?? null,
  };
}

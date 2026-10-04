// MLB from MLB's own Stats API (statsapi.mlb.com): live games and their linescore, the source baseball always uses first.
import { getJson } from "./espn.js";

const BASE = "https://statsapi.mlb.com/api/v1";
const ordinal = (n) => `${n}${["th", "st", "nd", "rd"][(n % 100 >> 3) ^ 1 && n % 10 < 4 ? n % 10 : 0]}`;

const teamState = (t) => ({ id: String(t.team?.id ?? ""), name: t.team?.name ?? "", score: Number(t.score ?? 0), rank: null });

/** Game shape the ingest loop uses, from one schedule entry that was hydrated with its linescore. */
export function parseGame(g) {
  const ls = g.linescore ?? {};
  const half = ls.inningHalf ? ls.inningHalf[0].toUpperCase() + ls.inningHalf.slice(1).toLowerCase() : "";
  return {
    id: String(g.gamePk),
    start: g.gameDate ?? null,
    detail: ls.currentInning ? `${half} ${ordinal(ls.currentInning)}, ${ls.outs ?? 0} out` : g.status?.detailedState ?? "",
    period: ls.currentInning ?? 0,
    secondsLeft: null,
    possession: null,
    home: teamState(g.teams.home),
    away: teamState(g.teams.away),
    mlb: linescoreExtras(ls),
  };
}

/** Outs, count, runners and hits/errors as a plain object (stored in box_json). */
export function linescoreExtras(ls) {
  const o = ls.offense ?? {};
  return {
    outs: ls.outs ?? null, balls: ls.balls ?? null, strikes: ls.strikes ?? null, half: ls.inningHalf ?? null,
    runners: [o.first ? 1 : 0, o.second ? 1 : 0, o.third ? 1 : 0],
    home_hits: ls.teams?.home?.hits ?? null, away_hits: ls.teams?.away?.hits ?? null,
    home_errors: ls.teams?.home?.errors ?? null, away_errors: ls.teams?.away?.errors ?? null,
  };
}

const ymd = (d) => d.toISOString().slice(0, 10);

/** Games in progress now (yesterday's date included, for games that run past midnight UTC). */
export async function fetchMlbLive() {
  const now = new Date();
  const days = [new Date(now - 86_400_000), now].map(ymd);
  const pages = await Promise.all(days.map((d) =>
    getJson(`${BASE}/schedule?sportId=1&date=${d}&hydrate=linescore`).catch(() => ({ dates: [] }))));
  const seen = new Set();
  return pages.flatMap((p) => (p.dates ?? []).flatMap((d) => d.games ?? []))
    .filter((g) => g.status?.abstractGameState === "Live" && !seen.has(g.gamePk) && seen.add(g.gamePk))
    .map(parseGame);
}

/** The freshest read of one game: its linescore (MLB caches it for 10 seconds). */
export async function fetchLinescore(pk) {
  return getJson(`${BASE}/game/${pk}/linescore`);
}

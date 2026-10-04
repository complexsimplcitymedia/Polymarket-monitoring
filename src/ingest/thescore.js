// theScore's open API: one call per league lists every game it carries, with a fresh box score for each.
import { getJson } from "./espn.js";
import { norm } from "./names.js";

const PATH = { cfb: "ncaaf", nfl: "nfl", mlb: "mlb" };

/** Live games theScore lists for a league. Empty (never a throw) when the feed is down. */
export async function fetchTheScore(league) {
  try {
    const list = await getJson(`https://api.thescore.com/${PATH[league]}/events/current`);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

const names = (t) => [t?.name, t?.medium_name, t?.short_name, t?.full_name].filter(Boolean).map(norm);

/** The theScore event whose teams are this game's two teams (names compared after normalizing). */
export function findEvent(events, home, away) {
  const h = norm(home), a = norm(away);
  return events.find((e) => names(e.home_team).includes(h) && names(e.away_team).includes(a)) ?? null;
}

/** Columns for one game: score "away-home", the clock text, and when theScore last updated the box score. */
export function tsColumns(event) {
  const box = event?.box_score;
  if (!box?.score) return {};
  return {
    ts_score: `${box.score.away?.score ?? 0}-${box.score.home?.score ?? 0}`,
    ts_clock: box.progress?.string ?? null,
    ts_updated_at: box.updated_at ? new Date(box.updated_at).toISOString() : null,
  };
}

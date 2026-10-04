// NCAA's own scoreboard feed (the one ncaa.com and henrygd/ncaa-api read), called directly: max-age=5, no wrapper cache.
import { getJson } from "./espn.js";
import { norm } from "./names.js";

const URL = "https://sdataprod.ncaa.com/";
const HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c";
const DIVISIONS = [11, 12]; // FBS, FCS

/** All contests for a football week (FBS and FCS). Empty (never a throw) when the feed is down. */
export async function fetchNcaa(week, year = new Date().getUTCFullYear()) {
  if (!week) return [];
  const one = (division) => {
    const vars = JSON.stringify({ sportCode: "MFB", division, seasonYear: year, week: Number(week) });
    const ext = JSON.stringify({ persistedQuery: { version: 1, sha256Hash: HASH } });
    return getJson(`${URL}?extensions=${encodeURIComponent(ext)}&variables=${encodeURIComponent(vars)}`)
      .then((d) => d?.data?.contests ?? []).catch(() => []);
  };
  return (await Promise.all(DIVISIONS.map(one))).flat();
}

const teamKey = (t) => norm(String(t?.nameShort ?? ""));

/** The contest between these two teams (names compared after normalizing "St." to "State"). */
export function findContest(contests, home, away) {
  const h = norm(home), a = norm(away);
  return contests.find((c) => {
    const ts = c.teams ?? [];
    const ch = ts.find((t) => t.isHome), ca = ts.find((t) => !t.isHome);
    return ch && ca && teamKey(ch) === h && teamKey(ca) === a;
  }) ?? null;
}

/** Columns for one game: score "away-home" and "<period> <clock>". */
export function ncaaColumns(contest) {
  if (!contest) return {};
  const home = contest.teams.find((t) => t.isHome), away = contest.teams.find((t) => !t.isHome);
  return {
    ncaa_score: `${away.score ?? 0}-${home.score ?? 0}`,
    ncaa_clock: `${contest.currentPeriod ?? ""} ${contest.contestClock ?? ""}`.trim(),
  };
}

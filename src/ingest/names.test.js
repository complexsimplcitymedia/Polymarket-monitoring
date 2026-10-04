import test from "node:test";
import assert from "node:assert/strict";
import { candidateSlugs, norm, outcomePrices, priceFor } from "./names.js";
import { boxColumns, homeWinProb, parseScoreboard, polyColumns } from "./espn.js";

test("norm expands St and strips punctuation", () => {
  assert.equal(norm("Texas St."), "texas state");
  assert.equal(norm("Texas & A&M"), "texas and am");
});

test("candidate slugs need both teams, newest first", () => {
  const markets = [
    { slug: "cfb-templ-sfl-2026-09-01", title: "Temple vs. South Florida" },
    { slug: "cfb-templ-sfl-2026-10-03", title: "Temple vs. South Florida" },
    { slug: "cfb-x-y-2026-10-03", title: "Temple vs. Navy" },
  ];
  assert.deepEqual(candidateSlugs("South Florida", "Temple", markets), ["cfb-templ-sfl-2026-10-03", "cfb-templ-sfl-2026-09-01"]);
});

test("outcome prices only when the outcomes are the two teams", () => {
  const m = { outcomes: '["Temple","South Florida"]', outcomePrices: '["0.97","0.03"]' };
  const p = outcomePrices(m, "South Florida", "Temple");
  assert.equal(priceFor(p, "South Florida"), 0.03);
  assert.equal(outcomePrices({ outcomes: '["Over","Under"]', outcomePrices: '["0.5","0.5"]' }, "A", "B"), null);
});

test("scoreboard: live games with ball and clock", () => {
  const payload = { events: [{ id: "1", date: "2026-10-03T23:30:00Z", competitions: [{
    status: { type: { state: "in", shortDetail: "0:51 - 4th" }, period: 4, clock: 51 },
    situation: { possession: "58" },
    competitors: [
      { id: "58", homeAway: "home", score: "13", team: { id: "58", location: "South Florida" } },
      { id: "218", homeAway: "away", score: "17", team: { id: "218", location: "Temple" } },
    ] }] }, { id: "2", competitions: [{ status: { type: { state: "post" } }, competitors: [] }] }] };
  const [g, ...rest] = parseScoreboard(payload);
  assert.equal(rest.length, 0);
  assert.deepEqual([g.period, g.secondsLeft, g.possession, g.home.score, g.away.score], [4, 51, "South Florida", 13, 17]);
});

test("box score columns and win probability", () => {
  const s = { winprobability: [{ homeWinPercentage: 0.1 }, { homeWinPercentage: 0.01 }], boxscore: { teams: [
    { homeAway: "away", statistics: [{ name: "rushingYards", displayValue: "182" }, { name: "rushingAttempts", displayValue: "36" }, { name: "thirdDownEff", displayValue: "5-12" }, { name: "sacksYardsLost", displayValue: "1-5" }] },
    { homeAway: "home", statistics: [{ name: "rushingYards", displayValue: "113" }] },
  ] } };
  const c = boxColumns(s);
  assert.equal(homeWinProb(s), 0.01);
  assert.deepEqual([c.away_rush_yards, c.away_rush_carries, c.away_third_down, c.home_rush_yards], [182, 36, "5-12", 113]);
  assert.equal(JSON.parse(c.box_json).away.sacksYardsLost, "1-5");
});

test("polymarket event columns", () => {
  assert.deepEqual(polyColumns({ score: "17-13", period: "Q4", elapsed: "00:05", updatedAt: "2026-10-04T02:43:03Z" }),
    { poly_score: "17-13", poly_period: "Q4", poly_elapsed: "00:05", poly_updated_at: "2026-10-04T02:43:03Z" });
  assert.deepEqual(polyColumns(null), {});
});

import { findEvent, tsColumns } from "./thescore.js";

test("theScore: find the game by team names and read its box score", () => {
  const ev = { home_team: { name: "Utah Tech", full_name: "Utah Tech Trailblazers" }, away_team: { name: "Southern Utah" },
    box_score: { score: { home: { score: 27 }, away: { score: 46 } }, progress: { string: "4:27 4th" }, updated_at: "Sun, 04 Oct 2026 03:13:06 -0000" } };
  assert.equal(findEvent([ev], "Utah Tech", "Southern Utah"), ev);
  assert.equal(findEvent([ev], "Utah Tech", "Navy"), null);
  assert.deepEqual(tsColumns(ev), { ts_score: "46-27", ts_clock: "4:27 4th", ts_updated_at: "2026-10-04T03:13:06.000Z" });
  assert.deepEqual(tsColumns(null), {});
});

import test from "node:test";
import assert from "node:assert/strict";
import { espnPlays, mlbPlays, newPlays } from "./plays.js";

test("espn: plays from finished drives and the current one, with the real time", () => {
  const summary = { drives: {
    previous: [{ plays: [{ id: "1", sequenceNumber: "10", text: "Rush for 12 yards", period: { number: 1 }, clock: { displayValue: "9:12" },
      type: { text: "Rush" }, wallclock: "2026-10-03T23:41:02Z", statYardage: 12, scoringPlay: false, isTurnover: false, homeScore: 0, awayScore: 0 }] }],
    current: { plays: [{ id: "2", sequenceNumber: "11", text: "Pass intercepted", wallclock: "2026-10-03T23:41:40Z", isTurnover: true }] },
  } };
  const p = espnPlays(summary);
  assert.deepEqual(p.map((x) => x.play_id), ["1", "2"]);
  assert.equal(p[0].happened_at, "2026-10-03T23:41:02Z");
  assert.equal(p[1].turnover, true);
});

test("mlb: every pitch with its own start time", () => {
  const feed = { liveData: { plays: { allPlays: [{ about: { atBatIndex: 3, inning: 2, halfInning: "top", isScoringPlay: false },
    count: { balls: 1, strikes: 2 }, result: { homeScore: 1, awayScore: 0 },
    playEvents: [
      { index: 0, isPitch: true, startTime: "2026-10-03T19:00:01.100Z", details: { description: "Ball", type: { code: "FF" } }, pitchData: { startSpeed: 95.2 } },
      { index: 1, isPitch: true, startTime: "2026-10-03T19:00:21.900Z", details: { description: "Swinging Strike", type: { code: "SL" } }, pitchData: { startSpeed: 86.1 } },
    ] }] } } };
  const p = mlbPlays(feed);
  assert.deepEqual(p.map((x) => x.play_id), ["3-0", "3-1"]);
  assert.equal(p[1].happened_at, "2026-10-03T19:00:21.900Z");
  assert.equal(p[1].yards, 86.1);
});

test("newPlays returns each play once", () => {
  const seen = new Set();
  assert.equal(newPlays([{ play_id: "a" }, { play_id: "b" }], seen).length, 2);
  assert.equal(newPlays([{ play_id: "b" }, { play_id: "c" }], seen).length, 1);
});

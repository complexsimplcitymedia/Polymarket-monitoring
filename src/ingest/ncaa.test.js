import test from "node:test";
import assert from "node:assert/strict";
import { findContest, ncaaColumns } from "./ncaa.js";

const contest = {
  currentPeriod: "4TH", contestClock: "4:40",
  teams: [
    { isHome: true, nameShort: "New Mexico St.", score: 34 },
    { isHome: false, nameShort: "Western Ky.", score: 13 },
  ],
};

test("ncaa: finds the contest by team names and reads score and clock", () => {
  const c = findContest([contest], "New Mexico State", "Western Ky");
  assert.equal(c, contest);
  assert.deepEqual(ncaaColumns(c), { ncaa_score: "13-34", ncaa_clock: "4TH 4:40" });
  assert.equal(findContest([contest], "Navy", "Army"), null);
  assert.deepEqual(ncaaColumns(null), {});
});

import test from "node:test";
import assert from "node:assert/strict";
import { parseGame } from "./mlb.js";

test("mlb: a live schedule entry becomes the ingest's game shape", () => {
  const g = parseGame({
    gamePk: 824223, gameDate: "2026-09-23T23:10:00Z", status: { abstractGameState: "Live" },
    teams: { away: { team: { id: 120, name: "Washington Nationals" }, score: 3 }, home: { team: { id: 116, name: "Detroit Tigers" }, score: 5 } },
    linescore: { currentInning: 8, inningHalf: "Bottom", outs: 2, balls: 1, strikes: 2, offense: { first: {}, third: {} },
      teams: { home: { hits: 9, errors: 0 }, away: { hits: 6, errors: 1 } } },
  });
  assert.deepEqual([g.id, g.period, g.detail, g.home.score, g.away.score], ["824223", 8, "Bottom 8th, 2 out", 5, 3]);
  assert.deepEqual(g.mlb.runners, [1, 0, 1]);
  assert.equal(g.mlb.away_errors, 1);
});

import test from "node:test";
import assert from "node:assert/strict";
import { Book, PriceStream } from "./stream.js";

test("book: best bid/ask and midpoint", () => {
  const b = new Book();
  b.replace([{ price: "0.52", size: "100" }, { price: "0.50", size: "50" }], [{ price: "0.55", size: "80" }, { price: "0.58", size: "10" }]);
  assert.equal(b.bestBid, 0.52);
  assert.equal(b.bestAsk, 0.55);
  assert.ok(Math.abs(b.price - 0.535) < 1e-9);
});

test("book: a size of 0 removes the level and the best moves", () => {
  const b = new Book();
  b.replace([{ price: "0.52", size: "100" }, { price: "0.50", size: "50" }], [{ price: "0.55", size: "80" }]);
  b.change({ price: "0.52", size: "0", side: "BUY" });
  assert.equal(b.bestBid, 0.5);
  b.change({ price: "0.54", size: "20", side: "SELL" });
  assert.equal(b.bestAsk, 0.54);
});

test("book: a wide spread falls back to the last trade", () => {
  const b = new Book();
  b.replace([{ price: "0.10", size: "5" }], [{ price: "0.60", size: "5" }]);
  assert.equal(b.price, 0.35);          // no last trade yet: midpoint
  b.last = 0.2;
  assert.equal(b.price, 0.2);
});

test("stream: applies book, price change and last trade, and reports each", () => {
  const seen = [];
  const s = new PriceStream((id, book, ts, kind) => seen.push([id, kind, book.price]), () => {});
  s.subscribe(["A"]);
  s.handle(JSON.stringify([{ event_type: "book", asset_id: "A", timestamp: "1000", bids: [{ price: "0.40", size: "10" }], asks: [{ price: "0.44", size: "10" }] }]));
  s.handle(JSON.stringify({ event_type: "price_change", timestamp: "1001", price_changes: [{ asset_id: "A", price: "0.42", size: "5", side: "BUY" }] }));
  s.handle(JSON.stringify({ event_type: "last_trade_price", asset_id: "B", price: "0.9", timestamp: "1002" })); // not subscribed
  s.handle("PONG");
  assert.equal(seen.length, 2);
  assert.ok(Math.abs(seen[0][2] - 0.42) < 1e-9);
  assert.ok(Math.abs(seen[1][2] - 0.43) < 1e-9);
});

import { JumpDetector } from "./jumps.js";

test("jump: a 5 point move inside the window fires once, then waits out the cooldown", () => {
  const d = new JumpDetector({ windowMs: 5000, threshold: 0.05, cooldownMs: 3000 });
  assert.equal(d.observe("A", 0.40, 0), null);
  assert.equal(d.observe("A", 0.42, 1000), null);               // 2 points: not enough
  const j = d.observe("A", 0.48, 2000);                          // 8 points from 0.40
  assert.ok(j && Math.abs(j.delta - 0.08) < 1e-9 && j.windowMs === 2000);
  assert.equal(d.observe("A", 0.55, 2500), null);                // still cooling down
  assert.equal(d.observe("A", 0.30, 8000), null);                // first reading after the quiet time becomes the new reference
  const down = d.observe("A", 0.22, 9000);
  assert.ok(down && down.delta < 0);
});

test("jump: slow drift never fires because the window slides", () => {
  const d = new JumpDetector({ windowMs: 5000, threshold: 0.05 });
  let fired = 0;
  for (let i = 0; i < 40; i++) if (d.observe("A", 0.30 + i * 0.005, i * 1000)) fired++; // +0.5 point a second
  assert.equal(fired, 0);
});

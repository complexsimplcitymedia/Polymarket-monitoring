// Price-jump detector: a market maker reacting to a play moves the price in seconds, often before any score feed posts it.
export class JumpDetector {
  /** @param windowMs look-back for the reference price; threshold minimum move (0.05 = 5 points); cooldownMs quiet time after a jump */
  constructor({ windowMs = 5000, threshold = 0.05, cooldownMs = 3000 } = {}) {
    this.windowMs = windowMs;
    this.threshold = threshold;
    this.cooldownMs = cooldownMs;
    this.history = new Map(); // id -> [[ts, price], ...]
    this.quietUntil = new Map();
  }

  /** Feed one price; returns { from, to, delta, windowMs } when it moved by the threshold or more inside the window. */
  observe(id, price, ts) {
    if (price === null || price === undefined) return null;
    const h = this.history.get(id) ?? [];
    h.push([ts, price]);
    while (h.length && ts - h[0][0] > this.windowMs) h.shift();
    this.history.set(id, h);
    if (ts < (this.quietUntil.get(id) ?? 0)) return null;
    const [t0, p0] = h.reduce((best, cur) => (Math.abs(price - cur[1]) > Math.abs(price - best[1]) ? cur : best), h[0]);
    const delta = price - p0;
    if (Math.abs(delta) < this.threshold) return null;
    this.quietUntil.set(id, ts + this.cooldownMs);
    this.history.set(id, [[ts, price]]);
    return { from: p0, to: price, delta, windowMs: ts - t0 };
  }
}

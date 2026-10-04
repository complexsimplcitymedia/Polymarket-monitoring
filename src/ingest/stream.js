// Polymarket market-channel WebSocket: keeps a live order book per token and pushes changes to a callback.
const URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market";

/** One token's book: price levels per side, last trade, and the display price Polymarket shows. */
export class Book {
  bids = new Map();
  asks = new Map();
  last = null;
  ts = 0;

  replace(bids = [], asks = []) {
    this.bids = new Map(bids.filter((l) => +l.size > 0).map((l) => [+l.price, +l.size]));
    this.asks = new Map(asks.filter((l) => +l.size > 0).map((l) => [+l.price, +l.size]));
  }

  change({ price, size, side }) {
    const levels = side === "BUY" ? this.bids : this.asks;
    if (+size > 0) levels.set(+price, +size); else levels.delete(+price);
  }

  get bestBid() { return this.bids.size ? Math.max(...this.bids.keys()) : null; }
  get bestAsk() { return this.asks.size ? Math.min(...this.asks.keys()) : null; }

  /** Midpoint of the best bid and ask, or the last trade when the spread is wider than 10 cents (Polymarket's own rule). */
  get price() {
    const b = this.bestBid, a = this.bestAsk;
    if (b !== null && a !== null) return a - b <= 0.1 ? (a + b) / 2 : this.last ?? (a + b) / 2;
    return this.last ?? b ?? a;
  }
}

export class PriceStream {
  books = new Map();
  ids = new Set();
  ws = null;
  retry = 0;

  /** @param onUpdate (assetId, book, sourceTsMs, eventType) called on every change */
  constructor(onUpdate, log = console.log) {
    this.onUpdate = onUpdate;
    this.log = log;
  }

  subscribe(ids) {
    const fresh = ids.filter((i) => !this.ids.has(i));
    fresh.forEach((i) => { this.ids.add(i); this.books.set(i, new Book()); });
    if (fresh.length && this.ws?.readyState === 1) this.ws.send(JSON.stringify({ assets_ids: fresh, operation: "subscribe" }));
  }

  start() {
    const ws = new WebSocket(URL);
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.log(`stream open, ${this.ids.size} tokens`);
      ws.send(JSON.stringify({ assets_ids: [...this.ids], type: "market" }));
      this.ping = setInterval(() => ws.readyState === 1 && ws.send("PING"), 10_000);
    };
    ws.onmessage = (e) => this.handle(e.data);
    ws.onerror = () => {};
    ws.onclose = () => {
      clearInterval(this.ping);
      const wait = Math.min(15_000, 500 * 2 ** this.retry++);
      this.log(`stream closed, reconnecting in ${wait} ms`);
      setTimeout(() => this.start(), wait);
    };
  }

  handle(raw) {
    if (raw === "PONG") return;
    let msgs;
    try { msgs = JSON.parse(raw); } catch { return; }
    for (const m of Array.isArray(msgs) ? msgs : [msgs]) this.apply(m);
  }

  apply(m) {
    const ts = Number(m.timestamp) || Date.now();
    if (m.event_type === "book") {
      const b = this.books.get(m.asset_id);
      if (!b) return;
      b.replace(m.bids, m.asks); b.ts = ts;
      this.onUpdate(m.asset_id, b, ts, "book");
    } else if (m.event_type === "price_change") {
      for (const c of m.price_changes ?? []) {
        const b = this.books.get(c.asset_id);
        if (!b) continue;
        b.change(c); b.ts = ts;
        this.onUpdate(c.asset_id, b, ts, "price_change");
      }
    } else if (m.event_type === "last_trade_price") {
      const b = this.books.get(m.asset_id);
      if (!b) return;
      b.last = +m.price; b.ts = ts;
      this.onUpdate(m.asset_id, b, ts, "last_trade");
    }
  }
}

// Team-name normalization and market matching, shared by the ingest loop (mirrors sports/cfb.py norm/candidate_slugs).
export function norm(name) {
  let s = String(name ?? "").toLowerCase().replace("&", " and ").replace(/[^a-z0-9 ]/g, "");
  s = s.replace(/\bst\b/g, "state");
  return s.replace(/\s+/g, " ").trim();
}

/** Slugs whose title ("A vs. B") names exactly these two teams, newest first. */
export function candidateSlugs(home, away, markets) {
  const want = new Set([norm(home), norm(away)]);
  return markets
    .filter(({ title }) => {
      const parts = title.split(" vs. ").map(norm);
      return parts.length === 2 && parts.every((p) => want.has(p)) && new Set(parts).size === 2;
    })
    .map((m) => m.slug)
    .sort()
    .reverse();
}

/** Prices keyed by team name from a gamma market, or null when its outcomes are not these two teams. */
export function outcomePrices(market, home, away) {
  const parse = (v) => (typeof v === "string" ? JSON.parse(v) : v);
  const outcomes = parse(market?.outcomes) ?? [];
  const prices = parse(market?.outcomePrices) ?? [];
  const want = new Set([norm(home), norm(away)]);
  if (outcomes.length !== 2 || !outcomes.every((o) => want.has(norm(o)))) return null;
  return Object.fromEntries(outcomes.map((o, i) => [o, Number(prices[i])]));
}

export function priceFor(prices, team) {
  if (!prices) return null;
  const t = norm(team);
  for (const [k, v] of Object.entries(prices)) if (norm(k) === t) return v;
  return null;
}

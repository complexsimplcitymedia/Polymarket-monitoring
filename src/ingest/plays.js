// Play-by-play: every play (football) and pitch (baseball) saved the moment it is first seen, next to the time it happened.

/** Plays from an ESPN football summary (finished drives plus the drive in progress). */
export function espnPlays(summary) {
  const drives = [...(summary.drives?.previous ?? []), ...(summary.drives?.current ? [summary.drives.current] : [])];
  return drives.flatMap((d) => d.plays ?? []).map((p) => ({
    play_id: String(p.id),
    seq: Number(p.sequenceNumber ?? 0),
    period: p.period?.number ?? null,
    clock: p.clock?.displayValue ?? null,
    text: String(p.text ?? "").slice(0, 400),
    kind: p.type?.text ?? null,
    happened_at: p.wallclock ?? null,
    yards: p.statYardage ?? null,
    scoring: Boolean(p.scoringPlay),
    turnover: Boolean(p.isTurnover),
    home_score: p.homeScore ?? null,
    away_score: p.awayScore ?? null,
  }));
}

/** Every pitch (and other event) of every at-bat in MLB's live feed, with its own start time. */
export function mlbPlays(feed) {
  const all = feed.liveData?.plays?.allPlays ?? [];
  return all.flatMap((ab) => (ab.playEvents ?? []).map((e) => ({
    play_id: `${ab.about?.atBatIndex}-${e.index}`,
    seq: (ab.about?.atBatIndex ?? 0) * 100 + (e.index ?? 0),
    period: ab.about?.inning ?? null,
    clock: `${ab.about?.halfInning ?? ""} ${ab.count ? `${ab.count.balls}-${ab.count.strikes}` : ""}`.trim(),
    text: String(e.details?.description ?? e.details?.event ?? "").slice(0, 400),
    kind: e.isPitch ? `pitch ${e.details?.type?.code ?? ""}`.trim() : e.details?.eventType ?? null,
    happened_at: e.startTime ?? null,
    yards: e.pitchData?.startSpeed ?? null, // pitch speed for pitches
    scoring: Boolean(ab.about?.isScoringPlay && e.index === (ab.playEvents?.length ?? 1) - 1),
    turnover: false,
    home_score: ab.result?.homeScore ?? null,
    away_score: ab.result?.awayScore ?? null,
  })));
}

/** Keep only plays not seen before for this game; `seen` is a Set of play ids that this call updates. */
export function newPlays(plays, seen) {
  const fresh = plays.filter((p) => !seen.has(p.play_id));
  fresh.forEach((p) => seen.add(p.play_id));
  return fresh;
}

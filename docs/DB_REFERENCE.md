# poly_db Reference

Cold-start database reference for the Polymarket Intelligence stack. Every fact
below was read live from the running PostgreSQL 17 instance on 2026-10-04 ~21:52 UTC
and cross-checked against `src/backend/models.py`. Built for agentic retrieval:
each table is one section, with its columns, keys, writer, freshness, and the exact
query to run.

**Instance:** container `polymarket-db` (image `pgvector/pgvector:pg17`) ·
`100.110.82.54:5433` and `127.0.0.1:5433` → `:5432` · database `poly_db` · role `wolf`.
**Access:** `docker exec polymarket-db psql -U wolf -d poly_db -c "<sql>"`
**Schemas:** `public` only. **Views:** 0. **Vector/embedding columns:** none
(despite the pgvector image — no column has the `vector` type).

---

## Table of contents

1. [Fast queries cheat sheet](#fast-queries-cheat-sheet)
2. [Table inventory & row counts](#table-inventory--row-counts)
3. [High-volume / live tables](#high-volume--live-tables)
   - [market_ticks](#market_ticks) · [price_jumps](#price_jumps) · [price_history](#price_history)
   - [game_snapshots](#game_snapshots) · [game_plays](#game_plays) · [source_probes](#source_probes)
   - [markets](#markets)
4. [Signal & judgement tables](#signal--judgement-tables)
   - [opportunities](#opportunities) · [predictions](#predictions) · [alerts](#alerts)
5. [State & small tables](#state--small-tables)
   - [app_state](#app_state) · [bet_notes](#bet_notes) · [program_tiers](#program_tiers) · [webui_events](#webui_events)
6. [Dead / empty tables](#dead--empty-tables)
   - [news_articles](#news_articles)
7. [Anomalies](#anomalies)
8. [UNVERIFIED](#unverified)

---

## Fast queries cheat sheet

Run any of these with `docker exec polymarket-db psql -U wolf -d poly_db -c "<sql>"`.

| Need | Query |
|---|---|
| Row counts for all tables | `SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;` |
| Exact count (not estimate) | `SELECT count(*) FROM <table>;` |
| Full column list for a table | `SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='<table>' ORDER BY ordinal_position;` |
| Keys for a table | `SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='<table>'::regclass;` |
| Indexes for a table | `SELECT indexname, indexdef FROM pg_indexes WHERE tablename='<table>';` |
| Freshest tick | `SELECT slug, outcome, price, lag_ms, source_ts FROM market_ticks ORDER BY id DESC LIMIT 5;` |
| Biggest price jumps today | `SELECT slug, outcome, from_price, to_price, delta, window_ms, lag_ms, source_ts FROM price_jumps WHERE created_at > now() - interval '1 day' ORDER BY abs(delta) DESC LIMIT 20;` |
| Live games right now | `SELECT league, game_id, home_team, away_team, home_score, away_score, period, created_at FROM game_snapshots WHERE created_at > now() - interval '5 min' ORDER BY created_at DESC;` |
| Source health (last probe per source) | `SELECT DISTINCT ON (source) sport, source, ok, status, ms, live_games, updated_age_s, error, created_at FROM source_probes ORDER BY source, created_at DESC;` |
| Market by slug | `SELECT id, title, volume_7d, yes_percentage FROM markets WHERE slug = '<slug>';` |
| Top markets by 7d volume | `SELECT title, volume_7d, yes_percentage FROM markets WHERE is_active ORDER BY volume_7d DESC LIMIT 20;` |
| Opportunity counts by category | `SELECT category, count(*) FROM opportunities GROUP BY category ORDER BY category;` |
| Unsettled predictions | `SELECT sport, game_id, question, predictor, probability, game_time FROM predictions WHERE outcome IS NULL ORDER BY game_time;` |
| Active alerts | `SELECT created_at, kind, sport, team, title, gap, status FROM alerts WHERE status='active' ORDER BY created_at DESC;` |
| App state flag | `SELECT key, value, updated_at FROM app_state;` |

---

## Table inventory & row counts

15 tables remain in `public`. Counts below are `pg_stat_user_tables.n_live_tup`
estimates captured 2026-10-04 21:52 UTC, before the unused weather tables were dropped.

| Table | Est. rows | Freshness (max ts) | Writer |
|---|---:|---|---|
| `price_history` | 147,200 | 21:49:07 | `src/backend/tasks/update_markets.py` |
| `market_ticks` | 79,746 | 21:52:03 | `src/ingest/` (ticks worker) |
| `source_probes` | 8,775 | 21:51:10 | `src/backend/probe.py` |
| `markets` | 2,671 | 21:49:07 | `src/backend/tasks/update_markets.py` |
| `game_snapshots` | 1,716 | 21:51:09 | `src/ingest/` (ingest worker) |
| `price_jumps` | 1,195 | 21:51:36 | `src/ingest/` (ticks worker) |
| `game_plays` | 749 | 21:50:28 | `src/ingest/` (ingest worker) |
| `opportunities` | 191 | 19:59:17 | `src/backend/extras/opportunity_hunter.py` |
| `bet_notes` | 58 | 21:43:50 | `src/backend/bet_notes.py`, `routes/account.py` |
| `alerts` | 32 | 06:08:53 | `src/backend/sports/alerts.py` |
| `predictions` | 28 | 05:13:16 | `src/backend/sports/cfb.py` |
| `webui_events` | 12 | 07:02:49 | `src/backend/routes/webhook.py` |
| `program_tiers` | 10 | 11:44:53 | `src/backend/program_tiers.py`, `routes/tiers.py` |
| `app_state` | 1 | 21:49:07 | `src/backend/tasks/update_markets.py` |
| `news_articles` | 0 | — | **none** (insert path errors — see below) |

On 2026-10-05, the empty `weather_history` and `weather_anomalies` tables were
dropped. The scheduled opportunity hunter now persists parlays only; existing
`WEATHER` opportunities were deleted.

---

## High-volume / live tables

### market_ticks

Order-book ticks from the Polymarket CLOB stream, written by the `ticks` worker
(egress via the `ts-london` sidecar). The hottest table in the system — the
"market side" of the score→reprice edge. One row per price event.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | bigint | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `source_ts` | timestamp | NOT NULL | — |
| `asset_id` | varchar(90) | NOT NULL | — |
| `slug` | varchar(200) | — | — |
| `outcome` | varchar(80) | — | — |
| `event_type` | varchar(20) | — | — |
| `best_bid` | double | — | — |
| `best_ask` | double | — | — |
| `price` | double | — | — |
| `last_trade` | double | — | — |
| `lag_ms` | integer | — | — |

**Key:** `market_ticks_pkey (id)`.
**Indexes:** `ix_market_ticks_asset_time (asset_id, source_ts)`, `ix_market_ticks_created_at (created_at)`.
**Freshness:** max `created_at` 21:52:03, max `source_ts` 21:52:03 — live, seconds-old.
**Sample row:** asset `9763…57369`, slug `nfl-lac-sea-2026-10-04`, outcome `Seahawks`,
`event_type=price_change`, bid 0.97 / ask 0.98 / price 0.975, **`lag_ms = 43`**.

`lag_ms` (43 ms here) is the exchange-side lag — the tick lane is effectively
real-time. This is the raw material for the ~80–90 s score→reprice window; the
delay lives downstream in reprice, not here.

```sql
-- Most recent ticks
SELECT created_at, source_ts, slug, outcome, price, lag_ms
FROM market_ticks ORDER BY id DESC LIMIT 20;

-- Tick cadence for one market
SELECT date_trunc('minute', source_ts) m, count(*), avg(lag_ms)::int avg_lag
FROM market_ticks WHERE slug='<slug>' GROUP BY 1 ORDER BY 1 DESC LIMIT 30;
```

### price_jumps

Derived: ticks whose price moved beyond a threshold inside a window. Written by
the same ticks worker, computed from `market_ticks`.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | bigint | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `source_ts` | timestamp | NOT NULL | — |
| `asset_id` | varchar(90) | NOT NULL | — |
| `slug` | varchar(200) | — | — |
| `outcome` | varchar(80) | — | — |
| `from_price` | double | NOT NULL | — |
| `to_price` | double | NOT NULL | — |
| `delta` | double | NOT NULL | — |
| `window_ms` | integer | NOT NULL | — |
| `lag_ms` | integer | — | — |

**Key:** `price_jumps_pkey (id)`.
**Indexes:** `ix_price_jumps_created_at`, `ix_price_jumps_slug_time (slug, source_ts)`.
**Freshness:** max `created_at` 21:51:36 — live.
**Note:** 1,195 rows — small and sparse, as expected of outliers only.

```sql
SELECT slug, outcome, from_price, to_price, delta, window_ms, lag_ms, source_ts
FROM price_jumps ORDER BY abs(delta) DESC LIMIT 20;
```

### price_history

Slow 15-minute snapshots of market price/volume, written by
`src/backend/tasks/update_markets.py` on an APScheduler `IntervalTrigger(minutes=15)`.
Read by `routes/markets.py` for chart history.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `market_id` | varchar(255) | NOT NULL | — |
| `yes_percentage` | double | NOT NULL | — |
| `volume` | double | NOT NULL | — |
| `timestamp` | timestamp | NOT NULL | `now()` |

**Key:** `price_history_pkey (id)`.
**Indexes:** `ix_price_history_market_id`, `idx_price_history_market_time (market_id, "timestamp")`.
**Freshness:** max `timestamp` 21:49:07 — current 15-min cycle.
**Relation:** `market_id` → `markets.id` (no FK constraint; logical only).

```sql
SELECT "timestamp", yes_percentage, volume FROM price_history
WHERE market_id='<id>' ORDER BY "timestamp" DESC LIMIT 200;
```

### game_snapshots

The scoreboard spine. One row per ingest poll per live game, written by the ingest
worker. **This is the table the ~80–90 s score→reprice window is measured in:** it
stores the same game state from several sources side by side (`poly_*`, `ts_*`,
`ncaa_*`) with per-source latency columns (`poly_ms`, `espn_ms`, `ts_ms`), plus
`home_price`/`away_price` captured at that moment.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `league` | varchar(10) | NOT NULL | — |
| `game_id` | varchar(40) | NOT NULL | — |
| `market_slug` | varchar(200) | — | — |
| `detail` | varchar(80) | — | — |
| `period` | integer | — | — |
| `seconds_left` | double | — | — |
| `possession` | varchar(80) | — | — |
| `home_team` / `away_team` | varchar(80) | NOT NULL | — |
| `home_rank` / `away_rank` | integer | — | — |
| `home_score` / `away_score` | integer | NOT NULL | — |
| `home_price` / `away_price` | double | — | — |
| `home_win_prob` | double | — | — |
| `home_first_downs`, `home_total_yards`, `home_pass_yards`, `home_rush_carries`, `home_rush_yards`, `home_turnovers`, `home_third_down`, `home_possession_time`, `home_ypc_allowed` | mixed | — | — |
| `away_first_downs` … `away_ypc_allowed` | mixed | — | — |
| `box_json` | text | — | — |
| `poly_score` | varchar(20) | — | — |
| `poly_period` | varchar(10) | — | — |
| `poly_elapsed` | varchar(10) | — | — |
| `poly_updated_at` | timestamp | — | — |
| `ts_score` | varchar(20) | — | — |
| `ts_clock` | varchar(20) | — | — |
| `ts_updated_at` | timestamp | — | — |
| `poly_ms` | integer | — | — |
| `espn_ms` | integer | — | — |
| `ts_ms` | integer | — | — |
| `ncaa_score` | varchar(20) | — | — |
| `ncaa_clock` | varchar(30) | — | — |

**Key:** `game_snapshots_pkey (id)`.
**Indexes:** `ix_game_snapshots_created_at`, `ix_game_snapshots_game_time (league, game_id, created_at)`.
**Freshness:** max `created_at` 21:51:09 — live.
**Sample row:** `league=mlb`, `game_id=849825`, `market_slug=mlb-sd-mil-2026-10-04`,
`period=6`, Brewers 1 – Padres 2, `home_price=0.345` / `away_price=0.655`,
`poly_score=2-1`, `poly_ms=216`, `espn_ms=9`, `ts_score`/`ncaa_score` NULL.
`espn_ms=9` vs `poly_ms=216` shows the per-source latency spread the table exists
to capture.

```sql
-- Live board: latest snapshot per game
SELECT DISTINCT ON (league, game_id) league, game_id, home_team, away_team,
       home_score, away_score, period, home_price, away_price, poly_ms, espn_ms
FROM game_snapshots ORDER BY league, game_id, created_at DESC;

-- Score→price rows for one game (the edge window)
SELECT created_at, poly_score, home_score, away_score, home_price, away_price, poly_ms
FROM game_snapshots WHERE game_id='<id>' ORDER BY created_at DESC LIMIT 100;
```

### game_plays

Play-by-play events, written by the ingest worker. Unique on
`(league, game_id, play_id)` so re-polls don't duplicate.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | bigint | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `league` | varchar(10) | NOT NULL | — |
| `game_id` | varchar(40) | NOT NULL | — |
| `play_id` | varchar(60) | NOT NULL | — |
| `seq` | integer | NOT NULL | — |
| `period` | integer | — | — |
| `clock` | varchar(40) | — | — |
| `kind` | varchar(60) | — | — |
| `text` | text | — | — |
| `happened_at` | timestamp | — | — |
| `yards` | double | — | — |
| `scoring` | boolean | NOT NULL | — |
| `turnover` | boolean | NOT NULL | — |
| `home_score` / `away_score` | integer | — | — |

**Key:** `game_plays_pkey (id)`. **Unique:** `uq_game_plays (league, game_id, play_id)`.
**Indexes:** `ix_game_plays_game_seq (league, game_id, seq)`, `ix_game_plays_created_at`.
**Freshness:** max `created_at` 21:50:28.

```sql
SELECT seq, period, clock, kind, text, scoring, home_score, away_score, happened_at
FROM game_plays WHERE game_id='<id>' ORDER BY seq DESC LIMIT 50;
```

### source_probes

Source latency/health telemetry written by `src/backend/probe.py`. Measures each
upstream per sport: HTTP status, ms, bytes, cache age, live games, freshness.
This is how you answer "is statsapi.mlb.com healthy right now" without guessing.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | bigint | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `sport` | varchar(10) | NOT NULL | — |
| `source` | varchar(40) | NOT NULL | — |
| `ok` | boolean | NOT NULL | — |
| `status` | integer | — | — |
| `ms` | integer | — | — |
| `bytes` | integer | — | — |
| `cache_age_s` | integer | — | — |
| `max_age_s` | integer | — | — |
| `cdn` | varchar(30) | — | — |
| `live_games` | integer | — | — |
| `points_total` | integer | — | — |
| `updated_age_s` | double | — | — |
| `error` | varchar(160) | — | — |

**Key:** `source_probes_pkey (id)`. **Index:** `ix_source_probes_sport_time (sport, created_at)`.
**Freshness:** max `created_at` 21:51:10 — live.

```sql
-- Last probe per source, with health
SELECT DISTINCT ON (sport, source) sport, source, ok, status, ms, live_games,
       updated_age_s, error, created_at
FROM source_probes ORDER BY sport, source, created_at DESC;
```

### markets

The catalogue. Top ~100 active Polymarket markets by 7-day volume, upserted by
`src/backend/tasks/update_markets.py` every 15 min. 2,671 rows, all `is_active = true`.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | varchar(255) | NOT NULL | — (Polymarket condition id) |
| `slug` | varchar(500) | NOT NULL | — |
| `title` | text | NOT NULL | — |
| `description` | text | — | — |
| `volume_24h` | double | NOT NULL | — |
| `volume_7d` | double | NOT NULL | — |
| `liquidity` | double | NOT NULL | — |
| `yes_percentage` | double | NOT NULL | — |
| `is_active` | boolean | NOT NULL | — |
| `end_date` | timestamp | — | — |
| `image_url` | text | — | — |
| `clob_token_ids` | text | — | — |
| `last_updated` | timestamp | NOT NULL | `now()` |
| `created_at` | timestamp | NOT NULL | `now()` |
| `outcomes_json` | text | — | — |

**Key:** `markets_pkey (id)`.
**Indexes:** `idx_markets_slug`, `idx_markets_is_active`, `idx_markets_volume_7d`.

```sql
-- Highest-volume active market
SELECT id, slug, title, volume_7d, yes_percentage, last_updated
FROM markets WHERE is_active ORDER BY volume_7d DESC LIMIT 10;
```

**Anomaly — stale rows inside a live table:** the highest-volume row in the table
(Russian parliamentary election, $14.49 M 7d) carries
`last_updated = 2026-09-21 12:41:39`, ~13 days old, while the table-wide max is
21:49:07 today. The 15-min job only refreshes rows in its current fetch set, so
markets that have dropped out of the top-100 (or are being read from a stale copy)
keep old timestamps. **`last_updated` is not a reliable "whole table is fresh"
signal — check per-row.** Also note `outcomes_json` is NULL on that row.

---

## Signal & judgement tables

### opportunities

Scanner output (weather mispricing + parlay candidates) written by
`src/backend/extras/opportunity_hunter.py` (`run_opportunity_scan`), triggered by
an APScheduler job every 5 min when `ENABLE_EXTRAS=true` (`config.py:74`, default true).

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `category` | varchar(50) | NOT NULL | — |
| `market_id` | varchar(255) | — | — |
| `title` | text | NOT NULL | — |
| `bracket` | varchar(100) | — | — |
| `true_probability` | double | NOT NULL | — |
| `market_price` | double | NOT NULL | — |
| `edge` | double | NOT NULL | — |
| `expected_value_pct` | double | NOT NULL | — |
| `kelly_fraction_pct` | double | NOT NULL | — |
| `recommendation` | varchar(100) | NOT NULL | — |
| `target_token_id` | text | — | — |
| `target_side` | varchar(10) | NOT NULL | — |
| `target_limit_price` | double | NOT NULL | — |
| `status` | varchar(50) | NOT NULL | — |
| `details_json` | text | — | — |
| `created_at` | timestamp | NOT NULL | `now()` |

**Key:** `opportunities_pkey (id)`.
**Indexes:** `idx_opportunities_edge`, `idx_opportunities_created`, `idx_opportunities_status`.
The counts below are a 2026-10-04 snapshot: 191 rows total, including 105
`WEATHER` and 86 `PARLAY`; none of their `market_id` values resolved to
`markets.id`. On 2026-10-05 the `WEATHER` rows were deleted and the scheduled
opportunity scanner was changed to persist parlays only.

```sql
SELECT category, count(*), max(created_at) FROM opportunities GROUP BY 1 ORDER BY 2 DESC;
```

### predictions

Model predictions (e.g. `predictor='cfb_scanner'`), written by
`src/backend/sports/cfb.py`. Unique per `(predictor, game_id, question)`.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `sport` | varchar(20) | NOT NULL | — |
| `game_id` | varchar(100) | NOT NULL | — |
| `question` | text | NOT NULL | — |
| `predictor` | varchar(50) | NOT NULL | — |
| `probability` | double | NOT NULL | — |
| `market_price` | double | — | — |
| `market_id` | varchar(255) | — | — |
| `game_time` | timestamp | — | — |
| `outcome` | integer | — | — |
| `settled_at` | timestamp | — | — |
| `created_at` | timestamp | NOT NULL | `now()` |

**Key:** `predictions_pkey (id)`. **Unique:** `uq_predictions_pick (predictor, game_id, question)`.
**Indexes:** `idx_predictions_outcome`, `idx_predictions_sport_predictor (sport, predictor)`.
**Freshness:** max 05:13:16.

```sql
SELECT sport, game_id, question, predictor, probability, market_price, game_time
FROM predictions WHERE outcome IS NULL ORDER BY game_time;
```

### alerts

Sport-gap alerts written by `src/backend/sports/alerts.py` (60 s CFB scan).

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `created_at` | timestamp | NOT NULL | `now()` |
| `kind` | varchar(40) | NOT NULL | — |
| `priority` | varchar(10) | NOT NULL | — |
| `sport` | varchar(10) | NOT NULL | — |
| `game_id` | varchar(100) | NOT NULL | — |
| `team` | varchar(100) | NOT NULL | — |
| `title` | text | NOT NULL | — |
| `espn_win_prob` | double | NOT NULL | — |
| `market_price` | double | NOT NULL | — |
| `gap` | double | NOT NULL | — |
| `margin` | integer | NOT NULL | — |
| `detail` | text | — | — |
| `market_slug` | varchar(500) | — | — |
| `delivery` | varchar(200) | NOT NULL | — |
| `status` | varchar(12) | NOT NULL | `'active'` |
| `retracted_at` | timestamp | — | — |
| `retract_note` | text | — | — |

**Key:** `alerts_pkey (id)`. **Indexes:** `idx_alerts_game_team (game_id, team)`, `idx_alerts_created`.
**Freshness:** max 06:08:53.

```sql
SELECT created_at, kind, sport, team, gap, priority, status FROM alerts
WHERE status='active' ORDER BY created_at DESC;
```

---

## State & small tables

### app_state

Single-row key/value store for pipeline state. 1 row.

| Column | Type | Null | Default |
|---|---|---|---|
| `key` | varchar(100) | NOT NULL | — |
| `value` | text | NOT NULL | — |
| `updated_at` | timestamp | NOT NULL | `now()` |

**Key:** `app_state_pkey (key)`. Freshness 21:49:07.

```sql
SELECT key, value, updated_at FROM app_state;
```

### bet_notes

Tagged notes on positions, written by `src/backend/bet_notes.py` / `routes/account.py`.
58 rows.

| Column | Type | Null | Default |
|---|---|---|---|
| `bet_key` | varchar(300) | NOT NULL | — |
| `tag` | varchar(20) | NOT NULL | — |
| `note` | text | — | — |
| `why_ended` | varchar(30) | — | — |
| `updated_at` | timestamp | NOT NULL | `now()` |

**Key:** `bet_notes_pkey (bet_key)`. Freshness 21:43:50.

### program_tiers

Programme ranking by team key. 10 rows.

| Column | Type | Null | Default |
|---|---|---|---|
| `key` | varchar(80) | NOT NULL | — |
| `tier` | integer | — | — |
| `note` | text | — | — |
| `updated_at` | timestamp | NOT NULL | `now()` |

**Key:** `program_tiers_pkey (key)`. Freshness 11:44:53.

### webui_events

Open WebUI relay events, written by `src/backend/routes/webhook.py`. 12 rows.

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | integer | NOT NULL | seq |
| `event_type` | varchar(100) | — | — |
| `user_id` | varchar(200) | — | — |
| `chat_id` | varchar(200) | — | — |
| `model` | varchar(200) | — | — |
| `content` | text | — | — |
| `raw` | text | — | — |
| `created_at` | timestamp | — | `now()` |

**Key:** `webui_events_pkey (id)`. **Indexes:** `ix_webui_events_event_type`, `ix_webui_events_created_at`, `ix_webui_events_chat_id`. Freshness 07:02:49.

---

## Dead / empty tables

### news_articles

**0 rows. The only write path is broken.** The ORM model exists
(`src/backend/models.py`, with `news_articles_url_hash_key UNIQUE (url_hash)` and
indexes on `market_id` / `published_at`), and `GET /api/news/{market_id}` tries to
insert freshly fetched articles **on every request** — but the insert fails:

```
asyncpg.exceptions.DataError: invalid input for query argument $9:
datetime.datetime(2026, 9, 15, 18, 21, 4, ... (tzinfo=utc)
(can't subtract offset-naive and offset-aware datetimes)
[SQL: INSERT INTO news_articles (... published_at ...) ...]
```

Cause: a tz-aware `published_at` is written into `published_at timestamp without
time zone`. Result: `GET /api/news/{market_id}` returns HTTP 500 on every call
(reproduced), so the NewsFeed view is dead. Fix is either strip tzinfo before
insert or migrate the column to `timestamptz`.

---

## Anomalies

1. **`news_articles` insert is broken** → `GET /api/news/{id}` = HTTP 500 always.
   Naive/aware datetime mismatch. Highest-impact data defect in the DB.
2. **At the 2026-10-04 snapshot, opportunities were orphaned** — their `market_id`
   values did not resolve to `markets.id`. The 106 `WEATHER` rows were subsequently
   deleted; the scheduled scanner now persists parlays only.
3. **`game_snapshots` has no uniqueness on game state.** 1,714 rows collapse to
   only **64 distinct `(league, game_id, home_score, away_score)`** states — the
   table is append-every-poll by design, so *repeated identical scores dominate*.
   Any "how many snapshots" count heavily overstates distinct game states. Don't
   treat row count as signal count.
4. **`markets.last_updated` is per-row, not global.** The top-volume market's row
   is 13 days stale while the table max is today (see `markets` above).
5. **`outcomes_json` is NULL** on at least some rows (the top-volume row included),
   so it cannot be relied on for outcome parsing without a null check.
6. **No FK constraints anywhere** — all relations (`price_history.market_id` →
   `markets.id`, `predictions.market_id` → `markets.id`, etc.) are logical only.
   Nothing prevents orphans, and orphans exist (see #2).
7. **Duplicate/overlapping indexes on `news_articles`:** both `ix_news_articles_market_id`
   and `idx_news_market_id` index `market_id`, plus `idx_news_market_published`
   and `idx_news_published_at`. Redundant, harmless while empty, worth collapsing
   if the table ever fills.

---

## UNVERIFIED

- **Exact writer of `price_history`** — inferred from
  `src/backend/tasks/update_markets.py` because its timestamps align to the 15-min
  cycle and `routes/markets.py` reads it; not observed in logs at write time.
- **Exact path that produces runtime `news_articles` INSERT attempts** — no
  persistence writer for `NewsArticle` was found in source, yet the running backend
  attempts the insert. The route was inferred from the error's SQL.
- **Which process writes `predictions` rows** beyond `src/backend/sports/cfb.py` —
  that is the only source hit (`predictor='cfb_scanner'`), but no running service
  was confirmed executing it; rows stopped at 05:13 today.
- **Whether the `ts-london`/`ncaa_*` columns are currently populated** — the sampled
  newest `game_snapshots` row had `ts_score` and `ncaa_score` NULL and only
  `poly_*` + `espn_ms` populated; broader coverage was not measured.
- **`clob_token_ids` semantics** — text column, not inspected in depth.

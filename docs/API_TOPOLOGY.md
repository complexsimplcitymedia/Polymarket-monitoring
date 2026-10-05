# API Topology and Request Paths

How a browser request reaches data, what each hop actually runs, and why the non-obvious
hops exist. Every claim cites a file and line, or a command and its real output. Where the
repository states no reason, the item is marked **INFERRED** or **UNVERIFIED** rather than
guessed at.

Scope: read-only survey. Nothing here has been implemented.

---

## 1. The request path, end to end

A browser client loads the SPA from nginx, and every `/api/*` call is proxied to the FastAPI
backend. The hop chain for a typical read (`GET /api/markets/top50`):

```
browser
  └─ TLS terminated by the host edge (Caddy, systemd unit caddy.service on VM4)
      └─ :5173  polymarket-frontend  (nginx:alpine)          docker-compose.yml:106-119
          └─ location /api/  →  proxy_pass http://backend:8000/api/   docker/nginx/default.conf:35-43
              └─ :8000  polymarket-backend  (uvicorn)         Dockerfile.backend:26
                  └─ /api/markets/top50                        src/backend/main.py:91
                      └─ SELECT … FROM markets WHERE is_active ORDER BY volume_7d   routes/markets.py:170-184
                          └─ PostgreSQL 17 (pgvector) :5432   docker-compose.yml:2-21
```

Evidence for each hop:

- **nginx serves the SPA and owns the proxy.** `Dockerfile.frontend` builds the Vite bundle
  (`npm run build`) and copies `docker/nginx/default.conf` into `nginx:alpine`
  (`Dockerfile.frontend:18-22`). The API location is a prefix proxy
  (`docker/nginx/default.conf:35-36`).
- **The frontend calls relative URLs.** Hooks request `/api/...` with no host
  (`src/frontend/src/hooks/useMarkets.ts:12`, `useNews.ts:24`, `useWhales.ts:28`), so in the
  container the browser hits nginx on the same origin and nginx forwards to `backend:8000` by
  Docker-DNS service name.
- **The backend is uvicorn on :8000**, `--host 0.0.0.0` inside the container
  (`Dockerfile.backend:26`), published on the host as `127.0.0.1:8001` and `100.110.82.54:8001`
  (`docker-compose.yml:36-37`).
- **Verified reachable:** `curl http://127.0.0.1:5173/api/health` → 200, `Content-Type:
  application/json`; `curl http://127.0.0.1:8001/docs` → 200 (Swagger UI). The live OpenAPI
  document at `http://127.0.0.1:8001/openapi.json` reports **52 paths / 53 operations**.

Request paths that do **not** follow the nginx → backend chain:

- **`/vnc/`** proxies to a tablet's noVNC server on the tailnet, `http://100.110.82.108:5800/`
  (`docker/nginx/default.conf:47-48`), with `Content-Type` rewritten by a `map` because the
  device sends none and `nosniff` would otherwise force `text/plain`
  (`docker/nginx/default.conf:7-21,49-50`).
- **`/vnc/websockify`** proxies to `http://100.110.82.54:6900` (`default.conf:64-65`), a
  websockify bridge started by host systemd at `100.110.82.54:6900 → 100.110.82.108:5900`
  (`scripts/sockify-tablet.service:7`). The device runs raw VNC on :5900, which is not a
  WebSocket, so websockify wraps it.
- **`/docs`, `/openapi.json`, `/redoc` are not covered by `location /api/`.** They fall into
  `location /` and are rewritten to the SPA's `index.html` (`default.conf:30-32`). Verified:
  `curl http://127.0.0.1:5173/docs` returns the SPA HTML (`<title>Polymarket Intelligence
  | Institutional Prediction Terminal</title>`), not Swagger. The backend's own `/docs` is
  still exposed at `:8001` (verified 200).
- **One component bypasses nginx in production.** `DebateFloor.tsx:92` reads
  `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'` and fetches the debate route
  directly (`DebateFloor.tsx:112`). No `VITE_API_BASE_URL` is set in the repo (grep returns one
  hit, the declaration itself), so the built SPA falls back to `http://localhost:8000`,
  which does **not** resolve for a remote browser. See weakness W4.

---

## 2. Every endpoint the backend exposes

Read from `src/backend/routes/*.py`, `src/backend/extras/routes/*.py`, and the app-level routes
in `src/backend/main.py`, and reconciled against the live `/openapi.json` (53 operations).
"Cache" is the mechanism the handler actually uses.

### App-level (`main.py`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 1 | GET | `/` | static dict | none (`main.py:121`) |
| 2 | GET | `/api/health` | static dict | none (`main.py:111`) |

### Markets — prefix `/api/markets` (`routes/markets.py:29`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 3 | GET | `/top50` | DB `markets` + `app_state` | none; reads a table refreshed every 15 min (`markets.py:156`, `tasks/update_markets.py:152-158`) |
| 4 | GET | `/status` | DB `markets`, `app_state` | none (`markets.py:205`) |
| 5 | GET | `/{market_id}/history` | DB `markets` → CLOB `/prices-history` | none (`markets.py:268,336`) |
| 6 | GET | `/{market_id}/stats` | DB + CLOB ×2 in parallel | none (`markets.py:409,445-448`) |
| 7 | GET | `/{market_id}` | DB; **on miss** gamma-api `get_market_by_slug`, then **DB write** | none (`markets.py:684,708,764-767,799-831`) |
| 8 | GET | `/{market_id}/trades` | data-api `/trades`, then per-wallet `/positions`, `/closed-positions`, `/value` | in-memory `user_stats_cache`, 300 s (`markets.py:840`; `cache.py:75`) |
| 9 | GET | `/{market_id}/holders` | data-api `/holders`, then per-holder fan-out (1 call cached, 3 uncached) | same 300 s in-memory cache (`markets.py:1146,1195,1212-1276`) |

### News — prefix `/api/news` (`routes/news.py:16`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 10 | GET | `/{market_id}` | DB `news_articles`; **on empty** NewsAPI `everything`/`top-headlines`, then DB write | DB rows persist; cleanup daily (`news.py:19,47-84`; `tasks/update_markets.py:161-167`) |
| 11 | POST | `/{market_id}/refresh` | NewsAPI (forced) | none (`news.py:93`) |

### Users — prefix `/api/users` (`routes/users.py:20`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 12 | GET | `/analytics?query=` | gamma-api (resolve) + data-api `/positions`, `/closed-positions` (paginated) | none (`users.py:564`) |

### Sports scanners — prefix `/api/scanners` (`routes/sports.py:25`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 13 | GET | `/mlb/board` | MLB Stats API | 300 s in-memory (`sports/mlb.py:27,278`) |
| 14 | GET | `/mlb/team/{team_id}` | MLB Stats API | 300 s (`sports/mlb.py`) |
| 15 | GET | `/nfl/board` | ESPN site.api | 300 s (`sports/nfl.py:20,134`) |
| 16 | GET | `/nfl/team/{team_id}` | ESPN | 300 s |
| 17 | GET | `/nba/board` | ESPN | 300 s (`sports/nba.py:21,129`) |
| 18 | GET | `/nba/team/{team_id}` | ESPN | 300 s |
| 19 | GET | `/cfb/live` | ESPN live scoreboard; writes prediction ledger | none (`sports.py:104`) |

### Account — prefix `/api/account` (`routes/account.py:18`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 20 | GET | `/summary` | Polymarket US account service; live scores attached per request | 60 s in-process (`account.py:24,153`) |
| 21 | GET | `/bets` | account service + DB `bet_notes` + live scores | 60 s account cache (`routes/account.py:51`) |
| 22 | PUT | `/bets/note` | DB `bet_notes` write | none |

### MLB / Football team tables

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 23 | GET | `/api/mlb/teams` | ESPN + MLB stats | 1800 s (`sports/mlb_teams.py:29,210`) |
| 24 | GET | `/api/football/{league}/teams` | ESPN | 1800 s (`sports/football_teams.py:22,239`) |

### Tiers — prefix `/api/tiers` (`routes/tiers.py:13`)

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 25 | GET | `/{league}` | DB `program_tiers` | none |
| 26 | PUT | `/{league}/{team_id}` | DB `program_tiers` write | none |

### Scores / Alerts / AI / Webhooks

| # | Method | Path | Data source | Cache |
|---|--------|------|-------------|-------|
| 27 | GET | `/api/scores/match` | ESPN scoreboards | via `live_scores` in-memory |
| 28 | GET | `/api/alerts` | DB `alerts` + ESPN scoreboards | none (`routes/alerts.py:21`) |
| 29 | POST | `/api/alerts/test-email` | SMTP / Hostinger API | none |
| 30 | GET | `/api/ai/status` | settings flag | none |
| 31 | GET | `/api/ai/models` | NanoGPT API | none |
| 32 | GET | `/api/ai/games` | DB `game_snapshots` (last 20 min) | none (`routes/ai.py:39`) |
| 33 | POST | `/api/ai/ask` | DB context + NanoGPT LLM | none (`routes/ai.py:50`) |
| 34 | POST | `/api/webhooks/openwebui` | DB `webui_events` write | none |
| 35 | GET | `/api/webhooks/openwebui/recent` | DB `webui_events` | none |

### Extras — mounted when `ENABLE_EXTRAS=true` (`main.py:105-108`, `extras/__init__.py:11-16`)

Trading, prefix `/api/trading` (`extras/routes/trading.py:15`):

| # | Method | Path | Data source |
|---|--------|------|-------------|
| 36 | GET | `/status` | CLOB + wallet balance |
| 37 | GET | `/orderbook/{token_id}` | CLOB live book |
| 38 | POST | `/order` | CLOB order submission (writes to chain unless `dry_run`) |
| 39 | POST | `/parlay` | CLOB multi-leg |
| 40 | GET | `/orders` | CLOB open orders |
| 41 | DELETE | `/order/{order_id}` | CLOB cancel |
| 42 | DELETE | `/orders` | CLOB cancel all |
| 43 | POST | `/execute-opportunity/{opportunity_id}` | DB `opportunities` + CLOB |
| 44 | GET | `/autotrade` | settings |
| 45 | POST | `/autotrade/toggle` | **mutates the live `settings` singleton in process** |

Debate, prefix `/api/debate`:

| # | Method | Path | Data source |
|---|--------|------|-------------|
| 46 | POST | `/{market_id}` | DB `markets` + LLM debate graph (`extras/routes/debate.py:454`) |

Extras scanners, prefix `/api/scanners` — **collides with sports.py's prefix**
(`extras/routes/scanners.py:23` vs `routes/sports.py:25`):

| # | Method | Path | Data source |
|---|--------|------|-------------|
| 47 | GET | `/weather/cities` | static city index |
| 48 | GET | `/weather/matrix` | NOAA / Open-Meteo + DB `weather_history` |
| 49 | GET | `/weather` | NOAA/HRRR vs CLOB |
| 50 | GET | `/parlays` | Polymarket markets |
| 51 | POST | `/parlays/analyze` | LLM parlay agent |
| 52 | GET | `/opportunities` | DB `opportunities` |
| 53 | POST | `/run` | triggers full scan (heavy, synchronous) |

**Total: 53 operations across 52 paths** — matches live `/openapi.json` exactly.

---

## 3. Why each non-obvious hop exists

Each item states the evidence in the repo, and whether the rationale is stated in code,
inferred, or unverifiable.

### 3.1 Why nginx proxies `/api/` instead of the browser hitting `:8001`

- **Stated in config:** the location is a same-origin prefix proxy
  (`docker/nginx/default.conf:35-36`). The frontend hooks use relative `/api/...` paths
  (`useMarkets.ts:12`), so a single origin serves both the SPA and the API.
- **Effect (verifiable):** the backend's `CORS_ORIGINS` default is `http://localhost:5173`
  (`config.py:83`); routing API calls through the same origin the SPA was loaded from means
  CORS is not on the critical path for normal use.
- **Why `:8001` is not called directly — INFERRED, not stated.** The backend *is* published on
  `:8001` (`docker-compose.yml:36-37`), so direct calls are possible; the single-origin design
  is the reason normal traffic does not use it. The repository does not say this in a comment.

### 3.2 Why the `ts-london` sidecar exists, and what `network_mode: service:ts-london` does

- **The rationale is stated in the compose comment:** "the ticks worker shares this container's
  network, so only its traffic exits through London" (`docker-compose.yml:56`).
- **Mechanism, evidence:** `ts-london` runs `tailscale/tailscale:latest` with
  `--exit-node=100.110.82.10` (the London exit node) and `NET_ADMIN` +
  `/dev/net/tun` (`docker-compose.yml:57-75`). `ticks` is declared
  `network_mode: "service:ts-london"` (`docker-compose.yml:85`). Verified live:
  `docker inspect polymarket-ticks` reports `NetworkMode = container:5fc52899…` (the ts-london
  container), and `docker exec polymarket-ts-london tailscale status` shows
  `100.110.82.8 polymarket-ticks` up.
- **What it does to the traffic:** because ticks shares ts-london's network namespace, *all* of
  ticks' egress goes through the Tailscale interface and out the London exit node. ticks
  therefore has no port publishable of its own and no `ports:` block
  (`docker-compose.yml:77-90`). No other service shares this namespace, so only ticks' traffic
  is routed through London.
- **Why London — the repo states the what, not the why.** `src/ingest/ticks.js:2` says the
  worker "is meant to run in London, next to the exchange." This is the closest thing to a
  rationale; the specific latency requirement is **not documented** and is left as-is here.

### 3.3 Why `probe` and `ingest` are separate services

- **`ingest` (Node)** is the live layer: poll live games and prices, write a reading to
  `game_snapshots` when something changed (`src/ingest/index.js:1`), with per-league ESPN/theScore/
  MLB/NCAAsource arbitration (`index.js:111-124`).
- **`probe` (Python)** is a measurement layer, not a data producer for the UI: every 60 s it
  times each score source, records status, bytes, cache headers, live-game count and total
  points into `source_probes` (`src/backend/probe.py:1-5,20,116-135`).
- **The split is defensible from the code**, but the repo does **not** state "why separate
  processes" in a comment. Read plainly: probe writes nothing the app serves; its `SOURCES`
  list (`probe.py:66-76`) overlaps almost entirely with what ingest already fetches
  (`ingest/espn.js`, `ingest/thescore.js`, `ingest/mlb.js`). **INFERRED:** they are separate so a
  measurement loop cannot add load or failure to the live writer, and so probe survives
  independently. **UNVERIFIED:** the repository contains no doc stating this intent.
- Both `probe` and `ticks` reuse images built from other Dockerfiles
  (`docker-compose.yml:80,93` — `Dockerfile.ingest` and `Dockerfile.backend` respectively), so
  there is one image per language but three running services.

### 3.4 Why every binding is a tailnet IP rather than `0.0.0.0`

- Every published port is paired `127.0.0.1` **and** `100.110.82.54` (the tailnet address):
  db `docker-compose.yml:11-12`, backend `:36-37`, frontend `:116-117`. Nothing binds
  `0.0.0.0`.
- **Effect:** the services are reachable only from the host loopback and the Tailscale network;
  they are not on the public interface. The public path is the host Caddy unit
  (`caddy.service`, independently verified active), which terminates TLS — as the nginx config
  itself states (`docker/nginx/default.conf:45-46`).
- **Why — INFERRED:** the pairing is a deliberate "host-local plus tailnet-only" exposure.
  The repository states no policy document for this; the pattern is consistent across all
  three services, which is the evidence.

### 3.5 The `/vnc/` and `/vnc/websockify` paths

- Rationale is stated in the config comments: nginx serves the tablet's noVNC page/assets and
  rewrites `Content-Type` because the device sends none and `nosniff` would force `text/plain`
  (`default.conf:7,45-50`); the WebSocket tunnel goes to a websockify bridge because the
  tablet's `:5900` is raw VNC, not WebSocket (`default.conf:62-65`). The bridge is the host
  systemd unit `scripts/sockify-tablet.service` (verified active), mapping
  `:6900 → tablet :5900`.
- **Note:** the websockify target in nginx is `100.110.82.54:6900` — the *host's own* tailnet
  IP — even though nginx runs inside a container. This works because the host's tailnet IP is
  routable from the container's bridge network on this host. **INFERRED** (no comment states
  the reliance).

---

## 4. Topology weaknesses

Ordered by severity. Each cites evidence and, where relevant, how to confirm it.

### W1 — `mlb-watch` runs but is not in the compose file (unexplained drift)

`polymarket-mlb-watch` is live on `100.110.82.54:6901`, image `polymarket-mlbwatch:latest`,
`Up` (verified via `docker ps`). It carries compose labels
`com.docker.compose.project=polymarket-monitoring`,
`…service=mlb-watch`, `…config_files=/home/wolf/Polymarket-monitoring/docker-compose.yml`.
But that file defines only **7 services** (`db, backend, frontend, ingest, probe, ts-london,
ticks` — verified via `docker compose config --services`), it is byte-identical to `HEAD`
(`git diff` clean), and `git log -S"mlb-watch" -- docker-compose.yml` returns nothing. So the
running container was launched from a compose definition that no longer exists in the file or
in history. On the next `docker compose up` this container is orphaned and will be stopped or
removed. **The reason is UNVERIFIED** — do not invent one. Change: either re-add the service
with its build/Dockerfile, or record its retirement, so the running state matches the declared
state.

### W2 — The backend has no authentication on any route

Grep for `Depends(get_current)`, `HTTPBearer`, `Security(`, `APIKeyHeader` across
`src/backend/` returns **nothing**. All 53 operations are unauthenticated, including the
mutating and money-moving ones: `POST /api/trading/order`, `POST /api/trading/execute-opportunity`,
`DELETE /api/trading/orders`, `POST /api/trading/autotrade/toggle`. Any host that can reach
`:8001` (or the tailnet IP) can place or cancel orders. The only gate is `AuthGate.tsx`, a
**frontend-only** component that stores a token in the client and never checks it server-side
(`AuthGate.tsx:12-14`). Change: require an auth dependency on the trading, account and webhook
routers at minimum, and enforce it in FastAPI, not in the SPA.

### W3 — `/api/scanners` is served by two routers with overlapping ownership

`routes/sports.py:25` and `extras/routes/scanners.py:23` both declare
`APIRouter(prefix="/api/scanners", …)`. They do not collide today (different sub-paths), but
the namespace is split across two modules with different lifetimes: the sports half is always
mounted (`main.py:94`, `:99` for scores, etc.), the extras half only when `ENABLE_EXTRAS`
(`main.py:105-108`). Two frontend hooks assume the extras half exists
(`useScanners.ts:75,87`). Change: give the extras scanners a distinct prefix (for example
`/api/extras/scanners`) or fold them into one router, so the API surface does not change shape
when a feature flag flips.

### W4 — One frontend component bypasses nginx and points at `localhost:8000`

`DebateFloor.tsx:92` builds its base from `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'`
and fetches the debate route directly (`:112`). No `VITE_API_BASE_URL` is defined anywhere in
the repo. In the containerised deployment every other hook uses same-origin relative paths, so
the built SPA's debate call resolves to the *browser user's* `localhost:8000`, which is not the
API. Change: use a relative `/api/debate/...` path like the other hooks.

### W5 — Unbounded, unthrottled external fan-out on the whale/holder endpoints

`GET /markets/{id}/trades?include_user_stats=true` and `GET /markets/{id}/holders` fetch
data-api per wallet. trades fans out with a semaphore of 10 (`markets.py:1055`); **holders has
no semaphore at all** — it issues one `/positions` call for every cached address and three
calls per uncached address, all at once (`markets.py:1282-1287`). Neither sets a concurrency cap
tied to the upstream's rate limit, and neither degrades gracefully if data-api throttles. The
only relief is a 300 s in-memory cache (`cache.py:75`), which is per-process and disappears on
restart. Change: bound the holders fan-out with a semaphore, cap addresses processed per
request or page the enrichment, and honour back-pressure on 429.

### W6 — Inconsistent error-handling contracts across routers

The same class of failure returns different codes and shapes depending on the module:

- `markets.py` swallows upstream failure and returns `[]` or a single-point history
  (`markets.py:265,1137,1143,1354`) — a client cannot tell "no trades" from "data-api down".
- `account.py` maps unconfigured to **503** and read failure to **502** (`account.py:37,40`).
- `ai.py` maps to **503 / 502 / 504** by failure class (`ai.py:56-62`).
- `sports.py` and the extras scanners collapse everything to **500** with the raw exception
  string embedded (`sports.py:39,52,65,76,89,99`; `scanners.py:43,58,70,81,93`), which also
  leaks internal detail.
- `scores.py` silently returns `{"game": null}` (`scores.py:17-20`).
Change: settle one convention — validation 4xx, upstream 502/504, unconfigured 503, and a
logged-and-empty 200 only for genuinely optional enrichment, never with the exception text in
the body.

### W7 — `POST /api/trading/autotrade/toggle` mutates the shared settings singleton

The handler writes `settings.AUTO_TRADE_ENABLED`, `AUTO_TRADE_DRY_RUN`, `AUTO_TRADE_MAX_BET`,
`AUTO_TRADE_MIN_EV` directly on the live settings object (`extras/routes/trading.py:74-91`).
Because `get_settings()` is `@lru_cache`d and imported as a module singleton
(`config.py:96-102`), this changes the running process's behaviour for **all** callers and is
lost on restart, with no audit trail, no persistence, and no auth (see W2). The scheduler that
consumes these flags (`tasks/update_markets.py:196-205`) runs in the same process. Change: make
autotrade configuration explicit persisted state with an audit log, not a live in-memory
mutation.

### W8 — Single points of failure, by construction

- **One Postgres container** backs every stateful path (`docker-compose.yml:2-21`); backend
  and both Node workers point at it. No replica, no read/write split. If it is down, the whole
  app is read-only or down.
- **One backend process** holds the APScheduler jobs (`main.py:58-60`,
  `tasks/update_markets.py:139-207`) and the only in-memory caches (`cache.py`, and the sports
  TTL caches). Restarting the backend restarts the market refresh, the CFB scan, the
  opportunity scan, and drops all caches. A second replica would run duplicate schedulers —
  the job set is not guarded for multi-instance.
- **`ticks` depends on `ts-london`**, which depends on a Tailscale auth key and a London exit
  node (`docker-compose.yml:66-69`). Lose the key or the exit node and the real-time price lane
  stops silently — there is no healthcheck on `ticks` or `ts-london` (`docker ps` shows neither
  as healthy; only `db` is `(healthy)`).
- **`ingest` and `probe`** likewise have no healthcheck (`docker-compose.yml:41-54,92-104`).

### W9 — Duplicated external-API responsibility across services

The same upstreams are polled by several independent processes with independent caches:

- **ESPN** is fetched by `ingest` (`ingest/espn.js`), by `probe`
  (`probe.py:67,71,74`), and by the backend scanners (`sports/espn_common.py:17`).
- **theScore / MLB Stats** overlap between `ingest` and `probe` (`probe.py:66-76`).
- **gamma-api** is called by the market refresh (`tasks/update_markets.py:31`), by
  `markets.py:708,799` on the read path, by `ingest` (`index.js:13`), by `ticks`
  (`ticks.js:11`), and by `users.py:22`.
This is not wrong per se — `ingest`'s comment says the parallel-source design is deliberate to
spread load across providers (`index.js:111-112`) — but there is no shared cache or budget, so
per-source request rate is the sum of every caller's. Change: name one owner per upstream (or
introduce a shared fetch/cache tier) and derive the expected request rate from it.

### W10 — Unbounded external calls without timeouts everywhere

Some calls set no timeout and rely on library defaults, and several are unbounded in count:
`fetch_price_history_from_clob` uses a 10 s timeout but is called twice per stats request and
once per history request with no caching (`markets.py:251,336,446-447`); `users.py` paginates
`_fetch_all_positions` up to `limit=2000` with no timeout visible in the grep
(`users.py:314`); `POST /api/scanners/run` runs the entire weather+parlay scan synchronously in
the request (`scanners.py:105-112`, `tasks/update_markets.py:196-205`). Change: set explicit
timeouts on every `httpx.AsyncClient` call site, cache CLOB history for the TTL of its
fidelity, and move the full scan behind a job that returns immediately with a task id.

### W11 — CORS is permissive for a single-origin deployment

`allow_origins=settings.cors_origins_list`, `allow_credentials=True`, `allow_methods=["*"]`,
`allow_headers=["*"]` (`main.py:82-88`), with the default origin list being
`http://localhost:5173,http://127.0.0.1:5173` (`config.py:83`). Since normal traffic is
same-origin via nginx, the CORS layer is only exercised by direct cross-origin callers (such as
W4's `localhost:8000`). `allow_credentials=True` with a wildcarded method/header set is broader
than needed. Change: drop credentials and the wildcard methods if the same-origin proxy is the
only supported path, or pin origins explicitly.

---

## 5. Prioritized improvements

Recommend-only. Each item: the evidence for the problem, then the concrete change.

| Priority | Problem | Evidence | Change |
|---|---|---|---|
| P0 | Unauthenticated money-moving routes | no auth dependency anywhere in `src/backend/`; `extras/routes/trading.py:57,126,104` | Add a FastAPI auth dependency to trading/account/webhook routers; enforce server-side (`AuthGate.tsx` is client-only). |
| P0 | Orphaned `mlb-watch` container will be reaped | live container vs `docker compose config --services` (7 services) and clean `git diff` | Re-declare the service in `docker-compose.yml`, or formally retire it and remove the running container in a controlled step. |
| P1 | `autotrade/toggle` mutates the live settings singleton | `extras/routes/trading.py:74-91`; `config.py:96-102` | Persist autotrade config (DB or file), reload deliberately, and log every change. |
| P1 | Unbounded holders fan-out | `routes/markets.py:1282-1287` (no semaphore; trades uses one at `:1055`) | Bound concurrency, page enrichment, honour 429, and cap per-request work. |
| P1 | `/api/scanners` served by two routers | `routes/sports.py:25` vs `extras/routes/scanners.py:23`; flag at `main.py:105` | Rename the extras prefix (`/api/extras/scanners`) or merge into one router. |
| P2 | Debate UI bypasses the proxy | `DebateFloor.tsx:92,112`; no `VITE_API_BASE_URL` defined | Fetch relative `/api/debate/...` like the other hooks. |
| P2 | Inconsistent error contracts + detail leakage | `sports.py:39-99`, `scanners.py:43-93` (500 + raw exception) vs `account.py:37-40` (503/502) vs `markets.py:265` (silent `[]`) | Standardise status codes; never echo the raw exception; log server-side. |
| P2 | No healthchecks on `ingest`, `ticks`, `probe`, `ts-london`, `backend`, `frontend` | `docker-compose.yml` sets `healthcheck` only for `db:17-21` | Add HTTP/process healthchecks and wire `depends_on: condition: service_healthy`. |
| P2 | Scheduler and caches are single-instance-bound | `main.py:58-60`; `tasks/update_markets.py:139-207`; `cache.py:75` | If scaling the backend, elect a scheduler leader or move jobs to a dedicated worker, and externalise the cache (Redis or a DB table). |
| P3 | Overlapping upstream polling with independent budgets | `probe.py:66-76` vs `ingest/espn.js`/`thescore.js`/`mlb.js` vs `sports/espn_common.py:17`; gamma-api called from 5 modules | Pick one owner per upstream or add a shared cache/budget layer. |
| P3 | Synchronous heavy endpoints | `scanners.py:105-112` (`/run` scans everything in-request) | Return a task id and run the scan in the scheduler. |
| P3 | Permissive CORS | `main.py:82-88`; `config.py:83` | Drop credentials + wildcard methods, or pin origins, given same-origin proxying. |
| P3 | CLOB history uncached per request | `routes/markets.py:336,446-447` | Cache history for its fidelity TTL (15/60/240/1440 min). |

---

## 6. Unverified

- **Why `ticks` must run in London.** Only `ingest/ticks.js:2` ("meant to run in London, next to
  the exchange") is stated; the concrete latency target is absent.
- **Why `probe` is a separate process** rather than a mode of `ingest`. The separation is
  visible; the intent comment is absent.
- **The provenance of the `mlb-watch` container.** Not in the compose file, not in git history;
  the compose labels imply the project, but the definition is gone.
- **Whether the `127.0.0.1` + tailnet dual binding is a codified policy** or an emergent habit.
- **Whether `POST /api/auth/oauth/{provider}` is served.** `AuthGate.tsx:20` calls it; the live
  route table has no `/api/auth/...` path, and `curl :5173/api/auth/oauth/google` returns 404.

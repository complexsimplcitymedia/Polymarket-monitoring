import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios, { type AxiosError } from 'axios'
import {
    Activity,
    RefreshCw,
    Play,
    Pause,
    Wifi,
    WifiOff,
    Clock,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Trash2,
    Gauge,
    Server,
    RotateCcw,
    Save,
    Globe,
} from 'lucide-react'
import { useMarketStore, type LatencyEndpoints } from '../stores/marketStore'

interface EndpointDef {
    id: string
    method: 'GET' | 'POST'
    path: string
    label: string
    needsMarket: boolean
}

interface ProbeResult {
    status: number | null
    durationMs: number
    ok: boolean
    error: string | null
    timestamp: number
}

interface EndpointRow {
    def: EndpointDef
    last: ProbeResult | null
    history: ProbeResult[]
}

interface RouteProbe {
    label: string
    key: keyof LatencyEndpoints
    testPath: string
    last: ProbeResult | null
}

const ENDPOINTS: EndpointDef[] = [
    { id: 'health', method: 'GET', path: '/api/health', label: 'Health Check', needsMarket: false },
    { id: 'markets_top50', method: 'GET', path: '/api/markets/top50', label: 'Markets Top 50', needsMarket: false },
    { id: 'markets_status', method: 'GET', path: '/api/markets/status', label: 'Markets Status', needsMarket: false },
    { id: 'market_detail', method: 'GET', path: '/api/markets/__MARKET_ID__', label: 'Market Detail', needsMarket: true },
    { id: 'market_history', method: 'GET', path: '/api/markets/__MARKET_ID__/history?timeframe=24H', label: 'Market History (24H)', needsMarket: true },
    { id: 'market_stats', method: 'GET', path: '/api/markets/__MARKET_ID__/stats', label: 'Market Stats', needsMarket: true },
    { id: 'market_trades', method: 'GET', path: '/api/markets/__MARKET_ID__/trades?min_volume=1000&days=1', label: 'Market Trades', needsMarket: true },
    { id: 'market_holders', method: 'GET', path: '/api/markets/__MARKET_ID__/holders', label: 'Market Holders', needsMarket: true },
    { id: 'news', method: 'GET', path: '/api/news/__MARKET_ID__?limit=10', label: 'News Feed', needsMarket: true },
    { id: 'sports_mlb', method: 'GET', path: '/api/scanners/mlb/board', label: 'MLB Board', needsMarket: false },
    { id: 'sports_cfb', method: 'GET', path: '/api/scanners/cfb/live', label: 'CFB Live', needsMarket: false },
    { id: 'sports_nfl', method: 'GET', path: '/api/scanners/nfl/board', label: 'NFL Board', needsMarket: false },
    { id: 'sports_nba', method: 'GET', path: '/api/scanners/nba/board', label: 'NBA Board', needsMarket: false },
    { id: 'account_summary', method: 'GET', path: '/api/account/summary', label: 'Account Summary', needsMarket: false },
    { id: 'polymarket_status', method: 'GET', path: '/api/status/polymarket', label: 'Polymarket Status', needsMarket: false },
    { id: 'webhook_recent', method: 'GET', path: '/api/webhooks/openwebui/recent', label: 'OpenWebUI Recent', needsMarket: false },
]

const AUTO_INTERVAL_MS = 10000
const HISTORY_LIMIT = 20

const FALLBACK_CONDITION = '0xeb26070a9c65e6f7967ef0ab7ab9ae3bdb2728b814e559c6b8557a6e5db301b6'

const ROUTES: RouteProbe[] = [
    { label: 'CLOB REST (trade)', key: 'trade', testPath: '/markets', last: null },
    { label: 'Data API v2', key: 'data', testPath: `/v2/trades?condition=${FALLBACK_CONDITION}&limit=1`, last: null },
    { label: 'Gamma events', key: 'gamma', testPath: '/events?active=true&limit=1', last: null },
    { label: 'ESPN CFB', key: 'espnCfb', testPath: '/scoreboard?limit=5', last: null },
    { label: 'ESPN NFL', key: 'espnNfl', testPath: '/scoreboard?limit=5', last: null },
    { label: 'MLB Stats API', key: 'mlbStats', testPath: '/schedule?sportId=1&limit=1', last: null },
    { label: 'theScore', key: 'theScore', testPath: '/ncaaf/events/current', last: null },
]

export function LatencyPanel() {
    const [rows, setRows] = useState<EndpointRow[]>(() =>
        ENDPOINTS.map((def) => ({ def, last: null, history: [] }))
    )
    const [marketId, setMarketId] = useState<string | null>(null)
    const [isProbing, setIsProbing] = useState(false)
    const [autoRefresh, setAutoRefresh] = useState(true)
    const abortRef = useRef<AbortController | null>(null)

    const latencyEndpoints = useMarketStore((s) => s.latencyEndpoints)
    const setLatencyEndpoints = useMarketStore((s) => s.setLatencyEndpoints)
    const resetLatencyEndpoints = useMarketStore((s) => s.resetLatencyEndpoints)
    const [routeInputs, setRouteInputs] = useState<LatencyEndpoints>(latencyEndpoints)
    const [routeResults, setRouteResults] = useState<RouteProbe[]>(ROUTES)

    const resolvePath = useCallback(
        (path: string) => {
            if (!path.includes('__MARKET_ID__')) return path
            return path.replace(/__MARKET_ID__/g, encodeURIComponent(marketId || 'none'))
        },
        [marketId]
    )

    const probeOne = useCallback(async (def: EndpointDef): Promise<ProbeResult> => {
        const start = performance.now()
        const path = resolvePath(def.path)
        try {
            const response = await axios({
                method: def.method,
                url: path,
                timeout: 20000,
                signal: abortRef.current?.signal,
            })
            const durationMs = Math.round(performance.now() - start)
            return {
                status: response.status,
                durationMs,
                ok: response.status >= 200 && response.status < 300,
                error: null,
                timestamp: Date.now(),
            }
        } catch (err) {
            const durationMs = Math.round(performance.now() - start)
            const axiosErr = err as AxiosError
            const status = axiosErr.response?.status ?? null
            const error = axiosErr.message || 'Unknown error'
            return {
                status,
                durationMs,
                ok: false,
                error,
                timestamp: Date.now(),
            }
        }
    }, [resolvePath])

    const probeAll = useCallback(async () => {
        if (isProbing) return
        setIsProbing(true)
        abortRef.current = new AbortController()

        if (!marketId) {
            try {
                const res = await axios.get<{ markets?: { id: string; condition_id?: string }[] }>('/api/markets/top50', {
                    timeout: 15000,
                    signal: abortRef.current.signal,
                })
                const first = res.data?.markets?.[0]
                if (first) {
                    setMarketId(first.id)
                    if (first.condition_id) {
                        setRouteResults((prev) =>
                            prev.map((r) =>
                                r.key === 'data'
                                    ? { ...r, testPath: `/v2/trades?condition=${first.condition_id}&limit=1` }
                                    : r
                            )
                        )
                    }
                }
            } catch {
                // leave marketId null, templated endpoints will fail cleanly
            }
        }

        const results = await Promise.all(
            rows.map(async (row) => {
                const result = await probeOne(row.def)
                return { defId: row.def.id, result }
            })
        )

        setRows((prev) =>
            prev.map((row) => {
                const found = results.find((r) => r.defId === row.def.id)
                if (!found) return row
                const nextHistory = [...row.history, found.result].slice(-HISTORY_LIMIT)
                return { ...row, last: found.result, history: nextHistory }
            })
        )

        setIsProbing(false)
        abortRef.current = null
    }, [isProbing, marketId, probeOne, rows])

    const probeRoutes = useCallback(async () => {
        const next = await Promise.all(
            routeResults.map(async (r) => {
                const base = routeInputs[r.key]
                const url = `${base.replace(/\/$/, '')}${r.testPath}`
                const start = performance.now()
                try {
                    const res = await axios.get(url, { timeout: 15000 })
                    return {
                        ...r,
                        last: {
                            status: res.status,
                            durationMs: Math.round(performance.now() - start),
                            ok: res.status >= 200 && res.status < 300,
                            error: null,
                            timestamp: Date.now(),
                        },
                    }
                } catch (err) {
                    const axiosErr = err as AxiosError
                    return {
                        ...r,
                        last: {
                            status: axiosErr.response?.status ?? null,
                            durationMs: Math.round(performance.now() - start),
                            ok: false,
                            error: axiosErr.message,
                            timestamp: Date.now(),
                        },
                    }
                }
            })
        )
        setRouteResults(next)
    }, [routeInputs, routeResults])

    useEffect(() => {
        probeAll()
        probeRoutes()
    }, []) // initial probe on mount

    useEffect(() => {
        if (!autoRefresh) return
        const id = setInterval(() => {
            probeAll()
            probeRoutes()
        }, AUTO_INTERVAL_MS)
        return () => clearInterval(id)
    }, [autoRefresh, probeAll, probeRoutes])

    const handleManualRefresh = () => {
        if (isProbing) return
        probeAll()
        probeRoutes()
    }

    const clearHistory = () => {
        setRows((prev) => prev.map((row) => ({ ...row, last: null, history: [] })))
        setRouteResults((prev) => prev.map((r) => ({ ...r, last: null })))
    }

    const handleSaveRoutes = () => {
        setLatencyEndpoints(routeInputs)
    }

    const handleResetRoutes = () => {
        resetLatencyEndpoints()
        setRouteInputs(latencyEndpoints)
    }

    useEffect(() => {
        setRouteInputs(latencyEndpoints)
    }, [latencyEndpoints])

    const stats = useMemo(() => {
        const lastResults = rows.map((r) => r.last).filter(Boolean) as ProbeResult[]
        const okCount = lastResults.filter((r) => r.ok).length
        const failCount = lastResults.length - okCount
        const avg = lastResults.length
            ? Math.round(lastResults.reduce((a, b) => a + b.durationMs, 0) / lastResults.length)
            : 0
        const max = lastResults.length ? Math.max(...lastResults.map((r) => r.durationMs)) : 0
        return { okCount, failCount, avg, max, total: lastResults.length }
    }, [rows])

    const statusColor = (ok: boolean | null) => {
        if (ok === null) return 'text-slate-500'
        return ok ? 'text-emerald-400' : 'text-rose-400'
    }

    return (
        <div className="max-w-[1600px] mx-auto space-y-6">
            {/* Header Card */}
            <section className="glass-card rounded-2xl p-5 border border-white/10 shadow-2xl">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-primary-500/20 border border-primary-500/30">
                            <Gauge className="w-6 h-6 text-primary-400" />
                        </div>
                        <div>
                            <h2 className="text-lg font-black font-display text-white tracking-tight">
                                API Latency Observatory
                            </h2>
                            <p className="text-xs text-slate-400 font-mono">
                                Live round-trip times across our own backend endpoints and upstream sources
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-900/80 border border-white/10 text-xs font-mono">
                            <Server className="w-3.5 h-3.5 text-slate-400" />
                            <span className="text-slate-400">Market probe:</span>
                            <span className={marketId ? 'text-emerald-400' : 'text-amber-400'}>
                                {marketId || 'auto-detect'}
                            </span>
                        </div>

                        <button
                            onClick={handleManualRefresh}
                            disabled={isProbing}
                            className="px-3 py-1.5 rounded-lg bg-surface-900 hover:bg-primary-500/20 text-slate-300 hover:text-white border border-white/10 transition-colors flex items-center gap-2 text-xs font-bold font-display disabled:opacity-50"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${isProbing ? 'animate-spin' : ''}`} />
                            Refresh
                        </button>

                        <button
                            onClick={() => setAutoRefresh((v) => !v)}
                            className={`px-3 py-1.5 rounded-lg border transition-colors flex items-center gap-2 text-xs font-bold font-display ${
                                autoRefresh
                                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                    : 'bg-surface-900 text-slate-300 border-white/10 hover:text-white'
                            }`}
                        >
                            {autoRefresh ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                            {autoRefresh ? 'Pause 10s' : 'Auto 10s'}
                        </button>

                        <button
                            onClick={clearHistory}
                            className="px-3 py-1.5 rounded-lg bg-surface-900 hover:bg-rose-500/20 text-slate-300 hover:text-rose-400 border border-white/10 transition-colors flex items-center gap-2 text-xs font-bold font-display"
                        >
                            <Trash2 className="w-3.5 h-3.5" />
                            Clear
                        </button>
                    </div>
                </div>

                {/* Summary Strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
                    <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 flex items-center gap-3">
                        <Activity className="w-4 h-4 text-primary-400" />
                        <div>
                            <div className="text-[10px] text-slate-500 font-mono uppercase">Avg RTT</div>
                            <div className="text-sm font-bold text-white font-mono">{stats.avg}ms</div>
                        </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 flex items-center gap-3">
                        <Clock className="w-4 h-4 text-amber-400" />
                        <div>
                            <div className="text-[10px] text-slate-500 font-mono uppercase">Max RTT</div>
                            <div className="text-sm font-bold text-white font-mono">{stats.max}ms</div>
                        </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 flex items-center gap-3">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <div>
                            <div className="text-[10px] text-slate-500 font-mono uppercase">OK</div>
                            <div className="text-sm font-bold text-white font-mono">{stats.okCount}/{stats.total}</div>
                        </div>
                    </div>
                    <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 flex items-center gap-3">
                        {stats.failCount > 0 ? <XCircle className="w-4 h-4 text-rose-400" /> : <Wifi className="w-4 h-4 text-emerald-400" />}
                        <div>
                            <div className="text-[10px] text-slate-500 font-mono uppercase">Failures</div>
                            <div className={`text-sm font-bold font-mono ${stats.failCount > 0 ? 'text-rose-400' : 'text-white'}`}>
                                {stats.failCount}
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Route Switcher / Upstream Observatory */}
            <section className="glass-card rounded-2xl p-5 border border-white/10 shadow-2xl">
                <div className="flex items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                            <Globe className="w-5 h-5 text-emerald-400" />
                        </div>
                        <div>
                            <h3 className="text-base font-black font-display text-white">Upstream Route Observatory</h3>
                            <p className="text-[11px] text-slate-400 font-mono">
                                Edit endpoints and test latency. Changes persist in localStorage.
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={probeRoutes}
                            className="px-3 py-1.5 rounded-lg bg-surface-900 hover:bg-primary-500/20 text-slate-300 hover:text-white border border-white/10 transition-colors flex items-center gap-2 text-xs font-bold font-display"
                        >
                            <RefreshCw className="w-3.5 h-3.5" />
                            Test
                        </button>
                        <button
                            onClick={handleSaveRoutes}
                            className="px-3 py-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition-colors flex items-center gap-2 text-xs font-bold font-display"
                        >
                            <Save className="w-3.5 h-3.5" />
                            Save
                        </button>
                        <button
                            onClick={handleResetRoutes}
                            className="px-3 py-1.5 rounded-lg bg-surface-900 hover:bg-rose-500/20 text-slate-300 hover:text-rose-400 border border-white/10 transition-colors flex items-center gap-2 text-xs font-bold font-display"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            Reset
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {routeResults.map((r) => (
                        <div
                            key={r.key}
                            className="rounded-xl p-3 bg-surface-900/60 border border-white/5 hover:border-white/10 transition-colors"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-bold text-white">{r.label}</span>
                                {r.last ? (
                                    r.last.ok ? (
                                        <Wifi className="w-4 h-4 text-emerald-400" />
                                    ) : (
                                        <WifiOff className="w-4 h-4 text-rose-400" />
                                    )
                                ) : (
                                    <Wifi className="w-4 h-4 text-slate-600" />
                                )}
                            </div>
                            <input
                                type="text"
                                value={routeInputs[r.key]}
                                onChange={(e) => setRouteInputs((prev) => ({ ...prev, [r.key]: e.target.value }))}
                                className="w-full text-[11px] font-mono bg-surface-950 border border-white/10 rounded-lg px-2.5 py-1.5 text-slate-300 focus:outline-none focus:border-primary-500/50 mb-2"
                            />
                            <div className="flex items-center justify-between text-[11px] font-mono">
                                <span className={statusColor(r.last?.ok ?? null)}>
                                    {r.last ? `${r.last.durationMs}ms` : '—'}
                                </span>
                                <span className="text-slate-500">
                                    {r.last ? `HTTP ${r.last.status}` : 'untested'}
                                </span>
                            </div>
                            {r.last?.error && (
                                <div className="mt-2 text-[10px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-lg p-1.5">
                                    {r.last.error}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </section>

            {/* Endpoint Grid */}
            <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {rows.map((row) => {
                    const { def, last, history } = row
                    const hasData = !!last
                    const spark = history.map((h) => h.durationMs)
                    const avgHistory = spark.length
                        ? Math.round(spark.reduce((a, b) => a + b, 0) / spark.length)
                        : 0
                    const maxHistory = spark.length ? Math.max(...spark) : 0

                    return (
                        <div
                            key={def.id}
                            className="glass-card rounded-xl p-4 border border-white/10 shadow-xl hover:border-white/15 transition-colors"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded bg-surface-800 text-slate-300 border border-white/5">
                                            {def.method}
                                        </span>
                                        {def.needsMarket && (
                                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                                market
                                            </span>
                                        )}
                                    </div>
                                    <h3 className="text-sm font-bold text-white truncate" title={def.label}>
                                        {def.label}
                                    </h3>
                                    <p className="text-[11px] text-slate-500 font-mono truncate" title={resolvePath(def.path)}>
                                        {resolvePath(def.path)}
                                    </p>
                                </div>
                                <div className="shrink-0">
                                    {hasData ? (
                                        last!.ok ? (
                                            <Wifi className="w-5 h-5 text-emerald-400" />
                                        ) : (
                                            <WifiOff className="w-5 h-5 text-rose-400" />
                                        )
                                    ) : (
                                        <Wifi className="w-5 h-5 text-slate-600" />
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 flex items-end justify-between gap-4">
                                <div>
                                    <div className="text-[10px] text-slate-500 font-mono uppercase">Last RTT</div>
                                    <div className={`text-2xl font-black font-mono ${statusColor(hasData ? last!.ok : null)}`}>
                                        {hasData ? `${last!.durationMs}ms` : '—'}
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[10px] text-slate-500 font-mono">avg {avgHistory}ms</div>
                                    <div className="text-[10px] text-slate-500 font-mono">max {maxHistory}ms</div>
                                </div>
                            </div>

                            {/* Sparkline */}
                            <div className="mt-3 h-8 flex items-end gap-0.5">
                                {history.length === 0 ? (
                                    <div className="w-full h-full rounded bg-surface-900/50 border border-white/5" />
                                ) : (
                                    history.map((h, idx) => {
                                        const height = maxHistory > 0 ? Math.max(10, (h.durationMs / maxHistory) * 100) : 10
                                        return (
                                            <div
                                                key={idx}
                                                className={`flex-1 rounded-sm ${h.ok ? 'bg-primary-500/60' : 'bg-rose-500/60'}`}
                                                style={{ height: `${height}%`, minHeight: 4 }}
                                                title={`${h.durationMs}ms @ ${new Date(h.timestamp).toLocaleTimeString()}`}
                                            />
                                        )
                                    })
                                )}
                            </div>

                            {last?.error && (
                                <div className="mt-3 flex items-start gap-2 text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-lg p-2">
                                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                                    <span className="break-all">{last.error}</span>
                                </div>
                            )}

                            {last?.status && (
                                <div className="mt-2 text-[10px] font-mono text-slate-500">
                                    HTTP {last.status} · {new Date(last.timestamp).toLocaleTimeString()}
                                </div>
                            )}
                        </div>
                    )
                })}
            </section>
        </div>
    )
}

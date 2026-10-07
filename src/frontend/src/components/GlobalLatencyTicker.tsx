import { useEffect, useState, useCallback } from 'react'
import axios from 'axios'
import { Activity, RefreshCw } from 'lucide-react'

interface PingStat {
    name: string
    short: string
    url: string
    latencyMs: number | null
    status: 'fast' | 'moderate' | 'slow' | 'down'
    lagLabel?: string
}

const TARGETS: Omit<PingStat, 'latencyMs' | 'status'>[] = [
    { name: 'Polymarket BBO', short: 'POLY', url: '/api/status/polymarket', lagLabel: 'Live Radar (0s)' },
    { name: 'MLB Stats API', short: 'MLB', url: '/api/scanners/mlb/board', lagLabel: '+1.5s delay' },
    { name: 'ESPN Broadcast', short: 'ESPN', url: '/api/scanners/cfb/live', lagLabel: '+8.0s TV lag' },
]

export function GlobalLatencyTicker() {
    const [pings, setPings] = useState<PingStat[]>(() =>
        TARGETS.map(t => ({ ...t, latencyMs: null, status: 'fast' }))
    )
    const [isPinging, setIsPinging] = useState(false)
    const [lastPingTime, setLastPingTime] = useState<Date>(new Date())

    const runPings = useCallback(async () => {
        setIsPinging(true)
        const updated = await Promise.all(
            TARGETS.map(async (target) => {
                const start = performance.now()
                try {
                    await axios.get(target.url, { timeout: 8000 })
                    const duration = Math.round(performance.now() - start)
                    let status: PingStat['status'] = 'fast'
                    if (duration > 350) status = 'slow'
                    else if (duration > 180) status = 'moderate'
                    return {
                        ...target,
                        latencyMs: duration,
                        status
                    }
                } catch {
                    return {
                        ...target,
                        latencyMs: null,
                        status: 'down' as const
                    }
                }
            })
        )
        setPings(updated)
        setLastPingTime(new Date())
        setIsPinging(false)
    }, [])

    useEffect(() => {
        runPings()
        const interval = setInterval(runPings, 60000) // Auto-ping every 60 seconds (every minute)
        return () => clearInterval(interval)
    }, [runPings])

    return (
        <div className="w-full flex items-center justify-between gap-1.5 font-mono text-xs min-w-0">
            {/* Header / Label */}
            <div className="flex items-center gap-1.5 text-slate-400 font-semibold uppercase tracking-wider shrink-0">
                <Activity className={`w-3.5 h-3.5 text-emerald-400 shrink-0 ${isPinging ? 'animate-spin' : 'animate-pulse'}`} />
                <span className="text-[10px] text-slate-300 font-bold hidden sm:inline">FEED LATENCY:</span>
            </div>

            {/* Compact Latency Badges */}
            <div className="flex items-center gap-1 sm:gap-1.5 min-w-0 overflow-hidden">
                {pings.map((p) => {
                    const color =
                        p.status === 'fast'
                            ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                            : p.status === 'moderate'
                            ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                            : p.status === 'slow'
                            ? 'text-orange-400 border-orange-500/30 bg-orange-500/10'
                            : 'text-rose-400 border-rose-500/30 bg-rose-500/10'

                    return (
                        <div
                            key={p.short}
                            className={`flex items-center gap-1 px-1.5 sm:px-2 py-0.5 rounded-lg border text-[10px] font-black shrink-0 ${color}`}
                            title={`${p.name}: ${p.latencyMs ? p.latencyMs + 'ms' : 'Offline'} (${p.lagLabel || ''})`}
                        >
                            <span className="opacity-75">{p.short}:</span>
                            <span>{p.latencyMs !== null ? `${p.latencyMs}ms` : 'ERR'}</span>
                        </div>
                    )
                })}
            </div>

            {/* Refresh Trigger */}
            <button
                onClick={runPings}
                disabled={isPinging}
                title={`Last pinged ${lastPingTime.toLocaleTimeString()}. Click to refresh.`}
                className="p-1 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition disabled:opacity-50 shrink-0"
            >
                <RefreshCw className={`w-3.5 h-3.5 ${isPinging ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
        </div>
    )
}

import { useState, useMemo } from 'react'
import {
    Activity,
    TrendingUp,
    TrendingDown,
    RefreshCw,
    Wallet,
    Clock,
    ExternalLink,
    Zap,
    ShieldAlert,
    Target
} from 'lucide-react'
import { useAccount, AccountOpenPosition } from '../hooks/useAccount'
import { useWhales, WhaleTrade } from '../hooks/useWhales'
import { useMarkets } from '../hooks/useMarkets'
import { getUserTags } from '../utils/userTags'

interface HeldGameItem {
    pos: AccountOpenPosition
    marketId: string
    marketTitle: string
    yesPct?: number
}

function formatAddress(address: string): string {
    if (!address) return 'Unknown'
    if (address.length < 10) return address
    return `${address.slice(0, 6)}...${address.slice(-4)}`
}

function formatCurrency(value: number): string {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value)
}

function formatTimeAgo(dateString: string): string {
    if (!dateString) return ''
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
}

export function HeldPositionsWhaleRadar() {
    const { data: accountData, isLoading: accountLoading } = useAccount()
    const { data: marketsData } = useMarkets()
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
    const [minVol, setMinVol] = useState<number>(250)

    const heldItems: AccountOpenPosition[] = useMemo(() => {
        return accountData?.open_positions?.items || []
    }, [accountData])

    // Match held position slugs with market IDs in market database
    const heldGamesWithMarket: HeldGameItem[] = useMemo(() => {
        return heldItems.map((pos: AccountOpenPosition) => {
            const matched = marketsData?.markets?.find(m =>
                m.slug === pos.slug ||
                (pos.slug && m.slug.includes(pos.slug.replace('aec-', ''))) ||
                (pos.title && m.title?.toLowerCase().includes(pos.title.toLowerCase()))
            )
            return {
                pos,
                marketId: matched?.id || pos.slug,
                marketTitle: matched?.title || pos.title || pos.slug,
                yesPct: matched?.yes_percentage,
            }
        })
    }, [heldItems, marketsData])

    // Default to first held game if none selected
    const activeGame: HeldGameItem | null = useMemo(() => {
        if (!heldGamesWithMarket.length) return null
        if (!selectedSlug) return heldGamesWithMarket[0]
        return heldGamesWithMarket.find((g: HeldGameItem) => g.pos.slug === selectedSlug) || heldGamesWithMarket[0]
    }, [heldGamesWithMarket, selectedSlug])

    const {
        data: whaleTrades,
        isLoading: tradesLoading,
        refetch,
        isFetching
    } = useWhales(activeGame?.marketId || null, minVol, 3)

    // Calculate Whale Flow Sentiment Metrics on the Held Game
    const metrics = useMemo(() => {
        if (!whaleTrades || !whaleTrades.length) {
            return { totalVolume: 0, buyVol: 0, sellVol: 0, bullishPct: 50, count: 0 }
        }
        let buy = 0
        let sell = 0
        whaleTrades.forEach(t => {
            if (t.is_bullish || t.side === 'BUY') buy += t.volume
            else sell += t.volume
        })
        const total = buy + sell
        const bullishPct = total > 0 ? Math.round((buy / total) * 100) : 50
        return { totalVolume: total, buyVol: buy, sellVol: sell, bullishPct, count: whaleTrades.length }
    }, [whaleTrades])

    if (accountLoading) {
        return (
            <div className="p-8 text-center glass-card rounded-2xl border border-white/10 text-slate-400 font-mono">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary-400" />
                <span>Scanning active portfolio tickets...</span>
            </div>
        )
    }

    if (!heldItems.length) {
        return (
            <div className="p-6 text-center glass-card rounded-2xl border border-white/10 text-slate-400">
                <Wallet className="w-8 h-8 mx-auto mb-2 text-slate-500" />
                <h3 className="text-sm font-bold text-white font-display">No Active Tickets Running</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                    When you enter a trade on Polymarket, this Whale Radar automatically tracks institutional block orders on your active games.
                </p>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {/* Held Games Tab Selector */}
            <div className="bg-surface-900/90 border border-white/10 rounded-2xl p-3.5 shadow-2xl backdrop-blur-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 px-1">
                    <div className="flex items-center gap-2 text-xs font-bold font-display uppercase tracking-wider text-slate-200">
                        <Target className="w-4 h-4 text-emerald-400" />
                        <span>Whale Radar for Your Active Held Tickets</span>
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono">
                            {heldItems.length} Active
                        </span>
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="text-[11px] text-slate-400 font-mono hidden sm:inline">Min Whale Size:</span>
                        <div className="flex items-center gap-1 bg-surface-950 p-0.5 rounded-lg border border-white/10 text-[10px] font-mono">
                            {[100, 250, 500, 1000].map(v => (
                                <button
                                    key={v}
                                    onClick={() => setMinVol(v)}
                                    className={`px-2 py-1 rounded transition ${minVol === v ? 'bg-primary-500 text-white font-bold' : 'text-slate-400 hover:text-white'}`}
                                >
                                    ${v}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {heldGamesWithMarket.map((item: HeldGameItem) => {
                        const isSelected = activeGame?.pos.slug === item.pos.slug
                        return (
                            <button
                                key={item.pos.slug}
                                onClick={() => setSelectedSlug(item.pos.slug)}
                                className={`p-3 rounded-xl text-left transition-all border ${
                                    isSelected
                                        ? 'bg-gradient-to-r from-primary-500/20 to-emerald-500/10 border-primary-400/60 shadow-lg shadow-primary-500/10'
                                        : 'bg-surface-950/60 hover:bg-white/5 border-white/5 text-slate-400 hover:text-slate-200'
                                }`}
                            >
                                <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-mono text-emerald-400 uppercase font-bold tracking-wider">
                                        Active Position
                                    </span>
                                    <span className="text-[10px] font-mono text-slate-400">
                                        {item.pos.contracts} contracts
                                    </span>
                                </div>
                                <div className="text-xs font-bold text-white font-display truncate mt-0.5">
                                    {item.pos.title || item.marketTitle}
                                </div>
                                <div className="flex items-center justify-between mt-2 text-[11px] font-mono">
                                    <span className="text-slate-300">Holding: <strong className="text-white">{item.pos.outcome}</strong></span>
                                    <span className="text-emerald-400 font-bold">${item.pos.value.toFixed(2)}</span>
                                </div>
                            </button>
                        )
                    })}
                </div>
            </div>

            {/* Whale Sentiment & Order Flow Banner on Active Game */}
            {activeGame && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="glass-card rounded-2xl p-3.5 border border-white/10 shadow-lg">
                        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 uppercase">
                            <Zap className="w-3.5 h-3.5 text-amber-400" />
                            <span>Whale Flow on Game</span>
                        </div>
                        <div className="text-xl font-black font-display text-white mt-1">
                            {formatCurrency(metrics.totalVolume)}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5 font-mono">
                            {metrics.count} block orders tracked
                        </div>
                    </div>

                    <div className="glass-card rounded-2xl p-3.5 border border-white/10 shadow-lg">
                        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 uppercase">
                            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Whale Buy Pressure</span>
                        </div>
                        <div className="text-xl font-black font-display text-emerald-400 mt-1">
                            {metrics.bullishPct}% Bullish
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-surface-800 overflow-hidden flex mt-1.5">
                            <div className="bg-emerald-400 h-full" style={{ width: `${metrics.bullishPct}%` }} />
                            <div className="bg-rose-500 h-full" style={{ width: `${100 - metrics.bullishPct}%` }} />
                        </div>
                    </div>

                    <div className="glass-card rounded-2xl p-3.5 border border-white/10 shadow-lg">
                        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 uppercase">
                            <Activity className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Live Market Implied Odds</span>
                        </div>
                        <div className="text-xl font-black font-display text-cyan-300 mt-1">
                            {activeGame.yesPct ? `${Math.round(activeGame.yesPct)}% Yes` : 'In-Play Live'}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5 font-mono truncate">
                            Slug: {activeGame.pos.slug}
                        </div>
                    </div>
                </div>
            )}

            {/* Live Real-Time Whale Trade Stream on This Game */}
            <div className="glass-card rounded-2xl p-4 border border-white/10 shadow-2xl">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-primary-400" />
                        <h3 className="text-xs font-bold font-display text-white uppercase tracking-wider">
                            Live Whale Trades Stream ({activeGame?.pos.title || 'Active Ticket'})
                        </h3>
                    </div>
                    <button
                        onClick={() => refetch()}
                        disabled={isFetching}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-900 border border-white/10 text-[11px] font-mono text-slate-300 hover:text-white disabled:opacity-50"
                    >
                        <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin text-emerald-400' : ''}`} />
                        <span>Refresh Flow</span>
                    </button>
                </div>

                {tradesLoading ? (
                    <div className="p-6 text-center text-slate-400 font-mono text-xs">
                        <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-primary-400" />
                        <span>Loading real-time whale orders on {activeGame?.pos.title}...</span>
                    </div>
                ) : !whaleTrades || !whaleTrades.length ? (
                    <div className="p-6 text-center border border-white/5 rounded-xl bg-surface-950/40 text-slate-400 font-mono">
                        <ShieldAlert className="w-6 h-6 text-slate-500 mx-auto mb-1.5" />
                        <p className="text-xs">No whale trades $\ge$ ${minVol} detected in recent blocks for this game.</p>
                        <p className="text-[10px] text-slate-500 mt-1">Lower the minimum filter or wait for upcoming in-play sweeps.</p>
                    </div>
                ) : (
                    <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
                        {whaleTrades.map((trade: WhaleTrade, idx: number) => {
                            const isBuy = trade.side === 'BUY'
                            const displayName = trade.name || formatAddress(trade.address)
                            const tags = getUserTags({
                                global_pnl: trade.global_pnl,
                                total_balance: trade.total_balance,
                            })

                            return (
                                <div
                                    key={`${trade.trade_id || trade.timestamp}-${idx}`}
                                    className="p-3 rounded-xl bg-surface-950/60 border border-white/5 hover:border-primary-500/30 transition-all flex items-center justify-between gap-3"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className={`p-1.5 rounded-xl flex-shrink-0 ${trade.is_bullish ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                                            {trade.is_bullish ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                                        </div>

                                        <div className="min-w-0">
                                            <div className="flex items-center gap-1.5 flex-wrap">
                                                <a
                                                    href={`https://polymarket.com/profile/${trade.address}`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-xs font-bold text-white hover:text-primary-300 font-mono truncate max-w-[120px]"
                                                >
                                                    {displayName}
                                                </a>
                                                <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase ${
                                                    isBuy ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                                }`}>
                                                    {trade.side}
                                                </span>
                                                <span className="text-[8px] font-bold px-1.5 py-0.5 rounded bg-surface-800 text-slate-200 border border-white/10 uppercase">
                                                    {trade.outcome}
                                                </span>
                                                {tags.map(tag => (
                                                    <span key={tag.label} className="text-[8px] font-semibold px-1.5 py-0.5 rounded bg-surface-900 text-slate-400 border border-white/10">
                                                        {tag.label}
                                                    </span>
                                                ))}
                                            </div>

                                            <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400 font-mono">
                                                <span>{trade.size.toLocaleString()} shares</span>
                                                <span>•</span>
                                                <span>@{(trade.price * 100).toFixed(1)}¢</span>
                                                <span>•</span>
                                                <span className="flex items-center gap-1 text-[9px] text-slate-500">
                                                    <Clock className="w-2.5 h-2.5" />
                                                    {formatTimeAgo(trade.timestamp)}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2.5">
                                        <div className="text-right">
                                            <div className={`text-xs font-black font-display ${trade.is_bullish ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                {formatCurrency(trade.volume)}
                                            </div>
                                            <div className="text-[8px] font-mono text-slate-500 uppercase">
                                                Block Order
                                            </div>
                                        </div>
                                        <a
                                            href={`https://polymarket.com/profile/${trade.address}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="p-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition"
                                        >
                                            <ExternalLink className="w-3 h-3" />
                                        </a>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>
        </div>
    )
}

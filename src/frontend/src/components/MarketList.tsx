import { useMemo, useState } from 'react'
import { Search, TrendingUp, TrendingDown, Loader2, Sparkles, Filter } from 'lucide-react'
import { clsx } from 'clsx'
import { useMarkets } from '../hooks/useMarkets'
import { useMarketStore, Market } from '../stores/marketStore'

function formatVolume(volume: number): string {
    if (volume >= 1_000_000) {
        return `$${(volume / 1_000_000).toFixed(1)}M`
    }
    if (volume >= 1_000) {
        return `$${(volume / 1_000).toFixed(1)}K`
    }
    return `$${volume.toFixed(0)}`
}

function MarketCard({
    market,
    isSelected,
    onClick,
}: {
    market: Market
    isSelected: boolean
    onClick: () => void
}) {
    const yesPercent = Math.min(Math.max(market.yes_percentage, 0), 100)
    const noPercent = 100 - yesPercent

    return (
        <button
            onClick={onClick}
            className={clsx(
                'market-card w-full text-left p-3.5 rounded-xl transition-all duration-200 group relative overflow-hidden',
                'border',
                isSelected
                    ? 'bg-gradient-to-br from-primary-500/20 via-surface-900/90 to-surface-900 border-primary-500/60 shadow-lg shadow-primary-500/15'
                    : 'bg-surface-900/40 hover:bg-surface-900/80 border-white/5 hover:border-white/15'
            )}
        >
            {/* Active Accent Bar */}
            {isSelected && (
                <div className="absolute top-0 left-0 bottom-0 w-1 bg-gradient-to-b from-primary-400 to-accent-400" />
            )}

            <div className="flex items-start gap-3">
                {market.image_url ? (
                    <img
                        src={market.image_url}
                        alt=""
                        className="w-10 h-10 rounded-xl object-cover flex-shrink-0 ring-1 ring-white/10 group-hover:ring-primary-500/40 transition-all"
                    />
                ) : (
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 border border-white/10 flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
                        <TrendingUp className="w-5 h-5 text-primary-400" />
                    </div>
                )}
                <div className="flex-1 min-w-0">
                    <h3 className="text-xs sm:text-sm font-semibold text-slate-100 line-clamp-2 leading-snug group-hover:text-white transition-colors">
                        {market.title}
                    </h3>

                    {/* Probability Meter */}
                    <div className="mt-2.5">
                        <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                            <span className="font-bold text-emerald-400 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                                {yesPercent.toFixed(1)}% Yes
                            </span>
                            <span className="text-slate-400">
                                {noPercent.toFixed(1)}% No
                            </span>
                        </div>
                        <div className="w-full h-1.5 bg-surface-800 rounded-full overflow-hidden flex border border-white/5">
                            <div
                                className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-300"
                                style={{ width: `${yesPercent}%` }}
                            />
                            <div
                                className="h-full bg-gradient-to-r from-rose-500/70 to-rose-400/70 transition-all duration-300"
                                style={{ width: `${noPercent}%` }}
                            />
                        </div>
                    </div>

                    {/* Meta stats */}
                    <div className="flex items-center justify-between mt-2.5 text-[11px] font-mono text-slate-400">
                        <span className="flex items-center gap-1 text-slate-300 bg-surface-950/60 px-2 py-0.5 rounded border border-white/5">
                            {formatVolume(market.volume_7d)} vol
                        </span>
                        {market.category && (
                            <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold truncate max-w-[90px]">
                                {market.category}
                            </span>
                        )}
                    </div>
                </div>
            </div>
        </button>
    )
}

const CATEGORIES = ['All', 'Crypto', 'Politics', 'Macro', 'Sports', 'Weather'] as const

export function MarketList() {
    const { data, isLoading, error } = useMarkets()
    const { selectedMarket, setSelectedMarket, searchQuery, setSearchQuery } = useMarketStore()
    const [selectedCategory, setSelectedCategory] = useState<string>('All')

    const filteredMarkets = useMemo(() => {
        if (!data?.markets) return []
        let list = data.markets

        // Category filter
        if (selectedCategory !== 'All') {
            const catLower = selectedCategory.toLowerCase()
            list = list.filter((m) =>
                m.category?.toLowerCase().includes(catLower) ||
                m.title.toLowerCase().includes(catLower) ||
                m.slug.toLowerCase().includes(catLower)
            )
        }

        // Search query filter
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase()
            list = list.filter((m) =>
                m.title.toLowerCase().includes(query) ||
                m.slug.toLowerCase().includes(query)
            )
        }

        return list
    }, [data?.markets, searchQuery, selectedCategory])

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
                <span className="text-xs font-mono text-slate-400">Streaming CLOB markets...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="text-center py-10 px-4">
                <TrendingDown className="w-8 h-8 text-rose-400 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-200">Failed to load CLOB markets</p>
                <p className="text-xs text-slate-400 mt-1">Please refresh or verify API connection</p>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-[calc(100vh-230px)]">
            {/* Search Input */}
            <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                    type="text"
                    placeholder="Search titles, tokens, keywords..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-8 py-2 text-xs font-mono bg-surface-900/80 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-primary-500/60 focus:ring-1 focus:ring-primary-500/30 transition-all shadow-inner"
                />
                {searchQuery && (
                    <button
                        onClick={() => setSearchQuery('')}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-white"
                    >
                        ×
                    </button>
                )}
            </div>

            {/* Category Filter Chips */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-2.5 mb-2 scrollbar-none">
                {CATEGORIES.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={clsx(
                            'px-2.5 py-1 rounded-lg text-[11px] font-semibold whitespace-nowrap transition-all',
                            selectedCategory === cat
                                ? 'bg-primary-500 text-white shadow-sm shadow-primary-500/30'
                                : 'bg-surface-900/60 hover:bg-surface-800 text-slate-400 hover:text-white border border-white/5'
                        )}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Market List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1.5 scrollbar-thin">
                {filteredMarkets.map((market) => (
                    <MarketCard
                        key={market.id}
                        market={market}
                        isSelected={selectedMarket?.id === market.id}
                        onClick={() => setSelectedMarket(market)}
                    />
                ))}
                {filteredMarkets.length === 0 && (
                    <div className="text-center py-12 px-4 rounded-xl border border-dashed border-white/10">
                        <Sparkles className="w-6 h-6 text-slate-500 mx-auto mb-2" />
                        <p className="text-xs font-mono text-slate-400">
                            No markets match "{searchQuery || selectedCategory}"
                        </p>
                    </div>
                )}
            </div>

            {/* Footer Status */}
            {data?.last_updated && (
                <div className="pt-3 border-t border-white/10 flex items-center justify-between text-[10px] font-mono text-slate-500">
                    <span>{filteredMarkets.length} displayed</span>
                    <span>Updated: {new Date(data.last_updated).toLocaleTimeString()}</span>
                </div>
            )}
        </div>
    )
}

import { Market, useMarketStore } from '../stores/marketStore'
import { marketSides } from '../utils/sides'
import { usePriceHistory } from '../hooks/usePriceHistory'
import { useLiveScore } from '../hooks/useLiveScore'
import { ExternalLink } from 'lucide-react'

/** A spread or total market belongs to the game's event page, whose slug is the slug without the line. */
const eventSlug = (slug: string): string => slug.replace(/-(spread|total)-.*$/, '')

const money = (n: number): string =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

/** Polymarket-style head to head: each side with its price, the live score, and what has moved the price. */
export default function HeadToHead({ market }: { market: Market }) {
    const sides = marketSides(market)
    const { selectedTimeframe } = useMarketStore()
    const { data: history } = usePriceHistory(market.id, selectedTimeframe)
    const { data: live } = useLiveScore(sides.named ? market.title : null)

    const points = history?.history ?? []
    const move = points.length > 1 ? points[points.length - 1].yes_percentage - points[0].yes_percentage : null
    const leader = sides.a.pct >= sides.b.pct ? 'a' : 'b'

    const total = live ? live.away_score + live.home_score : 0
    const awayLead = live ? live.away_score - live.home_score : 0
    const scoreLine = live
        ? `${live.away} ${live.away_score} - ${live.home} ${live.home_score}`
        : null
    const when = live ? (live.state === 'in' ? `LIVE · ${live.detail}` : live.state === 'post' ? 'Final' : live.detail || 'Not started') : null

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
                {([['a', sides.a], ['b', sides.b]] as const).map(([key, side]) => (
                    <div
                        key={key}
                        className={`rounded-xl border px-4 py-3 ${
                            leader === key ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-surface-900/70 border-white/10'
                        }`}
                    >
                        <div className="text-xs font-mono uppercase tracking-wider text-slate-400 truncate">{side.label}</div>
                        <div className={`text-3xl font-black font-display ${leader === key ? 'text-emerald-300' : 'text-slate-200'}`}>
                            {side.pct.toFixed(0)}%
                        </div>
                        <div className="text-[11px] font-mono text-slate-500">pays {side.pct > 0 ? (100 / side.pct).toFixed(1) : '-'}x</div>
                    </div>
                ))}
            </div>
            <div className="w-full h-1.5 bg-surface-800 rounded-full overflow-hidden flex border border-white/5">
                <div className="h-full bg-emerald-500" style={{ width: `${sides.a.pct}%` }} />
                <div className="h-full bg-rose-500/70" style={{ width: `${sides.b.pct}%` }} />
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-slate-400">
                {scoreLine && live && (
                    <span>
                        <span className={live.state === 'in' ? 'text-amber-300' : 'text-slate-500'}>{when}</span>
                        <span className="text-slate-200"> · {scoreLine}</span>
                        {live.state !== 'pre' && awayLead !== 0 && (
                            <span className="text-slate-500">
                                {' '}· {awayLead > 0 ? live.away : live.home} up {Math.abs(awayLead)}, total {total}
                            </span>
                        )}
                    </span>
                )}
                {move !== null && (
                    <span>
                        {sides.a.label} {move >= 0 ? '+' : ''}
                        {move.toFixed(1)} pts over {selectedTimeframe}
                    </span>
                )}
                <span>24h volume {money(market.volume_24h)}</span>
                <span>7d volume {money(market.volume_7d)}</span>
                <a
                    href={`https://polymarket.com/event/${eventSlug(market.slug)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto flex items-center gap-1 text-primary-300 hover:text-white"
                >
                    Open on Polymarket <ExternalLink className="w-3 h-3" />
                </a>
            </div>
        </div>
    )
}

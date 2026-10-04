import { Bell } from 'lucide-react'
import { useAlerts } from '../hooks/useAlerts'

const ago = (iso: string): string => {
    const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.round(minutes / 60)
    return hours < 24 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`
}

/** Teams that are ahead on the scoreboard but priced below what the game supports. */
export default function AlertsPanel() {
    const { data } = useAlerts()
    if (!data) return null
    const isFirst = (a: { kind: string }) => a.kind === 'first_score_upset'
    const active = data.alerts.filter((a) => a.status === 'active')
    const earlier = data.alerts.filter((a) => a.status !== 'active')
    return (
        <section className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <h2 className="flex items-center gap-2 text-sm font-bold font-display tracking-wide text-slate-300 uppercase">
                    <Bell className="w-4 h-4 text-amber-400" />
                    Alerts
                </h2>
                <span className="text-[11px] font-mono text-slate-500">
                    underpriced leaders (up {data.min_lead}+, still under {Math.round(data.max_price * 100)}%) and ranked teams scored on first by an unranked team ·{' '}
                    {data.email_configured ? 'email on' : 'email not set up (alerts show here only)'}
                </span>
            </div>
            {active.length === 0 ? (
                <p className="text-sm text-slate-500">
                    Nothing active right now. Scanning live college football and NFL games every minute.
                </p>
            ) : (
                <ul className="space-y-2">
                    {active.map((a) => (
                        <li
                            key={a.id}
                            className={`rounded-xl border px-3 py-2 text-sm ${
                                a.now && !isFirst(a) && !a.now.still_leading
                                    ? 'bg-surface-900/40 border-white/5 opacity-60'
                                    : a.priority === 'high'
                                      ? 'bg-amber-500/10 border-amber-500/40'
                                      : 'bg-surface-900/70 border-white/10'
                            }`}
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold text-slate-100">
                                    {isFirst(a) ? (
                                        <>
                                            {a.team} <span className="text-amber-300">scored on first</span>
                                        </>
                                    ) : (
                                        <>
                                            {a.team} <span className="text-emerald-300">was up {a.margin}</span>
                                        </>
                                    )}
                                    <span className="ml-2 text-[10px] font-mono text-slate-500 uppercase">{a.sport}</span>
                                    {a.priority === 'high' && <span className="ml-2 text-[10px] font-bold text-amber-300">HIGH</span>}
                                </span>
                                <span className="text-[11px] font-mono text-slate-500">{ago(a.created_at)}</span>
                            </div>
                            <div className="text-xs font-mono text-slate-300 mt-0.5">
                                {isFirst(a) ? 'now priced' : 'still priced'} <span className="text-rose-300">{(a.market_price * 100).toFixed(0)}%</span> vs ESPN{' '}
                                <span className="text-emerald-300">{(a.espn_win_prob * 100).toFixed(0)}%</span>
                                <span className="text-slate-500"> · gap {(a.gap * 100).toFixed(0)} pts · {a.title}</span>
                            </div>
                            {isFirst(a) ? (
                                a.now && (
                                    <div className="text-[11px] font-mono mt-0.5 text-slate-400">
                                        NOW: {a.now.away} {a.now.away_score} - {a.now.home} {a.now.home_score} ({a.now.state === 'post' ? 'Final' : a.now.detail})
                                    </div>
                                )
                            ) : a.now ? (
                                <div className={`text-[11px] font-mono mt-0.5 ${a.now.still_leading ? 'text-emerald-300' : 'text-rose-300'}`}>
                                    NOW: {a.now.away} {a.now.away_score} - {a.now.home} {a.now.home_score} ({a.now.state === 'post' ? 'Final' : a.now.detail})
                                    {a.now.still_leading ? ` · still up ${a.now.margin}` : ' · no longer qualifies (the score changed)'}
                                </div>
                            ) : (
                                <div className="text-[11px] font-mono text-slate-500 mt-0.5">NOW: game not on the board any more</div>
                            )}
                            {a.detail && <div className="text-[11px] font-mono text-slate-500">at alert time: {a.detail} · {a.delivery}</div>}
                        </li>
                    ))}
                </ul>
            )}
            {earlier.length > 0 && (
                <details className="mt-3">
                    <summary className="cursor-pointer text-[11px] font-mono text-slate-500 hover:text-slate-300">
                        Earlier alerts ({earlier.length}) · retracted or finished
                    </summary>
                    <ul className="mt-2 space-y-1.5">
                        {earlier.map((a) => (
                            <li key={a.id} className="rounded-lg border border-white/5 bg-surface-900/30 px-3 py-1.5 text-xs font-mono text-slate-500">
                                <span className={a.status === 'retracted' ? 'text-rose-400 font-bold' : 'text-slate-500'}>
                                    {a.status === 'retracted' ? 'RETRACTED' : 'finished'}
                                </span>
                                <span className="ml-2 line-through decoration-slate-600">{a.team} was up {a.margin}</span>
                                <span className="ml-2">{a.status === 'retracted' ? a.retract_note : a.now ? `final: ${a.now.away} ${a.now.away_score} - ${a.now.home} ${a.now.home_score}` : ''}</span>
                            </li>
                        ))}
                    </ul>
                </details>
            )}
        </section>
    )
}

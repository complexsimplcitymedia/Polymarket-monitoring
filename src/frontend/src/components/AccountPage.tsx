import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw, Wallet } from 'lucide-react'
import AlertsPanel from './AlertsPanel'

import { Bet, CycleGroup, LiveInfo, fetchAccount, useAccount, useBets, useSetBetNote } from '../hooks/useAccount'

const money = (value: number | null | undefined, digits = 2): string => {
    if (value === null || value === undefined) return '-'
    const sign = value < 0 ? '-' : ''
    return `${sign}$${Math.abs(value).toLocaleString('en-US', {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    })}`
}

const signedMoney = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '-'
    return `${value > 0 ? '+' : ''}${money(value)}`
}

const percent = (value: number | null | undefined, digits = 0): string =>
    value === null || value === undefined ? '-' : `${(value * 100).toFixed(digits)}%`

const tone = (value: number | null | undefined): string => {
    if (value === null || value === undefined || value === 0) return 'text-slate-200'
    return value > 0 ? 'text-emerald-400' : 'text-rose-400'
}

function Stat({ label, value, sub, valueClass }: { label: string; value: string; sub?: string; valueClass?: string }) {
    return (
        <div className="rounded-xl bg-surface-900/70 border border-white/10 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-mono">{label}</div>
            <div className={`text-xl font-bold font-display mt-0.5 ${valueClass ?? 'text-white'}`}>{value}</div>
            {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
        </div>
    )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl">
            <h2 className="text-sm font-bold font-display tracking-wide text-slate-300 uppercase mb-3">{title}</h2>
            {children}
        </section>
    )
}

const NEXT_TAG = { analysis: 'vibe', vibe: 'hedge', hedge: 'analysis' } as const
const TAG_TONE: Record<string, string> = {
    analysis: 'text-slate-500 border-white/10 hover:text-slate-300',
    vibe: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/40',
    hedge: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
}

function LiveLine({ live }: { live: LiveInfo }) {
    const score = `${live.away} ${live.away_score} - ${live.home} ${live.home_score}`
    const when = live.state === 'in' ? live.detail : live.state === 'post' ? 'Final' : live.detail || 'Not started'
    let verdict: { text: string; tone: string } | null = null
    if (live.kind) {
        const needs = live.needs
        verdict = {
            text: `${live.kind === 'over' ? 'Over' : 'Under'} ${live.line ?? ''}: total ${live.total}${
                live.kind === 'over' && needs != null ? (needs > 0 ? `, needs ${needs} more` : ', cleared') : ''
            }`,
            tone: live.kind === 'over' && needs === 0 ? 'text-emerald-400' : 'text-slate-300',
        }
    } else if (live.status && live.state !== 'pre') {
        const word = live.status === 'tied' ? 'tied' : `${live.status} by ${Math.abs(live.margin ?? 0)}`
        verdict = {
            text: `your side is ${word}`,
            tone: live.status === 'leading' ? 'text-emerald-400' : live.status === 'trailing' ? 'text-rose-400' : 'text-slate-300',
        }
    }
    return (
        <div className="mt-0.5 text-[11px] font-mono text-slate-500">
            <span className={live.state === 'in' ? 'text-amber-300' : ''}>{live.state === 'in' ? '● LIVE' : when}</span>
            {live.state === 'in' && <span> · {when}</span>} · {score}
            {verdict && <span className={`ml-2 ${verdict.tone}`}>{verdict.text}</span>}
        </div>
    )
}

function GroupRow({ label, g }: { label: string; g: CycleGroup }) {
    return (
        <tr className="border-t border-white/5">
            <td className="py-2 pr-3 text-slate-300 capitalize">{label}</td>
            <td className="py-2 pr-3 text-right font-mono">{g.n}</td>
            <td className="py-2 pr-3 text-right font-mono">{percent(g.win_rate)}</td>
            <td className="py-2 pr-3 text-right font-mono text-emerald-400">{signedMoney(g.avg_win)}</td>
            <td className="py-2 pr-3 text-right font-mono text-rose-400">{money(g.avg_loss)}</td>
            <td className="py-2 pr-3 text-right font-mono text-emerald-400">{signedMoney(g.best)}</td>
            <td className="py-2 pr-3 text-right font-mono text-rose-400">{money(g.worst)}</td>
            <td className={`py-2 text-right font-mono ${tone(g.net)}`}>{signedMoney(g.net)}</td>
        </tr>
    )
}

function BetsTable() {
    const { data, isLoading, error } = useBets()
    const [league, setLeague] = useState('all')
    const [ended, setEnded] = useState('all')
    const [tagFilter, setTagFilter] = useState('all')
    const setNote = useSetBetNote()
    const [limit, setLimit] = useState(40)

    if (isLoading) return <p className="text-sm text-slate-500">Loading your bets…</p>
    if (error || !data) return <p className="text-sm text-rose-400">Could not load your bets.</p>

    const leagues = ['all', ...Array.from(new Set(data.bets.map((b) => b.league))).sort()]
    const rows: Bet[] = data.bets.filter(
        (b) => (league === 'all' || b.league === league) && (ended === 'all' || b.how_ended === ended) && (tagFilter === 'all' || b.tag === tagFilter)
    )
    const decided = rows.filter((b) => b.pnl !== null)
    const wins = decided.filter((b) => (b.pnl ?? 0) > 0).length
    const net = decided.reduce((acc, b) => acc + (b.pnl ?? 0), 0)
    const select = 'bg-surface-900/90 border border-white/10 rounded-lg px-2 py-1 text-xs font-mono text-slate-300'

    return (
        <div>
            <div className="flex flex-wrap gap-3 mb-3 text-xs font-mono">
                {Object.entries(data.by_tag).map(([tag, t]) => (
                    <div key={tag} className="rounded-lg bg-surface-900/70 border border-white/10 px-3 py-1.5">
                        <span className={tag === 'vibe' ? 'text-fuchsia-300' : tag === 'hedge' ? 'text-sky-300' : 'text-slate-300'}>{tag}</span>
                        <span className="text-slate-400">
                            {' '}· {t.bets} bets · {t.win_rate === null ? '-' : `${Math.round(t.win_rate * 100)}% win`} ·{' '}
                        </span>
                        <span className={tone(t.pnl)}>{signedMoney(t.pnl)}</span>
                    </div>
                ))}
            </div>
            <div className="flex flex-wrap items-center gap-3 mb-3 text-xs font-mono text-slate-400">
                <select className={select} value={league} onChange={(e) => setLeague(e.target.value)}>
                    {leagues.map((l) => (
                        <option key={l} value={l}>{l === 'all' ? 'all sports' : l}</option>
                    ))}
                </select>
                <select className={select} value={ended} onChange={(e) => setEnded(e.target.value)}>
                    <option value="all">all outcomes</option>
                    <option value="sold">sold</option>
                    <option value="settled">held to settlement</option>
                    <option value="open">open</option>
                </select>
                <select className={select} value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
                    <option value="all">all types</option>
                    <option value="analysis">analysis only</option>
                    <option value="vibe">vibe only</option>
                    <option value="hedge">hedge only</option>
                </select>
                <span>
                    {rows.length} bets · {decided.length ? `${((wins / decided.length) * 100).toFixed(0)}% win` : 'no result yet'} ·{' '}
                    <span className={tone(net)}>{signedMoney(net)}</span>
                </span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-[11px] uppercase tracking-wider text-slate-500 font-mono">
                            <th className="text-left font-normal pb-2 pr-3">Opened (UTC)</th>
                            <th className="text-left font-normal pb-2 pr-3">Type</th>
                            <th className="text-left font-normal pb-2 pr-3">Why ended</th>
                            <th className="text-left font-normal pb-2 pr-3">Sport</th>
                            <th className="text-left font-normal pb-2 pr-3">Backed</th>
                            <th className="text-right font-normal pb-2 pr-3">Legs</th>
                            <th className="text-right font-normal pb-2 pr-3">Paid</th>
                            <th className="text-right font-normal pb-2 pr-3">Stake</th>
                            <th className="text-right font-normal pb-2 pr-3">Real cash</th>
                            <th className="text-right font-normal pb-2 pr-3">Bonus</th>
                            <th className="text-right font-normal pb-2 pr-3">Multiplier</th>
                            <th className="text-left font-normal pb-2 pr-3">Ended</th>
                            <th className="text-right font-normal pb-2 pr-3">Exit</th>
                            <th className="text-right font-normal pb-2 pr-3">Payout</th>
                            <th className="text-right font-normal pb-2 pr-3">Profit</th>
                            <th className="text-right font-normal pb-2 pr-3">Return</th>
                            <th className="text-right font-normal pb-2">Hold</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.slice(0, limit).map((b) => (
                            <tr key={`${b.slug}-${b.opened_at}`} className="border-t border-white/5">
                                <td className="py-1.5 pr-3 font-mono text-slate-400 whitespace-nowrap">{b.opened_at.slice(5, 16).replace('T', ' ')}</td>
                                <td className="py-1.5 pr-3">
                                    <button
                                        onClick={() => setNote.mutate({ bet_key: b.bet_key, tag: NEXT_TAG[b.tag] })}
                                        title="Click to cycle: analysis, vibe, hedge"
                                        className={`px-2 py-0.5 rounded-md text-[11px] font-bold border ${TAG_TONE[b.tag]}`}
                                    >
                                        {b.tag}
                                    </button>
                                </td>
                                <td className="py-1.5 pr-3">
                                    {b.how_ended === 'open' ? (
                                        <span className="text-slate-600">-</span>
                                    ) : (
                                        <select
                                            value={b.why_ended ?? ''}
                                            onChange={(e) =>
                                                e.target.value
                                                    ? setNote.mutate({ bet_key: b.bet_key, why_ended: e.target.value as NonNullable<Bet['why_ended']> })
                                                    : setNote.mutate({ bet_key: b.bet_key, clear_why: true })
                                            }
                                            className="bg-transparent border border-white/10 rounded-md px-1 py-0.5 text-[11px] text-slate-300"
                                        >
                                            <option value="">-</option>
                                            <option value="bounce">sold into a bounce</option>
                                            <option value="target">hit my number</option>
                                            <option value="cut">cut a dying leg</option>
                                            <option value="held">held on purpose</option>
                                        </select>
                                    )}
                                </td>
                                <td className="py-1.5 pr-3 uppercase text-slate-300">{b.league}</td>
                                <td className="py-1.5 pr-3 text-slate-200 max-w-[260px] truncate" title={b.title}>
                                    {b.kind === 'combo' ? `${b.legs}-leg combo` : b.backed || b.title}
                                </td>
                                <td className="py-1.5 pr-3 text-right font-mono text-slate-300">{b.kind === 'combo' ? b.legs : '-'}</td>
                                <td className="py-1.5 pr-3 text-right font-mono">{(b.price_paid * 100).toFixed(0)}¢</td>
                                <td className="py-1.5 pr-3 text-right font-mono">{money(b.stake)}</td>
                                <td className="py-1.5 pr-3 text-right font-mono text-emerald-300">{money(b.real_cash)}</td>
                                <td className="py-1.5 pr-3 text-right font-mono text-sky-300">{money(b.bonus_credit)}</td>
                                <td className="py-1.5 pr-3 text-right font-mono text-amber-300">{b.multiplier === null ? '-' : `${b.multiplier.toFixed(1)}x`}</td>
                                <td className="py-1.5 pr-3 text-slate-400">{b.how_ended}</td>
                                <td className="py-1.5 pr-3 text-right font-mono">{b.exit_price === null ? '-' : `${(b.exit_price * 100).toFixed(0)}¢`}</td>
                                <td className="py-1.5 pr-3 text-right font-mono">{b.pnl === null ? '-' : money(b.stake + b.pnl)}</td>
                                <td className={`py-1.5 pr-3 text-right font-mono ${tone(b.pnl)}`}>{signedMoney(b.pnl)}</td>
                                <td className={`py-1.5 pr-3 text-right font-mono ${tone(b.return)}`}>{b.return === null ? '-' : `${(b.return * 100).toFixed(0)}%`}</td>
                                <td className="py-1.5 text-right font-mono text-slate-400">{b.hold_minutes === null ? '-' : `${b.hold_minutes.toFixed(0)}m`}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {rows.length > limit && (
                <button
                    onClick={() => setLimit(limit + 40)}
                    className="mt-3 text-xs font-mono text-slate-400 hover:text-white"
                >
                    Show more ({rows.length - limit} left)
                </button>
            )}
        </div>
    )
}

export default function AccountPage() {
    const { data, isLoading, error } = useAccount()
    const queryClient = useQueryClient()
    const [refreshing, setRefreshing] = useState(false)

    const refresh = async () => {
        setRefreshing(true)
        try {
            const fresh = await fetchAccount(true)
            queryClient.setQueryData(['account', 'summary'], fresh)
        } finally {
            setRefreshing(false)
        }
    }

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-24 text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Reading your account…</span>
            </div>
        )
    }

    if (error || !data) {
        return (
            <div className="glass-card rounded-2xl p-6 border border-rose-500/30 text-rose-300">
                {error instanceof Error ? error.message : 'Could not load the account.'}
            </div>
        )
    }

    const { balance, open_positions: open, cash_flows: cash, trading } = data
    const heldBack = balance.bonus_hold > balance.current
    const updated = new Date(data.fetched_at * 1000).toLocaleTimeString()

    return (
        <div className="max-w-[1920px] mx-auto px-4 py-6 grid grid-cols-12 gap-4">
            {/* Account — left side */}
            <div className="col-span-12 space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-200">
                    <Wallet className="w-5 h-5 text-emerald-400" />
                    <h1 className="text-base font-bold font-display tracking-tight">My Account</h1>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={refresh}
                        disabled={refreshing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-900/90 border border-white/10 text-xs font-mono text-slate-300 hover:text-white disabled:opacity-50"
                    >
                        <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                        <span>Updated {updated}</span>
                    </button>
                </div>
            </div>

            <AlertsPanel />

            <Section title="Balance & withdrawals">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <Stat label="Balance" value={money(balance.current)} sub="available to bet" />
                    <Stat label="Real cash" value={money(balance.cash)} sub="debited before bonus" />
                    <Stat label="Bonus credit" value={money(balance.bonus)} />
                    <Stat label="Bonus hold" value={money(balance.bonus_hold)} sub="locked, releases as you trade" />
                    <Stat
                        label="Withdrawable (platform)"
                        value={money(balance.available_to_withdraw)}
                        valueClass={tone(balance.available_to_withdraw)}
                    />
                    <Stat
                        label="Balance minus hold"
                        value={money(balance.model_withdrawable)}
                        sub={heldBack ? 'balance is below the hold' : 'your working model'}
                        valueClass={tone(balance.model_withdrawable)}
                    />
                    <Stat label="Open positions" value={money(open.value)} sub={`cost ${money(open.cost)} · ${open.count} open`} />
                    <Stat label="Fees paid" value={money(trading.fees_paid)} sub={`${trading.total_fills} fills`} />
                </div>
            </Section>

            <Section title="Cash flows">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <Stat label="Deposited" value={money(cash.deposits)} />
                    <Stat label="Withdrawn" value={money(cash.withdrawals)} />
                    <Stat label="Net cash received" value={signedMoney(cash.net_cash_out)} valueClass={tone(cash.net_cash_out)} sub="withdrawn minus deposited" />
                    <Stat label="Total gain" value={signedMoney(cash.total_gain)} valueClass={tone(cash.total_gain)} sub="cash + balance + open positions" />
                    <Stat label="Match bonuses" value={money(cash.deposit_match_bonuses)} />
                    <Stat label="Referral bonuses" value={money(cash.referral_bonuses)} />
                    <Stat label="Bonuses credited" value={money(cash.bonuses)} />
                    <Stat label="Trading gain" value={signedMoney(cash.profit_excluding_bonuses)} valueClass={tone(cash.profit_excluding_bonuses)} sub="total gain minus bonuses" />
                </div>
            </Section>

            <Section title={`Open positions (${open.count})`}>
                {open.items.length === 0 ? (
                    <p className="text-sm text-slate-500">Nothing open.</p>
                ) : (
                    <div className="space-y-3">
                        {open.items.map((p) => (
                            <div key={p.slug} className="rounded-xl bg-surface-900/70 border border-white/10 p-3">
                                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                                    <span className="font-mono text-slate-400 truncate">{p.title || p.slug}</span>
                                    <span className="font-mono text-slate-200 flex items-center gap-3">
                                        {p.contracts.toFixed(0)} contracts @ {(p.avg_price * 100).toFixed(1)}¢ · cost {money(p.cost)} · now {money(p.value)}
                                        <a
                                            href={`https://polymarket.us/event/${p.slug}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            title="Open this market on Polymarket US"
                                            className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-primary-500/15 text-primary-300 border border-primary-500/30 hover:bg-primary-500/25 hover:text-primary-200 transition-colors"
                                        >
                                            open ↗
                                        </a>
                                    </span>
                                </div>
                                {p.legs.length > 0 && (
                                    <ul className="mt-2 space-y-1 text-xs">
                                        {p.legs.map((leg, i) => (
                                            <li key={i} className="flex justify-between gap-3 text-slate-400">
                                                <span className="min-w-0 flex items-center gap-2">
                                                    <span className="block truncate">{leg.title} · {leg.outcome}</span>
                                                    {leg.live && <LiveLine live={leg.live} />}
                                                </span>
                                                <span className="flex items-center gap-2">
                                                    <span
                                                        className={
                                                            leg.state === 'WON'
                                                                ? 'text-emerald-400'
                                                                : leg.state === 'LOST'
                                                                  ? 'text-rose-400'
                                                                  : 'text-slate-500'
                                                        }
                                                    >
                                                        {leg.state || 'LIVE'}
                                                    </span>
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Section>

            <Section title="Your bets">
                <BetsTable />
            </Section>

            <Section title="Trading results" >
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                    <Stat
                        label="All decided bets"
                        value={signedMoney(trading.all.net)}
                        valueClass={tone(trading.all.net)}
                        sub={`${trading.all.n} bets · ${percent(trading.all.win_rate)} win · ${trading.open} open`}
                    />
                    <Stat
                        label="Sold before the end"
                        value={signedMoney(trading.sold.net)}
                        valueClass={tone(trading.sold.net)}
                        sub={`${trading.sold.n} bets · ${percent(trading.sold.win_rate)} win`}
                    />
                    <Stat
                        label="Held to settlement"
                        value={signedMoney(trading.settled.net)}
                        valueClass={tone(trading.settled.net)}
                        sub={`${trading.settled.n} bets · ${percent(trading.settled.win_rate)} win`}
                    />
                    <Stat
                        label="Median hold (sold)"
                        value={trading.hold_minutes_sold.median === null ? '-' : `${trading.hold_minutes_sold.median.toFixed(0)} min`}
                        sub={
                            trading.hold_minutes_sold.p25 === null || trading.hold_minutes_sold.p75 === null
                                ? undefined
                                : `middle half ${trading.hold_minutes_sold.p25.toFixed(0)}-${trading.hold_minutes_sold.p75.toFixed(0)} min`
                        }
                    />
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-[11px] uppercase tracking-wider text-slate-500 font-mono">
                                <th className="text-left font-normal pb-2">Group</th>
                                <th className="text-right font-normal pb-2 pr-3">Decided</th>
                                <th className="text-right font-normal pb-2 pr-3">Win rate</th>
                                <th className="text-right font-normal pb-2 pr-3">Avg win</th>
                                <th className="text-right font-normal pb-2 pr-3">Avg loss</th>
                                <th className="text-right font-normal pb-2 pr-3">Best</th>
                                <th className="text-right font-normal pb-2 pr-3">Worst</th>
                                <th className="text-right font-normal pb-2">Net</th>
                            </tr>
                        </thead>
                        <tbody>
                            {Object.entries(trading.by_kind)
                                .filter(([, g]) => g.n > 0)
                                .map(([k, g]) => (
                                    <GroupRow key={`k-${k}`} label={k} g={g} />
                                ))}
                            {Object.entries(trading.by_legs)
                                .filter(([, g]) => g.n > 0)
                                .map(([n, g]) => (
                                    <GroupRow key={`n-${n}`} label={`${n}-leg combo`} g={g} />
                                ))}
                            {Object.entries(trading.by_league)
                                .filter(([, g]) => g.n > 0)
                                .sort(([, a], [, b]) => b.n - a.n)
                                .map(([l, g]) => (
                                    <GroupRow key={`l-${l}`} label={l} g={g} />
                                ))}
                        </tbody>
                    </table>
                </div>
            </Section>
            </div>

        </div>
    )
}

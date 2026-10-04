import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { FootballLeague, FootballTeamRow, RankedValue, useFootballTeams } from '../hooks/useFootballTeams'
import TeamStatTable, { Cell, Group } from './TeamStatTable'
import { tierGroup } from './TierSelect'
import { useSetTier, useTiers } from '../hooks/useTiers'

const wl = (p: [number, number] | undefined | null): string => (p ? `${p[0]}-${p[1]}` : '-')
const pctOf = (p: [number, number]): string => (p[0] + p[1] ? `${Math.round((p[0] / (p[0] + p[1])) * 100)}%` : '-')
const signed = (n: number, d = 1): string => `${n >= 0 ? '+' : ''}${n.toFixed(d)}`

const val = (get: (t: FootballTeamRow) => RankedValue | null, digits = 1, suffix = '') => (t: FootballTeamRow): Cell => {
    const v = get(t)
    return v ? { text: `${v.value.toFixed(digits)}${suffix}`, rank: v.rank ?? undefined } : { text: '-' }
}

const GROUPS: Group<FootballTeamRow>[] = [
    {
        title: 'Record & form',
        accent: 'text-sky-300',
        columns: [
            { label: 'Record', cell: (t) => ({ text: wl([t.record.wins, t.record.losses]), rank: t.record.rank }) },
            { label: 'AP', cell: (t) => ({ text: t.ap_rank ? `#${t.ap_rank}` : '-' }) },
            { label: 'Pt diff / g', cell: (t) => (t.diff ? { text: signed(t.diff.value), rank: t.diff.rank ?? undefined } : { text: '-' }) },
            { label: 'Last 3', cell: (t) => ({ text: wl(t.form.last_3) }) },
            { label: 'Last 5', cell: (t) => ({ text: wl(t.form.last_5) }) },
            { label: 'Home', cell: (t) => ({ text: wl(t.splits.home) }) },
            { label: 'Road', cell: (t) => ({ text: wl(t.splits.road) }) },
        ],
    },
    {
        title: 'Who they beat',
        accent: 'text-amber-300',
        columns: [
            { label: 'vs ranked', cell: (t) => ({ text: wl(t.quality.vs_ranked) }) },
            { label: 'vs .500+', cell: (t) => ({ text: wl(t.quality.vs_winning), note: pctOf(t.quality.vs_winning) }) },
            {
                label: 'Avg opponent',
                cell: (t) => ({
                    text: t.quality.avg_opp_pct === null ? '-' : t.quality.avg_opp_pct.toFixed(3).replace(/^0/, ''),
                    note: `${t.quality.known_games} of ${t.record.wins + t.record.losses} games`,
                }),
            },
            { label: 'vs non-FBS', cell: (t) => ({ text: wl(t.quality.outside_league) }) },
        ],
    },
    {
        title: 'Offense',
        accent: 'text-emerald-300',
        columns: [
            { label: 'Pts / g', cell: val((t) => t.offense.ppg) },
            { label: 'Yds / g', cell: val((t) => t.offense.yds, 0) },
            { label: 'Pass yds / g', cell: val((t) => t.offense.pass_yds, 0) },
            { label: 'Rush yds / g', cell: val((t) => t.offense.rush_yds, 0) },
            { label: '3rd down', cell: val((t) => t.offense.third_pct, 1, '%') },
        ],
    },
    {
        title: 'Defense & turnovers',
        accent: 'text-rose-300',
        columns: [
            { label: 'Pts allowed / g', cell: val((t) => t.defense.papg) },
            { label: 'Sacks / g', cell: val((t) => t.defense.sacks, 2) },
            { label: 'Takeaways / g', cell: val((t) => t.defense.takeaways, 2) },
            { label: 'Giveaways / g', cell: val((t) => t.defense.giveaways, 2) },
            { label: 'TO margin / g', cell: (t) => (t.defense.turnover_margin ? { text: signed(t.defense.turnover_margin.value, 2), rank: t.defense.turnover_margin.rank ?? undefined } : { text: '-' }) },
        ],
    },
    {
        title: 'Next game',
        accent: 'text-cyan-300',
        columns: [
            {
                label: 'Opponent',
                cell: (t) => {
                    const g = t.next_game
                    if (!g) return { text: '-' }
                    const where = g.home === null ? 'vs' : g.home ? 'vs' : '@'
                    const rank = g.opp_rank && g.opp_rank !== 99 ? ` (#${g.opp_rank})` : ''
                    return { text: `${where} ${g.opponent.split(' ').slice(0, -1).join(' ') || g.opponent}${rank}` }
                },
            },
            { label: 'Date', cell: (t) => ({ text: t.next_game ? new Date(t.next_game.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '-' }) },
        ],
    },
]

const NFL_FILTERS = ['All', 'AFC', 'NFC']

export default function FootballTeamsPage({ league }: { league: FootballLeague }) {
    const { data, isLoading, error } = useFootballTeams(league)
    const [filter, setFilter] = useState<string>(league === 'cfb' ? 'SEC' : 'All')
    const [sortBy, setSortBy] = useState<'record' | 'tier'>('record')
    const { data: tiers } = useTiers(league)
    const setTier = useSetTier(league)

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-24 text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>{league === 'cfb' ? 'Reading every FBS team…' : 'Building the NFL table…'}</span>
            </div>
        )
    }
    if (error || !data) {
        return <div className="glass-card rounded-2xl p-6 border border-rose-500/30 text-rose-300">{error instanceof Error ? error.message : 'Could not load the team table.'}</div>
    }

    const filters = league === 'cfb' ? ['Top 25', 'All FBS', ...data.groups] : [...NFL_FILTERS, ...data.groups]
    const inFilter = (t: FootballTeamRow): boolean => {
        if (filter === 'All' || filter === 'All FBS') return true
        if (filter === 'Top 25') return t.ap_rank !== null
        if (filter === 'AFC' || filter === 'NFC') return t.conference.startsWith(filter)
        return t.conference === filter
    }
    const tierOf = (t: FootballTeamRow): number => tiers?.[t.id]?.tier ?? 0
    const byRecord = (a: FootballTeamRow, b: FootballTeamRow): number =>
        filter === 'Top 25' ? (a.ap_rank ?? 99) - (b.ap_rank ?? 99) : b.record.pct - a.record.pct || (b.diff?.value ?? 0) - (a.diff?.value ?? 0)
    const rows = data.teams
        .filter(inFilter)
        .sort((a, b) => (sortBy === 'tier' ? tierOf(b) - tierOf(a) || byRecord(a, b) : byRecord(a, b)))
    const groups = [...GROUPS, tierGroup<FootballTeamRow>((t) => t.id, tiers, (id, tier) => setTier.mutate({ teamId: id, tier }))]

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
                {filters.map((f) => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-3 py-1 rounded-lg text-xs font-bold font-display border transition-colors ${
                            filter === f
                                ? 'bg-primary-500/30 text-white border-primary-500/50'
                                : 'text-slate-400 border-white/10 hover:text-white'
                        }`}
                    >
                        {f}
                    </button>
                ))}
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as 'record' | 'tier')}
                    className="bg-surface-900/90 border border-white/10 rounded-lg px-2 py-1 text-xs font-mono text-slate-300"
                >
                    <option value="record">sort: record</option>
                    <option value="tier">sort: my program tier</option>
                </select>
                <span className="ml-auto text-[11px] font-mono text-slate-500">
                    {rows.length} teams · small number = rank among {data.league_size} · <span className="text-emerald-300">top 5</span> /{' '}
                    <span className="text-rose-300">bottom 5</span>
                </span>
            </div>
            <TeamStatTable
                teams={rows}
                groups={groups}
                size={data.league_size}
                rowKey={(t) => t.id}
                teamCell={(t) => ({ name: t.team, sub: t.conference })}
            />
        </div>
    )
}

import { Loader2, Trophy } from 'lucide-react'
import { MlbTeamRow, StatKey, useMlbTeams } from '../hooks/useMlbTeams'
import TeamStatTable, { Cell, Group } from './TeamStatTable'
import { tierGroup } from './TierSelect'
import { useSetTier, useTiers } from '../hooks/useTiers'

const wl = (pair: [number, number] | { wins: number; losses: number } | undefined | null): string => {
    if (!pair) return '-'
    return Array.isArray(pair) ? `${pair[0]}-${pair[1]}` : `${pair.wins}-${pair.losses}`
}

const pctOf = (pair: [number, number]): string => {
    const total = pair[0] + pair[1]
    return total ? `${Math.round((pair[0] / total) * 100)}%` : '-'
}

const stat = (window: 'season' | 'sept', key: StatKey, digits: number, strip = false) => (t: MlbTeamRow): Cell => {
    const s = t[window][key]
    const text = s.value.toFixed(digits)
    return { text: strip ? text.replace(/^0/, '') : text, rank: s.rank }
}

const formCell = (key: string) => (t: MlbTeamRow): Cell => {
    const f = t.form[key]
    return { text: f ? `${f.wins}-${f.losses}` : '-', note: f ? `${f.rf.toFixed(1)} / ${f.ra.toFixed(1)}` : undefined }
}

const era = (s: { era?: number | null } | null | undefined): string =>
    s?.era === null || s?.era === undefined ? '-' : s.era.toFixed(2)

const GROUPS: Group<MlbTeamRow>[] = [
    {
        title: 'Record & form',
        accent: 'text-sky-300',
        columns: [
            { label: 'Season', cell: (t) => ({ text: wl(t.record), rank: t.record.rank, note: `${(t.record.pct * 1000).toFixed(0)}` }) },
            { label: 'Run diff / game', cell: (t) => ({ text: `${t.record.run_diff_per_game >= 0 ? '+' : ''}${t.record.run_diff_per_game.toFixed(2)}` }) },
            { label: 'September', cell: (t) => ({ text: wl(t.september) }) },
            { label: 'Last 10', cell: formCell('last_10') },
            { label: 'Last 20', cell: formCell('last_20') },
            { label: 'Last 50', cell: formCell('last_50') },
            { label: 'Best 40', cell: (t) => ({ text: wl(t.swing?.best) }) },
            { label: 'Worst 40', cell: (t) => ({ text: wl(t.swing?.worst) }) },
        ],
    },
    {
        title: 'Who they beat',
        accent: 'text-amber-300',
        columns: [
            { label: 'vs .500+', cell: (t) => ({ text: wl(t.quality.vs_above_500), note: pctOf(t.quality.vs_above_500) }) },
            { label: 'vs top 12', cell: (t) => ({ text: wl(t.quality.vs_top_12), note: pctOf(t.quality.vs_top_12) }) },
            { label: 'vs bottom 10', cell: (t) => ({ text: wl(t.quality.vs_bottom_10), note: pctOf(t.quality.vs_bottom_10) }) },
            { label: 'Avg opponent', cell: (t) => ({ text: t.quality.avg_opponent_pct === null ? '-' : t.quality.avg_opponent_pct.toFixed(3).replace(/^0/, '') }) },
        ],
    },
    {
        title: 'Offense',
        accent: 'text-emerald-300',
        columns: [
            { label: 'Sept R/G', cell: stat('sept', 'rpg', 2) },
            { label: 'Sept OPS', cell: stat('sept', 'ops', 3, true) },
            { label: 'Sept AVG', cell: stat('sept', 'avg', 3, true) },
            { label: 'Season R/G', cell: stat('season', 'rpg', 2) },
            { label: 'Season OPS', cell: stat('season', 'ops', 3, true) },
        ],
    },
    {
        title: 'Pitching',
        accent: 'text-rose-300',
        columns: [
            { label: 'Sept ERA', cell: stat('sept', 'era', 2) },
            { label: 'Sept WHIP', cell: stat('sept', 'whip', 2) },
            { label: 'Season ERA', cell: stat('season', 'era', 2) },
            { label: 'Season WHIP', cell: stat('season', 'whip', 2) },
        ],
    },
    {
        title: 'Defense',
        accent: 'text-violet-300',
        columns: [
            { label: 'Sept Fld%', cell: stat('sept', 'fld', 3, true) },
            { label: 'Sept Err/G', cell: stat('sept', 'errors_pg', 2) },
            { label: 'Season Fld%', cell: stat('season', 'fld', 3, true) },
            { label: 'Season Err/G', cell: stat('season', 'errors_pg', 2) },
        ],
    },
    {
        title: 'Next game',
        accent: 'text-cyan-300',
        columns: [
            { label: 'Opponent', cell: (t) => ({ text: t.next_game ? `${t.next_game.home ? 'vs' : '@'} ${t.next_game.opponent.split(' ').slice(-1)[0]}` : '-', note: t.next_game ? `G${t.next_game.game ?? '?'}` : undefined }) },
            { label: 'Starter (ERA)', cell: (t) => ({ text: t.next_game?.own_starter ? `${t.next_game.own_starter.name.split(' ').slice(-1)[0]} ${era(t.next_game.own_starter)}` : 'TBD' }) },
            { label: 'Their starter (ERA)', cell: (t) => ({ text: t.next_game?.opp_starter ? `${t.next_game.opp_starter.name.split(' ').slice(-1)[0]} ${era(t.next_game.opp_starter)}` : 'TBD' }) },
            { label: 'Series', cell: (t) => ({ text: t.next_game?.series || '-' }) },
        ],
    },
]

export default function MlbTeamsPage() {
    const { data, isLoading, error } = useMlbTeams()
    const { data: tiers } = useTiers('mlb')
    const setTier = useSetTier('mlb')

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-24 text-slate-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Building the team table…</span>
            </div>
        )
    }
    if (error || !data) {
        return (
            <div className="max-w-[1400px] mx-auto px-4 py-6">
                <div className="glass-card rounded-2xl p-6 border border-rose-500/30 text-rose-300">
                    {error instanceof Error ? error.message : 'Could not load the team table.'}
                </div>
            </div>
        )
    }

    const size = data.league_size
    const teams = [...data.teams].sort((a, b) => b.record.pct - a.record.pct)

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-slate-200">
                    <Trophy className="w-5 h-5 text-amber-400" />
                    <h1 className="text-lg font-black font-display tracking-tight">Playoff teams ({teams.length})</h1>
                </div>
                <p className="text-[11px] font-mono text-slate-500">
                    Small number = rank among all {size} teams, <span className="text-emerald-300">top 5</span> /{' '}
                    <span className="text-rose-300">bottom 5</span>. September = Sept 1 to the end of the regular season.
                    Form windows show runs scored / allowed per game underneath.
                </p>
            </div>

            <TeamStatTable
                teams={teams}
                groups={[...GROUPS, tierGroup<MlbTeamRow>((t) => String(t.id), tiers, (id, tier) => setTier.mutate({ teamId: id, tier }))]}
                size={size}
                rowKey={(t) => t.team}
                teamCell={(t) => ({ name: t.team, sub: `${t.round}${t.california ? ' · California' : ''}` })}
            />
        </div>
    )
}

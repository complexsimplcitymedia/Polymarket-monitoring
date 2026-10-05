import { ReactNode } from 'react'
import { Market } from '../stores/marketStore'
import { marketSides } from '../utils/sides'
import { FootballLeague, FootballTeamRow, useFootballTeams } from '../hooks/useFootballTeams'
import { MlbTeamRow, useMlbTeams } from '../hooks/useMlbTeams'
import { TierLeague, useSetTier, useTiers } from '../hooks/useTiers'
import { TierSelect } from './TierSelect'

const norm = (s: string): string => s.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim()

/** The team whose full name starts with the market's side name; the shortest wins ("Florida" over "Florida State"). */
function findTeam<T extends { team: string }>(teams: T[] | undefined, side: string): T | undefined {
    if (!teams) return undefined
    const n = norm(side)
    if (!n) return undefined
    const exact = teams.find((t) => norm(t.team) === n)
    if (exact) return exact
    return teams
        .filter((t) => norm(t.team).startsWith(`${n} `) || norm(t.team) === n)
        .sort((a, b) => a.team.length - b.team.length)[0]
}

interface Row {
    label: string
    a: ReactNode
    b: ReactNode
}

const wl = (p: [number, number] | undefined): string => (p ? `${p[0]}-${p[1]}` : '-')
const rk = (v: { value: number; rank: number | null } | null | undefined, d = 1, pre = ''): string =>
    v ? `${pre}${v.value.toFixed(d)}${v.rank ? ` (#${v.rank})` : ''}` : '-'

function footballRows(a: FootballTeamRow, b: FootballTeamRow): Row[] {
    const pair = (label: string, f: (t: FootballTeamRow) => ReactNode): Row => ({ label, a: f(a), b: f(b) })
    return [
        pair('Record', (t) => `${t.record.wins}-${t.record.losses}${t.ap_rank ? `  ·  AP #${t.ap_rank}` : ''}`),
        pair('Conference', (t) => t.conference),
        pair('Point diff / game', (t) => rk(t.diff, 1, t.diff && t.diff.value >= 0 ? '+' : '')),
        pair('Last 5', (t) => wl(t.form.last_5)),
        pair('Home / road', (t) => `${wl(t.splits.home)} / ${wl(t.splits.road)}`),
        pair('vs ranked / vs .500+', (t) => `${wl(t.quality.vs_ranked)} / ${wl(t.quality.vs_winning)}`),
        pair('Points / game', (t) => rk(t.offense.ppg)),
        pair('Points allowed / game', (t) => rk(t.defense.papg)),
        pair('Turnover margin / game', (t) => rk(t.defense.turnover_margin, 2, t.defense.turnover_margin && t.defense.turnover_margin.value >= 0 ? '+' : '')),
    ]
}

function mlbRows(a: MlbTeamRow, b: MlbTeamRow): Row[] {
    const pair = (label: string, f: (t: MlbTeamRow) => ReactNode): Row => ({ label, a: f(a), b: f(b) })
    const form = (k: string) => (t: MlbTeamRow) => (t.form[k] ? `${t.form[k].wins}-${t.form[k].losses}` : '-')
    return [
        pair('Season', (t) => `${t.record.wins}-${t.record.losses} (#${t.record.rank})`),
        pair('September', (t) => `${t.september.wins}-${t.september.losses}`),
        pair('Last 10 / last 20', (t) => `${form('last_10')(t)} / ${form('last_20')(t)}`),
        pair('vs top-12 teams', (t) => wl(t.quality.vs_top_12)),
        pair('Sept runs / game', (t) => rk(t.sept.rpg, 2)),
        pair('Sept OPS', (t) => rk(t.sept.ops, 3)),
        pair('Sept ERA', (t) => rk(t.sept.era, 2)),
        pair('Next starter (ERA)', (t) => (t.next_game?.own_starter ? `${t.next_game.own_starter.name.split(' ').slice(-1)[0]} ${t.next_game.own_starter.era?.toFixed(2) ?? '-'}` : 'TBD')),
    ]
}

function Table({ title, league, aName, bName, aId, bId, rows }: {
    title: string
    league: TierLeague
    aName: string
    bName: string
    aId: string
    bId: string
    rows: Row[]
}) {
    const { data: tiers } = useTiers(league)
    const setTier = useSetTier(league)
    return (
        <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-slate-500 mb-2">{title}</div>
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-left text-xs text-slate-400 font-mono">
                        <th className="font-normal pb-2" />
                        <th className="font-semibold text-slate-100 pb-2 pr-3">{aName}</th>
                        <th className="font-semibold text-slate-100 pb-2">{bName}</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r) => (
                        <tr key={r.label} className="border-t border-white/5">
                            <td className="py-1.5 pr-3 text-xs text-slate-500 font-mono whitespace-nowrap">{r.label}</td>
                            <td className="py-1.5 pr-3 font-mono text-slate-200">{r.a}</td>
                            <td className="py-1.5 font-mono text-slate-200">{r.b}</td>
                        </tr>
                    ))}
                    <tr className="border-t border-white/5">
                        <td className="py-1.5 pr-3 text-xs text-fuchsia-300 font-mono whitespace-nowrap">Your program tier</td>
                        <td className="py-1.5 pr-3">
                            <TierSelect value={tiers?.[aId]?.tier} onChange={(tier) => setTier.mutate({ teamId: aId, tier })} />
                        </td>
                        <td className="py-1.5">
                            <TierSelect value={tiers?.[bId]?.tier} onChange={(tier) => setTier.mutate({ teamId: bId, tier })} />
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    )
}

/** For a game market: video hero left, the teams' numbers right — the Polymarket event layout. */
export default function MatchupPanel({ market }: { market: Market | null }) {
    const sides = market ? marketSides(market) : null
    const named = !!sides?.named
    const mlb = useMlbTeams(named)
    const nfl = useFootballTeams('nfl', named)
    const cfb = useFootballTeams('cfb', named)

    if (!market || !sides || !named) return null

    const layout = (sportLabel: string, league: TierLeague, aName: string, bName: string, aId: string, bId: string, rows: Row[]) => (
        <section className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl">
            <Table title={`Matchup · ${sportLabel.split('·')[0].trim()}`} league={league} aName={aName} bName={bName} aId={aId} bId={bId} rows={rows} />
        </section>
    )

    const fbLeagues: { league: FootballLeague; teams: FootballTeamRow[] | undefined; label: string }[] = [
        { league: 'cfb', teams: cfb.data?.teams, label: 'College football' },
        { league: 'nfl', teams: nfl.data?.teams, label: 'NFL' },
    ]
    for (const { league, teams, label } of fbLeagues) {
        const a = findTeam(teams, sides.a.label)
        const b = findTeam(teams, sides.b.label)
        if (a && b && a.id !== b.id) {
            return layout(label, league, a.team, b.team, a.id, b.id, footballRows(a, b))
        }
    }
    const ma = findTeam(mlb.data?.teams, sides.a.label)
    const mb = findTeam(mlb.data?.teams, sides.b.label)
    if (ma && mb && ma.team !== mb.team) {
        return layout('MLB', 'mlb', ma.team, mb.team, String(ma.id), String(mb.id), mlbRows(ma, mb))
    }
    return null
}
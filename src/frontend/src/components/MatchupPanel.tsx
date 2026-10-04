// LiveVideo: Polymarket-style game video hero for the Architect's own pipeline.
// The tablet (wolf-logic-tablet, running the paid MLB/TV app) is streamed over RFB 5900 on the
// tailnet; websockify on VM4 (:6900) bridges it to a websocket; noVNC renders it below.
// Video left, matchup numbers right — the same shape as the Polymarket event page.
import { useState, ReactNode } from 'react'
import { Market } from '../stores/marketStore'
import { marketSides } from '../utils/sides'
import { FootballLeague, FootballTeamRow, useFootballTeams } from '../hooks/useFootballTeams'
import { MlbTeamRow, useMlbTeams } from '../hooks/useMlbTeams'
import { TierLeague, useSetTier, useTiers } from '../hooks/useTiers'
import { TierSelect } from './TierSelect'

// Watch feed (Architect-supplied 2026-10-04): droidVNC-NG's own built-in noVNC client runs on the
// tablet itself — 100.110.82.108:5800 serves vnc.html and websockets to its VNC server on 5900.
// No bridge on VM4 needed. Access key rides as the password param, per the Architect's share link.
const WATCH_URL = 'http://100.110.82.108:5800/vnc.html?autoconnect=true&show_dot=true&host=100.110.82.108&port=5900'

/** The video hero: noVNC frame with the popup camera/link buttons and a live badge, Polymarket-style. */
function VideoHero({ title, subtitle }: { title: string; subtitle: string }) {
    const [reloadKey, setReloadKey] = useState(0)
    return (
        <div>
            <div className="relative rounded-2xl overflow-hidden bg-black border border-white/10 shadow-2xl">
                <iframe
                    key={reloadKey}
                    src={WATCH_URL}
                    title={title}
                    allow="autoplay; fullscreen; picture-in-picture"
                    allowFullScreen
                    className="w-full aspect-video block bg-black"
                />
                {/* Live badge, top-left */}
                <span className="absolute top-2.5 left-3 flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-sm border border-white/10">
                    <span className="relative flex h-1.5 w-1.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75" />
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-rose-500" />
                    </span>
                    <span className="text-[10px] font-bold font-mono text-white tracking-wider">LIVE</span>
                </span>
                {/* Popup controls, top-right: pop-out, focus, reload, fullscreen link */}
                <div className="absolute top-2.5 right-3 flex items-center gap-1.5">
                    <button
                        type="button"
                        title="Reload stream"
                        onClick={() => setReloadKey((k) => k + 1)}
                        className="w-7 h-7 grid place-items-center rounded-md bg-black/60 backdrop-blur-sm border border-white/10 text-slate-300 hover:text-white hover:bg-black/80 transition-colors text-xs"
                    >
                        ⟳
                    </button>
                    <a
                        href="/novnc/vnc.html?host=100.110.82.54&port=6900&autoconnect=1&resize=scale&view_only=0"
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open video in its own window"
                        className="w-7 h-7 grid place-items-center rounded-md bg-black/60 backdrop-blur-sm border border-white/10 text-slate-300 hover:text-white hover:bg-black/80 transition-colors text-xs"
                    >
                        ⧉
                    </a>
                </div>
            </div>
            {/* Under-video header: sport label left, actions right — mirrors the reference layout */}
            <div className="flex items-center justify-between mt-3 px-0.5">
                <span className="text-[11px] font-mono uppercase tracking-wider text-slate-500">{subtitle}</span>
                <div className="flex items-center gap-3 text-slate-500">
                    <a
                        href="https://www.mlb.com/tv"
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open the source broadcast"
                        className="hover:text-slate-200 transition-colors text-xs"
                    >
                        ▤
                    </a>
                    <a
                        href="https://polymarket.us"
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open Polymarket US"
                        className="hover:text-slate-200 transition-colors text-xs"
                    >
                        ⌁
                    </a>
                    <a
                        href="https://www.mlb.com/tv/schedule"
                        target="_blank"
                        rel="noopener noreferrer"
                        title="MLB.TV schedule — pick the game"
                        className="hover:text-slate-200 transition-colors text-xs"
                    >
                        ⇪
                    </a>
                </div>
            </div>
            <h2 className="mt-1 text-2xl sm:text-3xl font-black font-display tracking-tight text-white truncate">{title}</h2>
        </div>
    )
}

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
            <div className="grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(300px,2fr)] items-start">
                <VideoHero title={market.title} subtitle={sportLabel} />
                <div className="min-w-0">
                    <Table title={`Matchup · ${sportLabel.split('·')[0].trim()}`} league={league} aName={aName} bName={bName} aId={aId} bId={bId} rows={rows} />
                </div>
            </div>
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
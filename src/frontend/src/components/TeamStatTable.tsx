import { ReactNode } from 'react'

export interface Cell {
    text: string
    render?: ReactNode
    rank?: number
    note?: string
}

export interface Column<T> {
    label: string
    cell: (t: T) => Cell
}

export interface Group<T> {
    title: string
    accent: string
    columns: Column<T>[]
}

const rankTone = (rank: number | undefined, size: number): string => {
    if (rank === undefined) return 'text-slate-200'
    if (rank <= 5) return 'text-emerald-300'
    if (rank > size - 5) return 'text-rose-300'
    return 'text-slate-200'
}

interface Props<T> {
    teams: T[]
    groups: Group<T>[]
    size: number
    rowKey: (t: T) => string
    teamCell: (t: T) => { name: string; sub?: string; badge?: ReactNode }
}

export default function TeamStatTable<T>({ teams, groups, size, rowKey, teamCell }: Props<T>) {
    return (
        <div className="glass-card rounded-2xl border border-white/10 shadow-2xl overflow-x-auto">
            <table className="w-full text-sm border-collapse">
                <thead>
                    <tr>
                        <th className="sticky left-0 z-10 bg-surface-950 px-3 py-2" />
                        {groups.map((g) => (
                            <th
                                key={g.title}
                                colSpan={g.columns.length}
                                className={`px-3 py-2 text-left text-[11px] uppercase tracking-wider font-mono border-l border-white/10 ${g.accent}`}
                            >
                                {g.title}
                            </th>
                        ))}
                    </tr>
                    <tr className="text-[10px] uppercase tracking-wider text-slate-500 font-mono">
                        <th className="sticky left-0 z-10 bg-surface-950 px-3 pb-2 text-left font-normal">Team</th>
                        {groups.map((g) =>
                            g.columns.map((c, i) => (
                                <th
                                    key={`${g.title}-${c.label}`}
                                    className={`px-3 pb-2 text-right font-normal whitespace-nowrap ${i === 0 ? 'border-l border-white/10' : ''}`}
                                >
                                    {c.label}
                                </th>
                            ))
                        )}
                    </tr>
                </thead>
                <tbody>
                    {teams.map((t) => {
                        const head = teamCell(t)
                        return (
                            <tr key={rowKey(t)} className="border-t border-white/5 hover:bg-white/[0.03]">
                                <td className="sticky left-0 z-10 bg-surface-950 px-3 py-2 whitespace-nowrap">
                                    <div className="flex items-center gap-2">
                                        {head.badge}
                                        <div>
                                            <div className="font-semibold text-slate-100">{head.name}</div>
                                            {head.sub && <div className="text-[10px] font-mono text-slate-500">{head.sub}</div>}
                                        </div>
                                    </div>
                                </td>
                                {groups.map((g) =>
                                    g.columns.map((c, i) => {
                                        const cell = c.cell(t)
                                        return (
                                            <td
                                                key={`${rowKey(t)}-${g.title}-${c.label}`}
                                                className={`px-3 py-2 text-right font-mono whitespace-nowrap ${i === 0 ? 'border-l border-white/10' : ''}`}
                                            >
                                                {cell.render ?? <span className={rankTone(cell.rank, size)}>{cell.text}</span>}
                                                {cell.rank !== undefined && (
                                                    <sup className="ml-0.5 text-[9px] text-slate-500">{cell.rank}</sup>
                                                )}
                                                {cell.note && <div className="text-[10px] text-slate-500">{cell.note}</div>}
                                            </td>
                                        )
                                    })
                                )}
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

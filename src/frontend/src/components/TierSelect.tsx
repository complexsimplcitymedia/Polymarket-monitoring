import { Group } from './TeamStatTable'

interface Props {
    value: number | null | undefined
    onChange: (tier: number | null) => void
}

const TONE: Record<number, string> = {
    5: 'text-emerald-300 border-emerald-500/40',
    4: 'text-emerald-200 border-emerald-500/20',
    3: 'text-slate-200 border-white/15',
    2: 'text-amber-200 border-amber-500/20',
    1: 'text-rose-300 border-rose-500/30',
}

export function TierSelect({ value, onChange }: Props) {
    return (
        <select
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
            title="Your rating of this team's program: 1 weak, 5 elite"
            className={`bg-transparent border rounded-md px-1.5 py-0.5 text-xs font-mono ${value ? TONE[value] : 'text-slate-500 border-white/10'}`}
        >
            <option value="">-</option>
            {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>
                    {n}
                </option>
            ))}
        </select>
    )
}

export function tierGroup<T>(
    getId: (t: T) => string,
    tiers: Record<string, { tier: number | null }> | undefined,
    setTier: (teamId: string, tier: number | null) => void
): Group<T> {
    return {
        title: 'Your rating',
        accent: 'text-fuchsia-300',
        columns: [
            {
                label: 'Program tier',
                cell: (t) => ({
                    text: String(tiers?.[getId(t)]?.tier ?? '-'),
                    render: <TierSelect value={tiers?.[getId(t)]?.tier} onChange={(tier) => setTier(getId(t), tier)} />,
                }),
            },
        ],
    }
}

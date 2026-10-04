import { useState } from 'react'
import FootballTeamsPage from './FootballTeamsPage'
import MlbTeamsPage from './MlbTeamsPage'

type Sport = 'mlb' | 'cfb' | 'nfl'

const SPORTS: { key: Sport; label: string }[] = [
    { key: 'mlb', label: 'MLB playoffs' },
    { key: 'cfb', label: 'College football' },
    { key: 'nfl', label: 'NFL' },
]
const PLACEHOLDERS = ['NBA', 'College basketball']

export default function TeamsPage() {
    const [sport, setSport] = useState<Sport>('mlb')
    return (
        <div className="max-w-[1900px] mx-auto px-4 py-6 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                {SPORTS.map((s) => (
                    <button
                        key={s.key}
                        onClick={() => setSport(s.key)}
                        className={`px-4 py-1.5 rounded-xl text-sm font-bold font-display border transition-colors ${
                            sport === s.key
                                ? 'bg-amber-500/30 text-white border-amber-500/50'
                                : 'text-slate-400 border-white/10 hover:text-white'
                        }`}
                    >
                        {s.label}
                    </button>
                ))}
                {PLACEHOLDERS.map((p) => (
                    <span
                        key={p}
                        title="Not in season yet"
                        className="px-4 py-1.5 rounded-xl text-sm font-bold font-display border border-white/5 text-slate-600 cursor-not-allowed"
                    >
                        {p} <span className="text-[10px] font-mono">offseason</span>
                    </span>
                ))}
            </div>
            {sport === 'mlb' && <MlbTeamsPage />}
            {sport === 'cfb' && <FootballTeamsPage league="cfb" />}
            {sport === 'nfl' && <FootballTeamsPage league="nfl" />}
        </div>
    )
}

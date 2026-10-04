import { useQuery } from '@tanstack/react-query'

export interface RankedStat {
    value: number
    rank: number
}

export type StatKey = 'rpg' | 'ops' | 'avg' | 'era' | 'whip' | 'fld' | 'errors_pg'

export interface FormWindow {
    wins: number
    losses: number
    rf: number
    ra: number
}

export interface Starter {
    id: number
    name: string
    era?: number | null
}

export interface NextGame {
    date: string
    time: string
    opponent: string
    home: boolean
    game: number | null
    round: string
    series: string
    own_starter: Starter | null
    opp_starter: Starter | null
}

export interface MlbTeamRow {
    team: string
    id: number | null
    california: boolean
    round: string
    record: { wins: number; losses: number; pct: number; rank: number; run_diff_per_game: number }
    form: Record<string, FormWindow>
    september: { wins: number; losses: number }
    quality: {
        vs_above_500: [number, number]
        vs_top_12: [number, number]
        vs_bottom_10: [number, number]
        avg_opponent_pct: number | null
    }
    swing: { window: number; best: [number, number]; worst: [number, number] } | null
    season: Record<StatKey, RankedStat>
    sept: Record<StatKey, RankedStat>
    next_game: NextGame | null
}

export interface MlbTeamsResponse {
    as_of: number
    league_size: number
    teams: MlbTeamRow[]
}

export function useMlbTeams(enabled = true) {
    return useQuery<MlbTeamsResponse>({
        queryKey: ['mlb', 'teams'],
        queryFn: async () => {
            const response = await fetch('/api/mlb/teams')
            if (!response.ok) throw new Error('Failed to load the team table')
            return response.json()
        },
        enabled,
        staleTime: 5 * 60 * 1000,
        refetchInterval: enabled ? 30 * 60 * 1000 : false,
    })
}

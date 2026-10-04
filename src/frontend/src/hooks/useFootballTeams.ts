import { useQuery } from '@tanstack/react-query'

export interface RankedValue {
    value: number
    rank: number | null
}

export type FootballLeague = 'cfb' | 'nfl'

export interface FootballTeamRow {
    team: string
    id: string
    conference: string
    ap_rank: number | null
    record: { wins: number; losses: number; pct: number; rank: number }
    diff: RankedValue | null
    form: { last_3: [number, number]; last_5: [number, number] }
    splits: { home: [number, number]; road: [number, number]; neutral: [number, number] }
    quality: {
        vs_ranked: [number, number]
        vs_winning: [number, number]
        avg_opp_pct: number | null
        outside_league: [number, number]
        known_games: number
    }
    offense: Record<'ppg' | 'yds' | 'pass_yds' | 'rush_yds' | 'third_pct', RankedValue | null>
    defense: Record<'papg' | 'sacks' | 'takeaways' | 'giveaways' | 'turnover_margin', RankedValue | null>
    next_game: { date: string; opponent: string; home: boolean | null; opp_rank: number | null } | null
}

export interface FootballTable {
    league: FootballLeague
    as_of: number
    league_size: number
    groups: string[]
    teams: FootballTeamRow[]
}

export function useFootballTeams(league: FootballLeague, enabled = true) {
    return useQuery<FootballTable>({
        queryKey: ['football', league, 'teams'],
        queryFn: async () => {
            const response = await fetch(`/api/football/${league}/teams`)
            if (!response.ok) throw new Error('Failed to load the team table')
            return response.json()
        },
        enabled,
        staleTime: 5 * 60 * 1000,
        refetchInterval: enabled ? 30 * 60 * 1000 : false,
    })
}

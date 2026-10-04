import { useQuery } from '@tanstack/react-query'

export interface LiveGame {
    away: string
    home: string
    away_score: number
    home_score: number
    state: 'pre' | 'in' | 'post'
    detail: string
}

/** The live score for a game market, matched by the teams in its title. Pass null to skip the lookup. */
export function useLiveScore(title: string | null) {
    return useQuery<LiveGame | null>({
        queryKey: ['live-score', title],
        queryFn: async () => {
            const response = await fetch(`/api/scores/match?title=${encodeURIComponent(title ?? '')}`)
            if (!response.ok) return null
            return (await response.json()).game
        },
        enabled: !!title,
        refetchInterval: 30000,
        staleTime: 15000,
    })
}

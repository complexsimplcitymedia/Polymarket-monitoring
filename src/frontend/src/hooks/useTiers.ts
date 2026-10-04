import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

export type TierLeague = 'mlb' | 'cfb' | 'nfl'

export interface TierEntry {
    tier: number | null
    note: string | null
}

export function useTiers(league: TierLeague, enabled = true) {
    return useQuery<Record<string, TierEntry>>({
        queryKey: ['tiers', league],
        queryFn: async () => {
            const response = await fetch(`/api/tiers/${league}`)
            if (!response.ok) throw new Error('Failed to load tiers')
            return (await response.json()).tiers
        },
        enabled,
        staleTime: 60 * 1000,
    })
}

export function useSetTier(league: TierLeague) {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async ({ teamId, tier }: { teamId: string; tier: number | null }) => {
            const response = await fetch(`/api/tiers/${league}/${teamId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier }),
            })
            if (!response.ok) throw new Error('Could not save the tier')
            return response.json()
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tiers', league] }),
    })
}

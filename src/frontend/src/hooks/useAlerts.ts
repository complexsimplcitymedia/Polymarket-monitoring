import { useQuery } from '@tanstack/react-query'

export interface AlertRow {
    id: number
    kind: 'underpriced_leader' | 'first_score_upset'
    created_at: string
    priority: 'normal' | 'high'
    sport: string
    team: string
    title: string
    espn_win_prob: number
    market_price: number
    gap: number
    margin: number
    detail: string | null
    delivery: string
    status: 'active' | 'retracted' | 'expired'
    retract_note: string | null
    now: {
        away: string
        home: string
        away_score: number
        home_score: number
        detail: string
        state: 'pre' | 'in' | 'post'
        margin: number
        still_leading: boolean
    } | null
}

export interface AlertsFeed {
    email_configured: boolean
    enabled: boolean
    max_price: number
    min_lead: number
    cooldown_minutes: number
    alerts: AlertRow[]
}

export function useAlerts() {
    return useQuery<AlertsFeed>({
        queryKey: ['alerts'],
        queryFn: async () => {
            const response = await fetch('/api/alerts?limit=30')
            if (!response.ok) throw new Error('Failed to load alerts')
            return response.json()
        },
        refetchInterval: 30000,
        staleTime: 15000,
    })
}

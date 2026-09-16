import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

export interface WeatherOpportunity {
    market_id: string
    title: string
    city: string
    forecast_high_f: number
    bracket: string
    true_probability: number
    market_price: number
    edge: number
    expected_value_pct: number
    kelly_fraction_pct: number
    recommendation: string
    target_token_id: string | null
    target_side: string
    target_limit_price: number
    clob_token_ids: string[]
}

export interface ParlayLeg {
    market_id: string
    title: string
    outcome: string
    price: number
    token_id: string | null
    side: string
}

export interface ParlayOpportunity {
    id: string
    category: string
    title: string
    legs: ParlayLeg[]
    combined_implied_prob: number
    payout_multiplier: string
    edge_thesis: string
    recommended_budget_usdc: number
    estimated_payout_usdc: number
}

export interface ParlayAnalysisResult {
    parlay_id?: string
    analysis: string
    verdict?: string
    confidence?: number
    model?: string
}

export interface StoredOpportunity {
    id: number
    category: string
    title: string
    market_id?: string
    market_slug?: string
    true_probability?: number
    market_price?: number
    edge?: number
    expected_value_pct?: number
    target_token_id?: string
    target_side?: string
    target_limit_price?: number
    kelly_fraction_pct?: number
    status: string
    confidence_score?: number
    details_json?: string
    created_at: string
}

export function useWeatherOpportunities() {
    return useQuery<WeatherOpportunity[]>({
        queryKey: ['scanners', 'weather'],
        queryFn: async () => {
            const res = await axios.get<WeatherOpportunity[]>('/api/scanners/weather')
            return res.data
        },
        staleTime: 1000 * 30, // 30 seconds
        refetchInterval: 1000 * 30,
    })
}

export function useParlayOpportunities() {
    return useQuery<ParlayOpportunity[]>({
        queryKey: ['scanners', 'parlays'],
        queryFn: async () => {
            const res = await axios.get<ParlayOpportunity[]>('/api/scanners/parlays')
            return res.data
        },
        staleTime: 1000 * 60, // 1 minute
        refetchInterval: 1000 * 60,
    })
}

export function useOpportunities() {
    return useQuery<StoredOpportunity[]>({
        queryKey: ['scanners', 'opportunities'],
        queryFn: async () => {
            const res = await axios.get<StoredOpportunity[]>('/api/scanners/opportunities?limit=30')
            return res.data
        },
        staleTime: 1000 * 15,
        refetchInterval: 1000 * 15,
    })
}

export function useTriggerScan() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async () => {
            const res = await axios.post('/api/scanners/run')
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['scanners'] })
        },
    })
}

export function useAnalyzeParlay() {
    return useMutation<ParlayAnalysisResult, Error, {
        parlay_id?: string
        category?: string
        title?: string
        legs: ParlayLeg[]
        combined_implied_prob?: number
        payout_multiplier?: string
    }>({
        mutationFn: async (payload) => {
            const res = await axios.post<ParlayAnalysisResult>('/api/scanners/parlays/analyze', payload)
            return res.data
        },
    })
}

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

export interface TrackedCity {
    key: string
    name: string
    station: string
    lat: number
    lon: number
    tz: string
}

export interface HourlyWeatherPoint {
    time: string
    temp_f: number | null
    cloud_cover_pct: number
    condition: string
    solar_radiation_w_m2: number
    wind_mph: number
    precip_prob_pct: number
}

export interface TwoDegreeBracket {
    bracket: string
    low: number
    high: number
    probability: number
    rank: number
}

export interface CityWeatherMatrix {
    city: TrackedCity
    target_date: string
    consensus_peak_f: number
    calibrated_std_f: number
    ten_year_climatology: {
        mean_high_f: number
        std_dev_f: number
        min_high_f: number
        max_high_f: number
        anomaly_z_score: number
        anomaly_regime: string
        historical_records: Array<{ year: number; date: string; high: number }>
    }
    cloud_and_overcast_matrix: {
        mean_daylight_cloud_cover_pct: number
        morning_cloud_cover_pct: number
        afternoon_cloud_cover_pct: number
        overcast_regime: string
        insolation_impact: string
        hourly_curve: HourlyWeatherPoint[]
    }
    multi_model_nwp: {
        models: Record<string, number>
        consensus_mean_f: number
        model_spread_f: number
        model_std_f: number
    }
    live_observation: {
        station_id: string
        temp_f: number | null
        dew_f: number | null
        humidity_pct: number | null
        wind_mph: number | null
        wind_dir: number | null
        weather_text: string | null
        nws_forecast_high: number | null
        nws_forecast_discussion: string | null
    }
    polymarket_bracket_matrix: {
        brackets: TwoDegreeBracket[]
        primary_bracket: TwoDegreeBracket | null
        hedge_bracket: TwoDegreeBracket | null
        dutched_win_prob_pct: number
        recommended_capital_split: string
        trap_to_fade: {
            bracket: string
            probability: number
            reason: string
        } | null
    }
}

export function useTrackedCities() {
    return useQuery<TrackedCity[]>({
        queryKey: ['scanners', 'weather', 'cities'],
        queryFn: async () => {
            const res = await axios.get<TrackedCity[]>('/api/scanners/weather/cities')
            return res.data
        },
        staleTime: 1000 * 60 * 30, // 30 mins
    })
}

export function useCityWeatherMatrix(city: string, targetDate?: string) {
    return useQuery<CityWeatherMatrix>({
        queryKey: ['scanners', 'weather', 'matrix', city, targetDate || 'today'],
        queryFn: async () => {
            const params = new URLSearchParams({ city })
            if (targetDate) params.append('target_date', targetDate)
            const res = await axios.get<CityWeatherMatrix>(`/api/scanners/weather/matrix?${params.toString()}`)
            return res.data
        },
        staleTime: 1000 * 60 * 5, // 5 mins
        refetchInterval: 1000 * 60 * 5,
        enabled: Boolean(city),
    })
}


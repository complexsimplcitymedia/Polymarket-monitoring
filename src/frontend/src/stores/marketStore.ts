import { create } from 'zustand'

export interface Market {
    id: string
    slug: string
    title: string
    description?: string | null
    volume_24h: number
    volume_7d: number
    liquidity: number
    yes_percentage: number
    outcomes?: { name: string; price: number }[]
    is_active: boolean
    end_date?: string | null
    image_url?: string | null
    clob_token_ids?: string[] | null
    category?: string | null
    last_updated?: string | null
}

export interface LatencyEndpoints {
    trade: string
    data: string
    gamma: string
    espnCfb: string
    espnNfl: string
    mlbStats: string
    theScore: string
    ncaa: string
    clobWs: string
}

export const DEFAULT_LATENCY_ENDPOINTS: LatencyEndpoints = {
    trade: 'https://clob.polymarket.com',
    data: 'https://data-api.polymarket.com',
    gamma: 'https://gamma-api.polymarket.com',
    espnCfb: 'https://site.api.espn.com/apis/site/v2/sports/football/college-football',
    espnNfl: 'https://site.api.espn.com/apis/site/v2/sports/football/nfl',
    mlbStats: 'https://statsapi.mlb.com/api/v1',
    theScore: 'https://api.thescore.com',
    ncaa: 'https://sdataprod.ncaa.com',
    clobWs: 'wss://ws-subscriptions-clob.polymarket.com',
}

export type Timeframe = '24H' | '7D' | '1M' | 'ALL'
export type ShareType = 'Yes' | 'No'

export interface MarketStore {
    selectedMarket: Market | null
    selectedTimeframe: Timeframe
    selectedShareType: ShareType
    searchQuery: string
    streamUrl: string | null
    latencyEndpoints: LatencyEndpoints
    setSelectedMarket: (market: Market | null) => void
    setSelectedTimeframe: (timeframe: Timeframe) => void
    setSelectedShareType: (shareType: ShareType) => void
    setSearchQuery: (query: string) => void
    setStreamUrl: (url: string | null) => void
    setLatencyEndpoints: (endpoints: Partial<LatencyEndpoints>) => void
    resetLatencyEndpoints: () => void
}

const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('wolf-latency-endpoints') : null
const initialEndpoints: LatencyEndpoints = stored ? { ...DEFAULT_LATENCY_ENDPOINTS, ...JSON.parse(stored) } : DEFAULT_LATENCY_ENDPOINTS

export const useMarketStore = create<MarketStore>((set) => ({
    selectedMarket: null,
    selectedTimeframe: '24H',
    selectedShareType: 'Yes',
    searchQuery: '',
    streamUrl: null,
    latencyEndpoints: initialEndpoints,
    setSelectedMarket: (market) => set({ selectedMarket: market }),
    setSelectedTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),
    setSelectedShareType: (shareType) => set({ selectedShareType: shareType }),
    setSearchQuery: (query) => set({ searchQuery: query }),
    setStreamUrl: (url) => set({ streamUrl: url }),
    setLatencyEndpoints: (endpoints) => set((state) => {
        const next = { ...state.latencyEndpoints, ...endpoints }
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('wolf-latency-endpoints', JSON.stringify(next))
        }
        return { latencyEndpoints: next }
    }),
    resetLatencyEndpoints: () => {
        if (typeof localStorage !== 'undefined') {
            localStorage.removeItem('wolf-latency-endpoints')
        }
        return { latencyEndpoints: DEFAULT_LATENCY_ENDPOINTS }
    },
}))

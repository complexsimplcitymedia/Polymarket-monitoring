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

export type Timeframe = '24H' | '7D' | '1M' | 'ALL'
export type ShareType = 'Yes' | 'No'

interface MarketStore {
    selectedMarket: Market | null
    selectedTimeframe: Timeframe
    selectedShareType: ShareType
    searchQuery: string
    streamUrl: string | null
    setSelectedMarket: (market: Market | null) => void
    setSelectedTimeframe: (timeframe: Timeframe) => void
    setSelectedShareType: (shareType: ShareType) => void
    setSearchQuery: (query: string) => void
    setStreamUrl: (url: string | null) => void
}

export const useMarketStore = create<MarketStore>((set) => ({
    selectedMarket: null,
    selectedTimeframe: '24H',
    selectedShareType: 'Yes',
    searchQuery: '',
    streamUrl: null,
    setSelectedMarket: (market) => set({ selectedMarket: market }),
    setSelectedTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),
    setSelectedShareType: (shareType) => set({ selectedShareType: shareType }),
    setSearchQuery: (query) => set({ searchQuery: query }),
    setStreamUrl: (url) => set({ streamUrl: url }),
}))

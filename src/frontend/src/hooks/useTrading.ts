import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

export interface TradingStatus {
    status: 'READY' | 'UNCONFIGURED' | 'ERROR'
    message: string
    wallet_address: string | null
    funder_address?: string | null
    signature_type?: number
    balance_usdc: number
    allowance_usdc: number
    can_trade: boolean
}

export interface OrderBookSummary {
    token_id: string
    bids: Array<{ price: string; size: string }>
    asks: Array<{ price: string; size: string }>
    best_bid: number
    best_ask: number
    spread: number
    midpoint: number
}

export interface OpenOrder {
    id: string
    market: string
    asset_id: string
    side: 'BUY' | 'SELL'
    price: number
    original_size: number
    size_matched: number
    status: string
    created_at?: number
}

export interface PlaceOrderRequest {
    token_id: string
    price: number
    size: number
    side?: string
    order_type?: string
    dry_run?: boolean
}

export interface ExecuteOpportunityRequest {
    opportunity_id: number
    budget_usdc: number
    dry_run: boolean
}

export interface ParlayOrderRequest {
    legs: Array<{
        token_id: string
        price: number
        side?: string
        market_title?: string
    }>
    total_budget: number
    dry_run?: boolean
}

export function useTradingStatus() {
    return useQuery<TradingStatus>({
        queryKey: ['trading', 'status'],
        queryFn: async () => {
            const res = await axios.get<TradingStatus>('/api/trading/status')
            return res.data
        },
        staleTime: 1000 * 10,
        refetchInterval: 1000 * 10,
    })
}

export function useOrderBook(tokenId: string | null) {
    return useQuery<OrderBookSummary>({
        queryKey: ['trading', 'orderbook', tokenId],
        queryFn: async () => {
            const res = await axios.get<OrderBookSummary>(`/api/trading/orderbook/${tokenId}`)
            return res.data
        },
        enabled: !!tokenId,
        staleTime: 1000 * 5,
        refetchInterval: 1000 * 5,
    })
}

export function useOpenOrders(marketId?: string) {
    return useQuery<OpenOrder[]>({
        queryKey: ['trading', 'orders', marketId],
        queryFn: async () => {
            const url = marketId ? `/api/trading/orders?market_id=${marketId}` : '/api/trading/orders'
            const res = await axios.get<OpenOrder[]>(url)
            return res.data
        },
        staleTime: 1000 * 10,
        refetchInterval: 1000 * 10,
    })
}

export function usePlaceOrder() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (payload: PlaceOrderRequest) => {
            const res = await axios.post('/api/trading/order', payload)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading'] })
        },
    })
}

export function useExecuteOpportunity() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async ({ opportunity_id, budget_usdc, dry_run }: ExecuteOpportunityRequest) => {
            const res = await axios.post(
                `/api/trading/execute-opportunity/${opportunity_id}?budget_usdc=${budget_usdc}&dry_run=${dry_run}`
            )
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading'] })
            queryClient.invalidateQueries({ queryKey: ['scanners'] })
        },
    })
}

export function usePlaceParlay() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (payload: ParlayOrderRequest) => {
            const res = await axios.post('/api/trading/parlay', payload)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading'] })
        },
    })
}

export function useCancelOrder() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (orderId: string) => {
            const res = await axios.delete(`/api/trading/order/${orderId}`)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading'] })
        },
    })
}

export function useCancelAllOrders() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async () => {
            const res = await axios.delete('/api/trading/orders')
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading'] })
        },
    })
}

export interface AutoTradeConfig {
    enabled: boolean
    max_bet_usdc: number
    min_ev_pct: number
    dry_run: boolean
}

export function useAutoTradeStatus() {
    return useQuery<AutoTradeConfig>({
        queryKey: ['trading', 'autotrade'],
        queryFn: async () => {
            const res = await axios.get<AutoTradeConfig>('/api/trading/autotrade')
            return res.data
        },
        staleTime: 1000 * 5,
        refetchInterval: 1000 * 5,
    })
}

export function useToggleAutoTrade() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (params: {
            enabled?: boolean
            dry_run?: boolean
            max_bet?: number
            min_ev?: number
        }) => {
            const res = await axios.post('/api/trading/autotrade/toggle', null, { params })
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['trading', 'autotrade'] })
        },
    })
}

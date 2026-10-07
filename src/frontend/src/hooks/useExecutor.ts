import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const EXECUTOR_BASE = '/trade'

export interface TradingStatus {
    status: 'READY' | 'UNCONFIGURED' | 'ERROR'
    mode: string
    wallet_address: string | null
    error?: string
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
    tick_size?: string
    neg_risk?: boolean
}

export interface PlaceOrderResponse {
    success: boolean
    latency_ms: number
    response?: unknown
    error?: string
    dry_run?: boolean
}

export interface ParlayOrderRequest {
    legs: Array<{
        token_id: string
        price: number
        side?: string
        tick_size?: string
        neg_risk?: boolean
    }>
    total_budget: number
    dry_run?: boolean
}

export function useExecutorStatus() {
    return useQuery<TradingStatus>({
        queryKey: ['executor', 'status'],
        queryFn: async () => {
            const res = await axios.get<TradingStatus>(`${EXECUTOR_BASE}/status`)
            return res.data
        },
        staleTime: 1000 * 10,
        refetchInterval: 1000 * 10,
    })
}

export function useExecutorOrderBook(tokenId: string | null) {
    return useQuery<OrderBookSummary>({
        queryKey: ['executor', 'orderbook', tokenId],
        queryFn: async () => {
            const res = await axios.get<OrderBookSummary>(`${EXECUTOR_BASE}/orderbook/${tokenId}`)
            return res.data
        },
        enabled: !!tokenId,
        staleTime: 1000 * 5,
        refetchInterval: 1000 * 5,
    })
}

export function useExecutorOpenOrders(marketId?: string) {
    return useQuery<OpenOrder[]>({
        queryKey: ['executor', 'orders', marketId],
        queryFn: async () => {
            const url = marketId ? `${EXECUTOR_BASE}/orders?market_id=${marketId}` : `${EXECUTOR_BASE}/orders`
            const res = await axios.get<OpenOrder[]>(url)
            return res.data
        },
        staleTime: 1000 * 10,
        refetchInterval: 1000 * 10,
    })
}

export function useExecutorPlaceOrder() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (payload: PlaceOrderRequest) => {
            const res = await axios.post<PlaceOrderResponse>(`${EXECUTOR_BASE}/order`, payload)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['executor'] })
        },
    })
}

export function useExecutorPlaceParlay() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (payload: ParlayOrderRequest) => {
            const res = await axios.post<{ success: boolean; latency_ms: number; legs: PlaceOrderResponse[]; error?: string }>(`${EXECUTOR_BASE}/parlay`, payload)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['executor'] })
        },
    })
}

export function useExecutorCancelOrder() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (orderId: string) => {
            const res = await axios.delete(`${EXECUTOR_BASE}/order/${orderId}`)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['executor', 'orders'] })
        },
    })
}

export function useExecutorCancelAllOrders() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async () => {
            const res = await axios.delete(`${EXECUTOR_BASE}/orders`)
            return res.data
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['executor', 'orders'] })
        },
    })
}

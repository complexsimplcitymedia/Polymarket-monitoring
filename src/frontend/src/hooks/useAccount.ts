import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

export interface AccountBalance {
    current: number
    buying_power: number
    cash: number
    bonus: number
    bonus_hold: number
    available_to_withdraw: number
    model_withdrawable: number
    pending_withdrawals: unknown[]
}

export interface LiveInfo {
    away: string
    home: string
    away_score: number
    home_score: number
    state: 'pre' | 'in' | 'post'
    detail: string
    pick?: string
    margin?: number
    status?: 'leading' | 'trailing' | 'tied'
    kind?: 'over' | 'under'
    total?: number
    line?: number | null
    needs?: number | null
}

export interface OpenPositionLeg {
    title: string
    outcome: string
    state: string
    live?: LiveInfo | null
}

export interface AccountOpenPosition {
    slug: string
    title: string
    outcome: string
    contracts: number
    avg_price: number
    cost: number
    value: number
    legs: OpenPositionLeg[]
}

export interface CashFlows {
    deposits: number
    withdrawals: number
    bonuses: number
    deposit_match_bonuses: number
    referral_bonuses: number
    balance: number
    open_positions_value: number
    net_cash_out: number
    total_gain: number
    profit_excluding_bonuses: number
}

export interface CycleGroup {
    n: number
    wins: number
    losses: number
    win_rate: number | null
    avg_win: number | null
    avg_loss: number | null
    best: number | null
    worst: number | null
    net: number
    entered: number
    return_on_entered: number | null
}

export interface TradingSummary {
    all: CycleGroup
    sold: CycleGroup
    settled: CycleGroup
    by_kind: Record<string, CycleGroup>
    by_league: Record<string, CycleGroup>
    by_legs: Record<string, CycleGroup>
    open: number
    hold_minutes_sold: { median: number | null; p25: number | null; p75: number | null }
    total_fills: number
    fees_paid: number
}

export interface AccountSummary {
    balance: AccountBalance
    open_positions: { count: number; cost: number; value: number; items: AccountOpenPosition[] }
    cash_flows: CashFlows
    trading: TradingSummary
    fetched_at: number
}

async function fetchAccount(refresh: boolean): Promise<AccountSummary> {
    const response = await fetch(`/api/account/summary${refresh ? '?refresh=true' : ''}`)
    if (!response.ok) {
        let detail = 'Failed to load the account'
        try {
            const body = await response.json()
            if (body?.detail) detail = String(body.detail)
        } catch {
            // keep the generic message
        }
        throw new Error(detail)
    }
    return response.json()
}

export function useAccount() {
    return useQuery<AccountSummary>({
        queryKey: ['account', 'summary'],
        queryFn: () => fetchAccount(false),
        refetchInterval: 30000,
        staleTime: 15000,
    })
}

export { fetchAccount }

export interface Bet {
    opened_at: string
    ended_at: string | null
    league: string
    kind: string
    title: string
    backed: string
    legs: number
    direction: string
    contracts: number
    price_paid: number
    stake: number
    multiplier: number | null
    own_cash: number
    real_cash: number
    bonus_credit: number
    fees: number
    how_ended: 'sold' | 'settled' | 'open'
    exit_price: number | null
    pnl: number | null
    return: number | null
    hold_minutes: number | null
    slug: string
    bet_key: string
    tag: 'analysis' | 'vibe' | 'hedge'
    note: string | null
    why_ended: 'bounce' | 'target' | 'cut' | 'held' | null
}

export interface TagSummary {
    bets: number
    stake: number
    pnl: number
    decided: number
    win_rate: number | null
    avg_price_paid: number
}

export interface BetsView {
    count: number
    bets: Bet[]
    by_tag: Record<string, TagSummary>
    fetched_at: number
}

export function useBets() {
    return useQuery<BetsView>({
        queryKey: ['account', 'bets'],
        queryFn: async () => {
            const response = await fetch('/api/account/bets')
            if (!response.ok) throw new Error('Failed to load your bets')
            return response.json()
        },
        refetchInterval: 60000,
        staleTime: 30000,
    })
}

export interface BetNoteUpdate {
    bet_key: string
    tag?: 'analysis' | 'vibe' | 'hedge'
    note?: string
    why_ended?: 'bounce' | 'target' | 'cut' | 'held'
    clear_why?: boolean
}

export function useSetBetNote() {
    const queryClient = useQueryClient()
    return useMutation({
        mutationFn: async (update: BetNoteUpdate) => {
            const response = await fetch('/api/account/bets/note', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(update),
            })
            if (!response.ok) throw new Error('Could not save')
            return response.json()
        },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['account', 'bets'] }),
    })
}

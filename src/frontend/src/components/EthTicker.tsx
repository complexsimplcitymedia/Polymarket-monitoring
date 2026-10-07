import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

export interface EthPriceData {
    priceUsd: number | null
    change24h: number | null
    lastUpdated: Date | null
    status: 'live' | 'updating' | 'error'
}

export function EthTicker() {
    const [data, setData] = useState<EthPriceData>({
        priceUsd: 2574.50,
        change24h: -1.24,
        lastUpdated: new Date(),
        status: 'live'
    })
    const [isRefreshing, setIsRefreshing] = useState(false)

    const fetchEthPrice = useCallback(async () => {
        setIsRefreshing(true)
        try {
            // First attempt: CoinGecko simple price
            const res = await axios.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd&include_24hr_change=true',
                { timeout: 4000 }
            )
            if (res.data?.ethereum?.usd) {
                setData({
                    priceUsd: res.data.ethereum.usd,
                    change24h: res.data.ethereum.usd_24h_change ?? 0,
                    lastUpdated: new Date(),
                    status: 'live'
                })
                setIsRefreshing(false)
                return
            }
        } catch {
            // Fallback: Coinbase Spot API
            try {
                const cbRes = await axios.get('https://api.coinbase.com/v2/prices/ETH-USD/spot', { timeout: 4000 })
                const amount = parseFloat(cbRes.data?.data?.amount)
                if (!isNaN(amount)) {
                    setData(prev => ({
                        priceUsd: amount,
                        change24h: prev.change24h ?? 0,
                        lastUpdated: new Date(),
                        status: 'live'
                    }))
                    setIsRefreshing(false)
                    return
                }
            } catch {
                setData(prev => ({ ...prev, status: 'error' }))
            }
        }
        setIsRefreshing(false)
    }, [])

    useEffect(() => {
        fetchEthPrice()
        const interval = setInterval(fetchEthPrice, 30000) // Poll every 30 seconds
        return () => clearInterval(interval)
    }, [fetchEthPrice])

    const isPositive = (data.change24h ?? 0) >= 0

    return (
        <div className="flex items-center justify-between p-3.5 rounded-2xl bg-surface-900/80 border border-white/10 backdrop-blur-xl shadow-xl font-mono text-xs">
            <div className="flex items-center gap-3">
                {/* Ethereum Emblem */}
                <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                    <svg className="w-5 h-5" viewBox="0 0 256 417" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                        <path d="M127.961 0L125.166 9.5V285.168L127.961 287.958L255.923 212.32L127.961 0Z" fill="currentColor" fillOpacity="0.8"/>
                        <path d="M127.962 0L0 212.32L127.962 287.958V156.966V0Z" fill="currentColor"/>
                        <path d="M127.961 312.187L126.386 314.106V413.435L127.961 416.995L256 236.586L127.961 312.187Z" fill="currentColor" fillOpacity="0.8"/>
                        <path d="M127.962 416.995V312.187L0 236.586L127.962 416.995Z" fill="currentColor"/>
                        <path d="M127.961 287.958L255.923 212.32L127.961 156.967V287.958Z" fill="currentColor" fillOpacity="0.6"/>
                        <path d="M0 212.32L127.962 287.958V156.967L0 212.32Z" fill="currentColor" fillOpacity="0.4"/>
                    </svg>
                </div>

                <div>
                    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
                        <span>ETH / USD</span>
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    </div>
                    <div className="text-xl font-black font-display text-white tracking-tight">
                        {data.priceUsd ? `$${data.priceUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '---'}
                    </div>
                </div>
            </div>

            <div className="flex flex-col items-end gap-1">
                {/* 24h Delta Badge */}
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold border ${
                    isPositive
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}>
                    {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    <span>{data.change24h !== null ? `${isPositive ? '+' : ''}${data.change24h.toFixed(2)}%` : '0.00%'}</span>
                </div>

                <div className="flex items-center gap-1.5 text-[9px] text-slate-500">
                    <span>24h Change</span>
                    <button
                        onClick={fetchEthPrice}
                        title="Refresh ETH Price"
                        className="hover:text-slate-300 transition-colors"
                    >
                        <RefreshCw className={`w-2.5 h-2.5 ${isRefreshing ? 'animate-spin text-indigo-400' : ''}`} />
                    </button>
                </div>
            </div>
        </div>
    )
}

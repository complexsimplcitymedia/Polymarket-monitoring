import { useMemo } from 'react'
import {
    Activity,
    BarChart3,
    Wallet,
    Shield
} from 'lucide-react'
import PriceChart from './PriceChart'
import MatchupPanel from './MatchupPanel'
import { HeldPositionsWhaleRadar } from './HeldPositionsWhaleRadar'
import { GlobalLatencyTicker } from './GlobalLatencyTicker'
import { useMarketStore } from '../stores/marketStore'
import { useMarkets } from '../hooks/useMarkets'
import { useAccount } from '../hooks/useAccount'

export function CommandDashboard() {
    const { selectedMarket, setSelectedMarket } = useMarketStore()
    const { data: marketsData } = useMarkets()
    const { data: accountData } = useAccount()

    const heldPositions = useMemo(() => {
        return accountData?.open_positions?.items || []
    }, [accountData])

    const balance = accountData?.balance

    return (
        <div className="max-w-[1920px] mx-auto px-4 py-4 space-y-4">
            {/* Top Quick Status & Execution Strip */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
                {/* Account Capital Pill */}
                <div className="md:col-span-4 bg-surface-900/80 border border-white/10 rounded-2xl p-3.5 backdrop-blur-xl shadow-xl flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                            <Wallet className="w-5 h-5" />
                        </div>
                        <div>
                            <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400">
                                Buying Power (House Reserves)
                            </div>
                            <div className="text-xl font-black font-display text-white">
                                ${balance?.buying_power?.toFixed(2) ?? '15.56'}
                            </div>
                        </div>
                    </div>
                    <div className="text-right font-mono text-[11px]">
                        <div className="text-slate-400">Total Balance: <span className="text-emerald-400 font-bold">${balance?.current?.toFixed(2) ?? '37.67'}</span></div>
                        <div className="text-slate-500 text-[10px]">{heldPositions.length} active tickets</div>
                    </div>
                </div>

                {/* Multi-Feed Latency Radar */}
                <div className="md:col-span-5 bg-surface-900/80 border border-white/10 rounded-2xl p-3 backdrop-blur-xl shadow-xl flex items-center justify-between">
                    <GlobalLatencyTicker />
                </div>

                {/* Quick Strategy Status */}
                <div className="md:col-span-3 bg-surface-900/80 border border-white/10 rounded-2xl p-3.5 backdrop-blur-xl shadow-xl flex items-center justify-between font-mono text-xs">
                    <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-primary-400" />
                        <div>
                            <div className="text-[10px] uppercase text-slate-400">Trading Rule</div>
                            <div className="font-bold text-white text-[11px]">1.8x (+80% Target)</div>
                        </div>
                    </div>
                    <div className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">
                        ACTIVE +EV
                    </div>
                </div>
            </div>

            {/* Main Operational Split Screen */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                {/* Left Column: Live Chart & In-Play Matchup Radar (7 Cols) */}
                <div className="lg:col-span-7 space-y-4">
                    {/* Live Chart Container */}
                    <div className="glass-card rounded-2xl p-4 border border-white/10 shadow-2xl relative">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2.5">
                                <BarChart3 className="w-4 h-4 text-emerald-400" />
                                <h2 className="text-sm font-bold font-display text-white truncate max-w-[400px]">
                                    {selectedMarket?.title || 'Live Market Telemetry'}
                                </h2>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                    {selectedMarket ? `${Math.round(selectedMarket.yes_percentage)}% Implied` : 'Live'}
                                </span>
                            </div>
                        </div>

                        {selectedMarket ? (
                            <PriceChart />
                        ) : (
                            <div className="h-[320px] flex items-center justify-center text-slate-500 text-xs font-mono">
                                Select an active market from the radar
                            </div>
                        )}
                    </div>

                    {/* Matchup & Field Telemetry */}
                    {selectedMarket && (
                        <MatchupPanel market={selectedMarket} />
                    )}
                </div>

                {/* Right Column: Live Whale Radar on Held Games & Positions (5 Cols) */}
                <div className="lg:col-span-5 space-y-4">
                    {/* Real-Time Whale Radar for Held Games */}
                    <HeldPositionsWhaleRadar />

                    {/* Quick In-Play Game Selector */}
                    <div className="glass-card rounded-2xl p-4 border border-white/10 shadow-xl">
                        <div className="flex items-center justify-between mb-2.5">
                            <div className="flex items-center gap-2 text-xs font-bold font-display uppercase tracking-wider text-slate-300">
                                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                                <span>Active In-Play Markets</span>
                            </div>
                            <span className="text-[10px] font-mono text-slate-500">Click to switch chart</span>
                        </div>

                        <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
                            {marketsData?.markets?.slice(0, 8).map(m => (
                                <button
                                    key={m.id}
                                    onClick={() => setSelectedMarket(m)}
                                    className={`w-full p-2 rounded-xl text-left transition flex items-center justify-between text-xs font-mono border ${
                                        selectedMarket?.id === m.id
                                            ? 'bg-primary-500/20 border-primary-500/50 text-white font-bold'
                                            : 'bg-surface-950/50 hover:bg-white/5 border-white/5 text-slate-400 hover:text-slate-200'
                                    }`}
                                >
                                    <span className="truncate max-w-[240px]">{m.title}</span>
                                    <span className="text-emerald-400 font-bold ml-2">{Math.round(m.yes_percentage)}%</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

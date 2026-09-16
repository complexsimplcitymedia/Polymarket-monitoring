import { useState } from 'react'
import {
    CloudSun,
    Layers,
    Zap,
    Radar,
    ListOrdered,
    CheckCircle,
    Bot,
    RefreshCw,
    DollarSign,
    Flame,
    Cpu,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
    useWeatherOpportunities,
    useParlayOpportunities,
    useOpportunities,
    useTriggerScan,
    useAnalyzeParlay,
    type ParlayOpportunity,
} from '../hooks/useScanners'
import {
    useTradingStatus,
    useOpenOrders,
    usePlaceOrder,
    useExecuteOpportunity,
    usePlaceParlay,
    useCancelOrder,
    useCancelAllOrders,
    useOrderBook,
    useAutoTradeStatus,
    useToggleAutoTrade,
} from '../hooks/useTrading'
import { useMarkets } from '../hooks/useMarkets'

export function AlphaTerminal() {
    const [activeTab, setActiveTab] = useState<'weather' | 'parlays' | 'pipeline' | 'clob' | 'orders'>('weather')
    const [dryRun, setDryRun] = useState<boolean>(true)
    const [tradeBudget, setTradeBudget] = useState<number>(5.0)

    // Data Hooks
    const { data: tradingStatus, isLoading: statusLoading } = useTradingStatus()
    const { data: weatherData, isLoading: weatherLoading, refetch: refetchWeather } = useWeatherOpportunities()
    const { data: parlayData, isLoading: parlayLoading, refetch: refetchParlays } = useParlayOpportunities()
    const { data: pipelineData, isLoading: pipelineLoading, refetch: refetchPipeline } = useOpportunities()
    const { data: openOrders, isLoading: ordersLoading, refetch: refetchOrders } = useOpenOrders()
    const { data: marketsData } = useMarkets()

    // Mutations
    const triggerScan = useTriggerScan()
    const analyzeParlay = useAnalyzeParlay()
    const executeOp = useExecuteOpportunity()
    const placeParlay = usePlaceParlay()
    const placeOrder = usePlaceOrder()
    const cancelOrder = useCancelOrder()
    const cancelAllOrders = useCancelAllOrders()

    // Interactive state for Parlay analysis drawer
    const [analyzingParlayId, setAnalyzingParlayId] = useState<string | null>(null)
    const [parlayAnalysis, setParlayAnalysis] = useState<Record<string, { analysis: string; verdict?: string; model?: string }>>({})

    // Interactive state for Quick CLOB Trader
    const [clobMarketId, setClobMarketId] = useState<string>('')
    const [clobTokenId, setClobTokenId] = useState<string>('')
    const [clobPrice, setClobPrice] = useState<number>(0.50)
    const [clobSize, setClobSize] = useState<number>(10)
    const [clobSide, setClobSide] = useState<'BUY' | 'SELL'>('BUY')
    const [executionFeedback, setExecutionFeedback] = useState<string | null>(null)

    const { data: orderBook } = useOrderBook(clobTokenId || null)
    const { data: autoTradeConfig } = useAutoTradeStatus()
    const toggleAutoTrade = useToggleAutoTrade()

    const handleRunFullScan = async () => {
        try {
            await triggerScan.mutateAsync()
            refetchWeather()
            refetchParlays()
            refetchPipeline()
        } catch (e) {
            console.error('Scan error:', e)
        }
    }

    const handleAnalyzeParlayClick = async (parlay: ParlayOpportunity) => {
        setAnalyzingParlayId(parlay.id)
        try {
            const res = await analyzeParlay.mutateAsync({
                parlay_id: parlay.id,
                category: parlay.category,
                title: parlay.title,
                legs: parlay.legs,
                combined_implied_prob: parlay.combined_implied_prob,
                payout_multiplier: parlay.payout_multiplier,
            })
            setParlayAnalysis((prev) => ({
                ...prev,
                [parlay.id]: {
                    analysis: res.analysis,
                    verdict: res.verdict,
                    model: res.model,
                },
            }))
        } catch (e) {
            console.error('Parlay analysis error:', e)
        } finally {
            setAnalyzingParlayId(null)
        }
    }

    const handleExecuteOpportunityClick = async (opId: number, title: string) => {
        setExecutionFeedback(`Executing "${title}"...`)
        try {
            const res = await executeOp.mutateAsync({
                opportunity_id: opId,
                budget_usdc: tradeBudget,
                dry_run: dryRun,
            })
            setExecutionFeedback(`Success: ${res.execution?.status || 'FILLED'} - Order ID: ${res.execution?.order_id || 'simulated'}`)
            setTimeout(() => setExecutionFeedback(null), 6000)
        } catch (e: any) {
            setExecutionFeedback(`Error: ${e.response?.data?.detail || e.message}`)
            setTimeout(() => setExecutionFeedback(null), 8000)
        }
    }

    const handleExecuteParlayClick = async (parlay: ParlayOpportunity) => {
        setExecutionFeedback(`Submitting Parlay bundle "${parlay.title}"...`)
        try {
            const res = await placeParlay.mutateAsync({
                legs: parlay.legs.map((l) => ({
                    token_id: l.token_id || 'simulated_token',
                    price: l.price,
                    side: l.side,
                    market_title: l.title,
                })),
                total_budget: tradeBudget,
                dry_run: dryRun,
            })
            setExecutionFeedback(`Parlay Executed: ${res.status} (${res.successful_orders}/${res.total_legs} legs filled)`)
            setTimeout(() => setExecutionFeedback(null), 6000)
        } catch (e: any) {
            setExecutionFeedback(`Error: ${e.response?.data?.detail || e.message}`)
            setTimeout(() => setExecutionFeedback(null), 8000)
        }
    }

    const handleQuickOrderSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!clobTokenId) {
            setExecutionFeedback('Error: Token ID is required')
            return
        }
        setExecutionFeedback(`Submitting ${clobSide} limit order...`)
        try {
            const res = await placeOrder.mutateAsync({
                token_id: clobTokenId,
                price: clobPrice,
                size: clobSize,
                side: clobSide,
                dry_run: dryRun,
            })
            setExecutionFeedback(`Order Placed: ${res.status || 'OK'} - Order ID: ${res.order_id || 'simulated'}`)
            refetchOrders()
            setTimeout(() => setExecutionFeedback(null), 6000)
        } catch (e: any) {
            setExecutionFeedback(`Failed: ${e.response?.data?.detail || e.message}`)
            setTimeout(() => setExecutionFeedback(null), 8000)
        }
    }

    return (
        <div className="space-y-6">
            {/* Top Control Bar & Live Status */}
            <div className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-96 h-96 bg-primary-600/10 rounded-full blur-3xl pointer-events-none" />
                <div className="flex flex-col xl:flex-row items-start xl:items-center justify-between gap-6 relative z-10">
                    <div className="space-y-1">
                        <div className="flex items-center gap-3">
                            <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary-500 to-accent-600 text-white shadow-lg shadow-primary-900/30">
                                <Flame className="w-6 h-6 animate-pulse text-amber-300" />
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h2 className="text-2xl font-bold text-white tracking-tight">Alpha Execution Terminal</h2>
                                    <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                        Tailscale Node chi6 Active
                                    </span>
                                </div>
                                <p className="text-xs sm:text-sm text-surface-300">
                                    Autonomous prediction market alpha engine with NOAA probabilistic edge, AMD EPYC LLM verification, and direct CLOB execution.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Quick Stats & Toggles */}
                    <div className="flex flex-wrap items-center gap-3 w-full xl:w-auto justify-start xl:justify-end">
                        {/* Trading Mode Switcher */}
                        <div className="flex items-center bg-surface-900/80 border border-white/10 rounded-xl p-1 text-xs">
                            <button
                                onClick={() => setDryRun(true)}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                    dryRun
                                        ? 'bg-amber-500/30 text-amber-300 border border-amber-500/40 shadow-sm'
                                        : 'text-surface-400 hover:text-white'
                                }`}
                            >
                                Paper / Dry-Run
                            </button>
                            <button
                                onClick={() => setDryRun(false)}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                    !dryRun
                                        ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 shadow-sm'
                                        : 'text-surface-400 hover:text-white'
                                }`}
                            >
                                Live On-Chain
                            </button>
                        </div>

                        {/* Trade Size Control */}
                        <div className="flex items-center gap-2 bg-surface-900/80 border border-white/10 rounded-xl px-3 py-1.5 text-xs">
                            <DollarSign className="w-3.5 h-3.5 text-surface-400" />
                            <span className="text-surface-400 font-medium">Bet Size:</span>
                            <div className="flex items-center gap-1">
                                {[2, 5, 10, 25].map((val) => (
                                    <button
                                        key={val}
                                        onClick={() => setTradeBudget(val)}
                                        className={`px-2 py-0.5 rounded font-mono font-semibold transition-colors ${
                                            tradeBudget === val
                                                ? 'bg-primary-500 text-white'
                                                : 'text-surface-300 hover:text-white bg-surface-800'
                                        }`}
                                    >
                                        ${val}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Wallet Balance Widget */}
                        <div className="flex items-center gap-3 bg-surface-900/80 border border-white/10 rounded-xl px-4 py-1.5">
                            <div className="text-left">
                                <div className="text-[10px] uppercase tracking-wider text-surface-400 font-semibold">
                                    Collateral Balance
                                </div>
                                <div className="text-sm font-bold font-mono text-white flex items-center gap-1">
                                    {statusLoading ? (
                                        <span className="text-surface-500">Loading...</span>
                                    ) : (
                                        <>
                                            <span className="text-emerald-400">
                                                ${(tradingStatus?.balance_usdc ?? 0).toFixed(2)}
                                            </span>
                                            <span className="text-xs text-surface-400 font-normal">USDC</span>
                                        </>
                                    )}
                                </div>
                            </div>
                            <div
                                className={`w-2.5 h-2.5 rounded-full ${
                                    tradingStatus?.status === 'READY'
                                        ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                                        : 'bg-amber-400'
                                }`}
                                title={tradingStatus?.message || 'Status'}
                            />
                        </div>

                        {/* Trigger Scan Button */}
                        <button
                            onClick={handleRunFullScan}
                            disabled={triggerScan.isPending}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-600 hover:bg-primary-500 text-white font-semibold text-xs transition-all shadow-lg shadow-primary-900/30 disabled:opacity-50"
                        >
                            <RefreshCw className={`w-3.5 h-3.5 ${triggerScan.isPending ? 'animate-spin' : ''}`} />
                            {triggerScan.isPending ? 'Scanning...' : 'Scan Alpha Now'}
                        </button>
                    </div>
                </div>

                {/* Execution Feedback Notification Toast */}
                {executionFeedback && (
                    <div className="mt-4 p-3 rounded-xl bg-surface-900/90 border border-primary-500/40 text-xs font-mono text-white flex items-center justify-between animate-fadeIn">
                        <div className="flex items-center gap-2">
                            <CheckCircle className="w-4 h-4 text-primary-400" />
                            <span>{executionFeedback}</span>
                        </div>
                        <button
                            onClick={() => setExecutionFeedback(null)}
                            className="text-surface-400 hover:text-white"
                        >
                            &times;
                        </button>
                    </div>
                )}
            </div>

            {/* Autonomous Execution Daemon Bar */}
            <div className="glass-card rounded-2xl p-4 border border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-gradient-to-r from-surface-900/90 via-surface-900/60 to-surface-900/90">
                <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl border ${
                        autoTradeConfig?.enabled
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : 'bg-surface-800 text-surface-400 border-white/10'
                    }`}>
                        <Bot className={`w-5 h-5 ${autoTradeConfig?.enabled ? 'animate-bounce text-emerald-300' : ''}`} />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h4 className="font-bold text-white text-sm">Autonomous Execution Daemon</h4>
                            <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full uppercase tracking-wider ${
                                autoTradeConfig?.enabled
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                    : 'bg-surface-800 text-surface-400 border border-white/10'
                            }`}>
                                {autoTradeConfig?.enabled ? 'Active • Auto-Firing' : 'Standby / Manual'}
                            </span>
                            {autoTradeConfig?.enabled && (
                                <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-primary-500/20 text-primary-300">
                                    {autoTradeConfig.dry_run ? 'Simulation Mode' : 'Live On-Chain'}
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-surface-300">
                            Evaluates weather & parlay mathematical edges every 5 minutes. Auto-executes setups with EV &ge; {autoTradeConfig?.min_ev_pct ?? 25}% (capped at ${autoTradeConfig?.max_bet_usdc ?? 5}/trade).
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                    <button
                        onClick={() => toggleAutoTrade.mutate({ dry_run: !autoTradeConfig?.dry_run })}
                        disabled={toggleAutoTrade.isPending}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                            autoTradeConfig?.dry_run
                                ? 'bg-amber-500/20 text-amber-300 border-amber-500/30 hover:bg-amber-500/30'
                                : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/30'
                        }`}
                    >
                        {autoTradeConfig?.dry_run ? 'Dry-Run Mode' : 'Live Execution Mode'}
                    </button>

                    <button
                        onClick={() => toggleAutoTrade.mutate({ enabled: !autoTradeConfig?.enabled })}
                        disabled={toggleAutoTrade.isPending}
                        className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all shadow-md ${
                            autoTradeConfig?.enabled
                                ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/30'
                                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/30'
                        }`}
                    >
                        {autoTradeConfig?.enabled ? 'Pause Auto-Trader' : 'Activate Auto-Trader'}
                    </button>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-2 border-b border-white/10 pb-2 overflow-x-auto">
                <button
                    onClick={() => setActiveTab('weather')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
                        activeTab === 'weather'
                            ? 'bg-primary-500/30 text-white border border-primary-500/40 shadow-md'
                            : 'text-surface-400 hover:text-surface-200'
                    }`}
                >
                    <CloudSun className="w-4 h-4 text-cyan-400" />
                    <span>Weather Mispricings (+EV)</span>
                    {weatherData && weatherData.length > 0 && (
                        <span className="px-1.5 py-0.2 text-[10px] rounded-full bg-cyan-500/20 text-cyan-300">
                            {weatherData.length}
                        </span>
                    )}
                </button>

                <button
                    onClick={() => setActiveTab('parlays')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
                        activeTab === 'parlays'
                            ? 'bg-primary-500/30 text-white border border-primary-500/40 shadow-md'
                            : 'text-surface-400 hover:text-surface-200'
                    }`}
                >
                    <Layers className="w-4 h-4 text-purple-400" />
                    <span>Correlated Parlays & AI</span>
                    {parlayData && parlayData.length > 0 && (
                        <span className="px-1.5 py-0.2 text-[10px] rounded-full bg-purple-500/20 text-purple-300">
                            {parlayData.length}
                        </span>
                    )}
                </button>

                <button
                    onClick={() => setActiveTab('pipeline')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
                        activeTab === 'pipeline'
                            ? 'bg-primary-500/30 text-white border border-primary-500/40 shadow-md'
                            : 'text-surface-400 hover:text-surface-200'
                    }`}
                >
                    <Radar className="w-4 h-4 text-emerald-400" />
                    <span>Opportunity Pipeline</span>
                    {pipelineData && pipelineData.length > 0 && (
                        <span className="px-1.5 py-0.2 text-[10px] rounded-full bg-emerald-500/20 text-emerald-300">
                            {pipelineData.length}
                        </span>
                    )}
                </button>

                <button
                    onClick={() => setActiveTab('clob')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
                        activeTab === 'clob'
                            ? 'bg-primary-500/30 text-white border border-primary-500/40 shadow-md'
                            : 'text-surface-400 hover:text-surface-200'
                    }`}
                >
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span>Direct CLOB Fast-Trader</span>
                </button>

                <button
                    onClick={() => setActiveTab('orders')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm transition-all whitespace-nowrap ${
                        activeTab === 'orders'
                            ? 'bg-primary-500/30 text-white border border-primary-500/40 shadow-md'
                            : 'text-surface-400 hover:text-surface-200'
                    }`}
                >
                    <ListOrdered className="w-4 h-4 text-blue-400" />
                    <span>Open Orders</span>
                    {openOrders && openOrders.length > 0 && (
                        <span className="px-1.5 py-0.2 text-[10px] rounded-full bg-blue-500/20 text-blue-300 font-mono">
                            {openOrders.length}
                        </span>
                    )}
                </button>
            </div>

            {/* TAB CONTENT */}

            {/* 1. WEATHER SCANNER */}
            {activeTab === 'weather' && (
                <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/20 flex items-center justify-between">
                        <div className="text-xs text-cyan-200">
                            <strong>NOAA High-Resolution Ensemble Engine:</strong> Quantifies probability density curves over bracket bounds and detects statistical underpricings where market odds diverge from physical meteorological forecasts.
                        </div>
                        <div className="text-[11px] font-mono text-cyan-400 font-semibold uppercase">
                            Stations: NYC Central Park, Miami MIA, Chicago ORD, LAX
                        </div>
                    </div>

                    {weatherLoading ? (
                        <div className="p-12 text-center text-surface-400">Loading NOAA forecasts & CLOB prices...</div>
                    ) : !weatherData || weatherData.length === 0 ? (
                        <div className="p-12 text-center text-surface-400 glass-card rounded-2xl">
                            No weather anomalies detected above threshold right now.
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {weatherData.map((op, idx) => (
                                <div
                                    key={idx}
                                    className="glass-card rounded-2xl p-5 border border-white/10 hover:border-cyan-500/40 transition-all flex flex-col justify-between space-y-4 shadow-lg group"
                                >
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="px-2 py-0.5 text-xs font-bold rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                                {op.city}
                                            </span>
                                            <span className="text-xs font-mono text-surface-400">
                                                Peak: {op.forecast_high_f}°F
                                            </span>
                                        </div>

                                        <h3 className="font-semibold text-white text-sm line-clamp-2 mb-3">
                                            {op.title}
                                        </h3>

                                        <div className="p-3 rounded-xl bg-surface-900/70 border border-white/5 space-y-2 mb-4">
                                            <div className="flex justify-between items-center text-xs">
                                                <span className="text-surface-400">Target Bracket:</span>
                                                <span className="font-mono text-white font-semibold">{op.bracket}</span>
                                            </div>
                                            <div className="flex justify-between items-center text-xs">
                                                <span className="text-surface-400">NOAA Model Prob:</span>
                                                <span className="font-mono text-cyan-300 font-bold">{op.true_probability.toFixed(1)}%</span>
                                            </div>
                                            <div className="flex justify-between items-center text-xs">
                                                <span className="text-surface-400">Market Price:</span>
                                                <span className="font-mono text-surface-200">{op.market_price.toFixed(1)}¢</span>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-2 gap-2 text-center">
                                            <div className="p-2 rounded-xl bg-emerald-950/30 border border-emerald-500/30">
                                                <div className="text-[10px] uppercase tracking-wider text-emerald-400 font-semibold">
                                                    Calculated Edge
                                                </div>
                                                <div className="text-base font-bold font-mono text-emerald-300">
                                                    +{op.edge.toFixed(1)}%
                                                </div>
                                            </div>
                                            <div className="p-2 rounded-xl bg-primary-950/30 border border-primary-500/30">
                                                <div className="text-[10px] uppercase tracking-wider text-primary-400 font-semibold">
                                                    Expected Value
                                                </div>
                                                <div className="text-base font-bold font-mono text-primary-300">
                                                    +{op.expected_value_pct.toFixed(0)}% EV
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="pt-2 border-t border-white/5 flex items-center justify-between gap-3">
                                        <div className="text-[11px] text-surface-400 font-mono">
                                            Kelly: {op.kelly_fraction_pct}%
                                        </div>
                                        <button
                                            onClick={() => handleExecuteOpportunityClick(idx + 1000, op.title)}
                                            disabled={executeOp.isPending}
                                            className="flex-1 py-2 px-3 rounded-xl bg-gradient-to-r from-cyan-600 to-primary-600 hover:from-cyan-500 hover:to-primary-500 text-white font-semibold text-xs transition-all shadow-md flex items-center justify-center gap-1.5"
                                        >
                                            <Zap className="w-3.5 h-3.5 text-amber-300" />
                                            <span>Execute ${tradeBudget.toFixed(0)} Bet</span>
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* 2. CORRELATED PARLAYS */}
            {activeTab === 'parlays' && (
                <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-500/20 flex items-center justify-between">
                        <div className="text-xs text-purple-200">
                            <strong>Synthetic Parlay Combinations:</strong> Bundles mathematically correlated events to unlock synthetic asymmetric payout multipliers (4x - 8x). Verified with local AMD EPYC LLM reasoning to detect inverse or high-risk outcomes.
                        </div>
                    </div>

                    {parlayLoading ? (
                        <div className="p-12 text-center text-surface-400">Discovering multi-market parlay opportunities...</div>
                    ) : !parlayData || parlayData.length === 0 ? (
                        <div className="p-12 text-center text-surface-400 glass-card rounded-2xl">
                            No parlay bundles generated for active markets.
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {parlayData.map((parlay) => {
                                const analysis = parlayAnalysis[parlay.id]
                                const isAnalyzing = analyzingParlayId === parlay.id

                                return (
                                    <div
                                        key={parlay.id}
                                        className="glass-card rounded-2xl p-5 border border-white/10 hover:border-purple-500/40 transition-all space-y-4 shadow-xl flex flex-col justify-between"
                                    >
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                                    {parlay.category}
                                                </span>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-surface-400 font-mono">
                                                        Payout Multiplier:
                                                    </span>
                                                    <span className="px-2 py-0.5 text-xs font-bold font-mono rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                                        {parlay.payout_multiplier}
                                                    </span>
                                                </div>
                                            </div>

                                            <h3 className="font-semibold text-white text-base">
                                                {parlay.title}
                                            </h3>

                                            <p className="text-xs text-surface-300">
                                                {parlay.edge_thesis}
                                            </p>

                                            {/* Legs */}
                                            <div className="space-y-2 pt-2">
                                                <div className="text-[11px] font-semibold text-surface-400 uppercase tracking-wider">
                                                    Parlay Legs ({parlay.legs.length}):
                                                </div>
                                                {parlay.legs.map((leg, lIdx) => (
                                                    <div
                                                        key={lIdx}
                                                        className="p-2.5 rounded-xl bg-surface-900/60 border border-white/5 flex items-center justify-between text-xs"
                                                    >
                                                        <div className="flex-1 pr-3 truncate text-surface-200">
                                                            <span className="font-bold text-primary-400 mr-2">
                                                                Leg {lIdx + 1}:
                                                            </span>
                                                            {leg.title}
                                                        </div>
                                                        <div className="flex items-center gap-2 font-mono shrink-0">
                                                            <span className="px-1.5 py-0.5 rounded bg-surface-800 text-surface-300 text-[10px]">
                                                                {leg.outcome}
                                                            </span>
                                                            <span className="text-white font-semibold">
                                                                {(leg.price * 100).toFixed(0)}¢
                                                            </span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>

                                            {/* LLM Analysis Box */}
                                            {analysis && (
                                                <div className="mt-3 p-3.5 rounded-xl bg-surface-950/80 border border-purple-500/30 text-xs space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-1.5 text-purple-300 font-semibold">
                                                            <Cpu className="w-3.5 h-3.5" />
                                                            <span>Local AMD EPYC LLM ({analysis.model || 'qwen2.5:3b'})</span>
                                                        </div>
                                                        {analysis.verdict && (
                                                            <span
                                                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                                                    analysis.verdict.includes('GO')
                                                                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                                                        : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                                                }`}
                                                            >
                                                                {analysis.verdict}
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="prose prose-invert prose-xs max-h-48 overflow-y-auto pr-2 text-surface-300">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                            {analysis.analysis}
                                                        </ReactMarkdown>
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <div className="pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-2">
                                            <button
                                                onClick={() => handleAnalyzeParlayClick(parlay)}
                                                disabled={isAnalyzing}
                                                className="px-3 py-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-purple-300 font-semibold text-xs transition-all flex items-center gap-1.5 border border-purple-500/20 disabled:opacity-50"
                                            >
                                                <Bot className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
                                                <span>{isAnalyzing ? 'Analyzing on EPYC...' : 'Analyze with Qwen LLM'}</span>
                                            </button>

                                            <button
                                                onClick={() => handleExecuteParlayClick(parlay)}
                                                disabled={placeParlay.isPending}
                                                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-all shadow-md flex items-center gap-1.5 disabled:opacity-50"
                                            >
                                                <Zap className="w-3.5 h-3.5 text-amber-300" />
                                                <span>Place Parlay (${tradeBudget.toFixed(0)})</span>
                                            </button>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* 3. OPPORTUNITY PIPELINE STREAM */}
            {activeTab === 'pipeline' && (
                <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/20 flex items-center justify-between">
                        <div className="text-xs text-emerald-200">
                            <strong>Live Postgres Opportunity Feed:</strong> Populated asynchronously by the background opportunity daemon running every 5 minutes. Stores all mathematically verified setups exceeding +20% EV and 12% edge.
                        </div>
                    </div>

                    {pipelineLoading ? (
                        <div className="p-12 text-center text-surface-400">Loading saved pipeline opportunities...</div>
                    ) : !pipelineData || pipelineData.length === 0 ? (
                        <div className="p-12 text-center text-surface-400 glass-card rounded-2xl">
                            No pipeline opportunities stored yet. Click "Scan Alpha Now" to populate.
                        </div>
                    ) : (
                        <div className="glass-card rounded-2xl overflow-hidden border border-white/10">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs">
                                    <thead className="bg-surface-900/80 border-b border-white/10 text-surface-400 uppercase tracking-wider font-semibold">
                                        <tr>
                                            <th className="p-3.5">ID</th>
                                            <th className="p-3.5">Category</th>
                                            <th className="p-3.5">Opportunity Title</th>
                                            <th className="p-3.5 text-right">Edge</th>
                                            <th className="p-3.5 text-right">Expected Value</th>
                                            <th className="p-3.5 text-right">Price</th>
                                            <th className="p-3.5 text-center">Status</th>
                                            <th className="p-3.5 text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5 font-mono">
                                        {pipelineData.map((op) => (
                                            <tr key={op.id} className="hover:bg-white/[0.02] transition-colors">
                                                <td className="p-3.5 text-surface-400">#{op.id}</td>
                                                <td className="p-3.5">
                                                    <span className="px-2 py-0.5 rounded text-[10px] font-sans font-bold bg-primary-500/20 text-primary-300">
                                                        {op.category}
                                                    </span>
                                                </td>
                                                <td className="p-3.5 font-sans font-medium text-white max-w-xs truncate">
                                                    {op.title}
                                                </td>
                                                <td className="p-3.5 text-right text-emerald-400 font-bold">
                                                    {op.edge ? `+${op.edge.toFixed(1)}%` : '--'}
                                                </td>
                                                <td className="p-3.5 text-right text-cyan-400 font-bold">
                                                    {op.expected_value_pct ? `+${op.expected_value_pct.toFixed(0)}%` : '--'}
                                                </td>
                                                <td className="p-3.5 text-right text-surface-300">
                                                    {op.market_price ? `${op.market_price.toFixed(1)}¢` : '--'}
                                                </td>
                                                <td className="p-3.5 text-center font-sans">
                                                    <span
                                                        className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                                                            op.status === 'ACTIVE'
                                                                ? 'bg-emerald-500/20 text-emerald-300'
                                                                : 'bg-surface-800 text-surface-400'
                                                        }`}
                                                    >
                                                        {op.status}
                                                    </span>
                                                </td>
                                                <td className="p-3.5 text-right font-sans">
                                                    <button
                                                        onClick={() => handleExecuteOpportunityClick(op.id, op.title)}
                                                        disabled={executeOp.isPending}
                                                        className="px-3 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-500 text-white font-semibold text-xs transition-colors shadow-sm disabled:opacity-50"
                                                    >
                                                        Execute
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* 4. DIRECT CLOB FAST-TRADER */}
            {activeTab === 'clob' && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Order Entry Form */}
                    <div className="lg:col-span-6 glass-card rounded-2xl p-6 border border-white/10 space-y-5">
                        <div className="flex items-center justify-between border-b border-white/10 pb-3">
                            <div className="flex items-center gap-2">
                                <Zap className="w-5 h-5 text-amber-400" />
                                <h3 className="font-bold text-white text-base">CLOB Fast Execution</h3>
                            </div>
                            <span className="text-xs font-mono text-surface-400">Gasless EIP-712</span>
                        </div>

                        <form onSubmit={handleQuickOrderSubmit} className="space-y-4">
                            {/* Preset Market Selector */}
                            <div>
                                <label className="block text-xs font-semibold text-surface-300 mb-1.5">
                                    Select from Top 100 Markets
                                </label>
                                <select
                                    value={clobMarketId}
                                    onChange={(e) => {
                                        const mId = e.target.value
                                        setClobMarketId(mId)
                                        const m = marketsData?.markets.find((item) => item.id === mId)
                                        if (m && m.clob_token_ids && m.clob_token_ids.length > 0) {
                                            setClobTokenId(m.clob_token_ids[0])
                                            setClobPrice(parseFloat((m.yes_percentage / 100).toFixed(2)))
                                        }
                                    }}
                                    className="w-full bg-surface-900 border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white focus:border-primary-500 focus:outline-none"
                                >
                                    <option value="">-- Choose active market --</option>
                                    {marketsData?.markets.slice(0, 50).map((m) => (
                                        <option key={m.id} value={m.id}>
                                            {m.title} ({m.yes_percentage.toFixed(0)}% Yes)
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Token ID */}
                            <div>
                                <label className="block text-xs font-semibold text-surface-300 mb-1.5">
                                    Asset Token ID
                                </label>
                                <input
                                    type="text"
                                    value={clobTokenId}
                                    onChange={(e) => setClobTokenId(e.target.value)}
                                    placeholder="Enter outcome token ID or select market above..."
                                    className="w-full bg-surface-900 border border-white/10 rounded-xl px-3 py-2.5 text-xs font-mono text-white focus:border-primary-500 focus:outline-none"
                                />
                            </div>

                            {/* Buy / Sell & Yes / No */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-surface-300 mb-1.5">Side</label>
                                    <div className="grid grid-cols-2 gap-1.5 bg-surface-900 p-1 rounded-xl border border-white/10">
                                        <button
                                            type="button"
                                            onClick={() => setClobSide('BUY')}
                                            className={`py-1.5 text-xs font-bold rounded-lg transition-colors ${
                                                clobSide === 'BUY' ? 'bg-emerald-600 text-white' : 'text-surface-400'
                                            }`}
                                        >
                                            BUY
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setClobSide('SELL')}
                                            className={`py-1.5 text-xs font-bold rounded-lg transition-colors ${
                                                clobSide === 'SELL' ? 'bg-rose-600 text-white' : 'text-surface-400'
                                            }`}
                                        >
                                            SELL
                                        </button>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-semibold text-surface-300 mb-1.5">Outcome Switch</label>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const m = marketsData?.markets.find((item) => item.id === clobMarketId)
                                            if (m && m.clob_token_ids && m.clob_token_ids.length > 1) {
                                                const next = clobTokenId === m.clob_token_ids[0] ? m.clob_token_ids[1] : m.clob_token_ids[0]
                                                setClobTokenId(next)
                                                setClobPrice(parseFloat((1 - clobPrice).toFixed(2)))
                                            }
                                        }}
                                        className="w-full py-2 bg-surface-900 hover:bg-surface-800 text-surface-200 border border-white/10 rounded-xl text-xs font-semibold transition-colors"
                                    >
                                        Flip YES / NO Token
                                    </button>
                                </div>
                            </div>

                            {/* Price & Quick Chips */}
                            <div>
                                <div className="flex justify-between items-center mb-1.5">
                                    <label className="text-xs font-semibold text-surface-300">
                                        Limit Price (${clobPrice.toFixed(2)})
                                    </label>
                                    <span className="text-[11px] font-mono text-cyan-400">
                                        Implied: {(clobPrice * 100).toFixed(0)}%
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    min="0.01"
                                    max="0.99"
                                    step="0.01"
                                    value={clobPrice}
                                    onChange={(e) => setClobPrice(parseFloat(e.target.value))}
                                    className="w-full accent-primary-500 cursor-pointer"
                                />
                                <div className="flex items-center gap-1.5 mt-2">
                                    {[0.10, 0.25, 0.50, 0.75, 0.90].map((p) => (
                                        <button
                                            key={p}
                                            type="button"
                                            onClick={() => setClobPrice(p)}
                                            className="px-2 py-1 rounded bg-surface-900 border border-white/5 text-[10px] font-mono text-surface-300 hover:text-white"
                                        >
                                            {(p * 100).toFixed(0)}¢
                                        </button>
                                    ))}
                                    {orderBook && orderBook.midpoint > 0 && (
                                        <button
                                            type="button"
                                            onClick={() => setClobPrice(orderBook.midpoint)}
                                            className="px-2 py-1 rounded bg-primary-950 border border-primary-500/30 text-[10px] font-mono text-primary-300"
                                        >
                                            Mid {(orderBook.midpoint * 100).toFixed(0)}¢
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Size (Shares) & Est. Cost */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-semibold text-surface-300 mb-1.5">
                                        Size (Shares)
                                    </label>
                                    <input
                                        type="number"
                                        min="1"
                                        step="1"
                                        value={clobSize}
                                        onChange={(e) => setClobSize(parseInt(e.target.value) || 1)}
                                        className="w-full bg-surface-900 border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-white focus:border-primary-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-surface-300 mb-1.5">
                                        Estimated Cost
                                    </label>
                                    <div className="bg-surface-900/60 border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-emerald-400 font-bold">
                                        ${(clobSize * clobPrice).toFixed(2)} USDC
                                    </div>
                                </div>
                            </div>

                            {/* Submit Button */}
                            <button
                                type="submit"
                                disabled={placeOrder.isPending}
                                className={`w-full py-3 rounded-xl font-bold text-xs tracking-wider uppercase transition-all shadow-lg flex items-center justify-center gap-2 ${
                                    clobSide === 'BUY'
                                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/30'
                                        : 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/30'
                                } disabled:opacity-50`}
                            >
                                <Zap className="w-4 h-4" />
                                <span>
                                    {placeOrder.isPending
                                        ? 'Transmitting to CLOB...'
                                        : `${dryRun ? '[Paper]' : '[Live]'} Submit ${clobSide} Order`}
                                </span>
                            </button>
                        </form>
                    </div>

                    {/* Live Order Book Display */}
                    <div className="lg:col-span-6 glass-card rounded-2xl p-6 border border-white/10 space-y-4">
                        <div className="flex items-center justify-between border-b border-white/10 pb-3">
                            <h3 className="font-bold text-white text-base">Polymarket CLOB Book</h3>
                            {orderBook && (
                                <div className="text-xs font-mono text-surface-400">
                                    Spread: {(orderBook.spread * 100).toFixed(1)}¢ | Mid: {(orderBook.midpoint * 100).toFixed(1)}¢
                                </div>
                            )}
                        </div>

                        {!clobTokenId ? (
                            <div className="p-12 text-center text-surface-500 text-xs">
                                Select a market or enter a Token ID to view the live CLOB depth.
                            </div>
                        ) : !orderBook ? (
                            <div className="p-12 text-center text-surface-400 text-xs">
                                Fetching live CLOB depth...
                            </div>
                        ) : (
                            <div className="space-y-4 font-mono text-xs">
                                {/* Asks (Sell Orders) */}
                                <div>
                                    <div className="text-[10px] text-rose-400 font-semibold uppercase mb-1">
                                        Asks (Offers)
                                    </div>
                                    <div className="space-y-1">
                                        {orderBook.asks && orderBook.asks.length > 0 ? (
                                            orderBook.asks.slice(-5).reverse().map((ask, i) => (
                                                <div
                                                    key={i}
                                                    className="flex justify-between items-center px-3 py-1 rounded bg-rose-950/20 text-rose-300"
                                                >
                                                    <span>{(parseFloat(ask.price) * 100).toFixed(1)}¢</span>
                                                    <span>{parseFloat(ask.size).toFixed(0)} shares</span>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-surface-500 text-center py-2">No active asks</div>
                                        )}
                                    </div>
                                </div>

                                {/* Midpoint Divider */}
                                <div className="py-1 px-3 bg-surface-800 text-center text-[11px] font-bold text-primary-300 rounded-lg">
                                    Midpoint: {(orderBook.midpoint * 100).toFixed(1)}¢
                                </div>

                                {/* Bids (Buy Orders) */}
                                <div>
                                    <div className="text-[10px] text-emerald-400 font-semibold uppercase mb-1">
                                        Bids (Bidders)
                                    </div>
                                    <div className="space-y-1">
                                        {orderBook.bids && orderBook.bids.length > 0 ? (
                                            orderBook.bids.slice(0, 5).map((bid, i) => (
                                                <div
                                                    key={i}
                                                    className="flex justify-between items-center px-3 py-1 rounded bg-emerald-950/20 text-emerald-300"
                                                >
                                                    <span>{(parseFloat(bid.price) * 100).toFixed(1)}¢</span>
                                                    <span>{parseFloat(bid.size).toFixed(0)} shares</span>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-surface-500 text-center py-2">No active bids</div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 5. OPEN ORDERS & CANCELLATION */}
            {activeTab === 'orders' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h3 className="font-bold text-white text-base">Active CLOB Limit Orders</h3>
                        {openOrders && openOrders.length > 0 && (
                            <button
                                onClick={() => cancelAllOrders.mutate()}
                                disabled={cancelAllOrders.isPending}
                                className="px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-500/40 text-xs font-semibold transition-colors disabled:opacity-50"
                            >
                                Cancel All Orders
                            </button>
                        )}
                    </div>

                    {ordersLoading ? (
                        <div className="p-12 text-center text-surface-400">Loading active orders from CLOB...</div>
                    ) : !openOrders || openOrders.length === 0 ? (
                        <div className="p-12 text-center text-surface-400 glass-card rounded-2xl">
                            No open orders currently on the Polymarket CLOB book.
                        </div>
                    ) : (
                        <div className="glass-card rounded-2xl overflow-hidden border border-white/10">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs font-mono">
                                    <thead className="bg-surface-900/80 border-b border-white/10 text-surface-400 uppercase tracking-wider font-semibold">
                                        <tr>
                                            <th className="p-3.5">Order ID</th>
                                            <th className="p-3.5">Side</th>
                                            <th className="p-3.5">Price</th>
                                            <th className="p-3.5">Size</th>
                                            <th className="p-3.5">Filled</th>
                                            <th className="p-3.5">Status</th>
                                            <th className="p-3.5 text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {openOrders.map((ord) => (
                                            <tr key={ord.id} className="hover:bg-white/[0.02] transition-colors">
                                                <td className="p-3.5 text-surface-400 max-w-[140px] truncate">{ord.id}</td>
                                                <td className="p-3.5">
                                                    <span
                                                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                                            ord.side === 'BUY'
                                                                ? 'bg-emerald-500/20 text-emerald-300'
                                                                : 'bg-rose-500/20 text-rose-300'
                                                        }`}
                                                    >
                                                        {ord.side}
                                                    </span>
                                                </td>
                                                <td className="p-3.5 text-white font-bold">{(ord.price * 100).toFixed(1)}¢</td>
                                                <td className="p-3.5 text-surface-200">{ord.original_size}</td>
                                                <td className="p-3.5 text-surface-400">{ord.size_matched}</td>
                                                <td className="p-3.5 text-primary-300 font-sans">{ord.status}</td>
                                                <td className="p-3.5 text-right font-sans">
                                                    <button
                                                        onClick={() => cancelOrder.mutate(ord.id)}
                                                        disabled={cancelOrder.isPending}
                                                        className="px-2.5 py-1 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 text-xs font-semibold transition-colors"
                                                    >
                                                        Cancel
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

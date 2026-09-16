import { useState } from 'react'
import {
    TrendingUp,
    Newspaper,
    BarChart3,
    Wallet,
    Trophy,
    Activity,
    User,
    MessageSquare,
    Flame,
    Radio,
    Cpu,
    Globe,
    ShieldCheck,
    Zap,
    ChevronRight,
} from 'lucide-react'
import { MarketList } from './components/MarketList'
import PriceChart from './components/PriceChart'
import { NewsFeed } from './components/NewsFeed'
import { WhaleList } from './components/WhaleList'
import { TopHolders } from './components/TopHolders'
import { PriceMovement } from './components/PriceMovement'
import { TimeframeSelector } from './components/TimeframeSelector'
import { SearchBar } from './components/SearchBar'
import DebateFloor from './components/DebateFloor'
import UserDashboard from './components/UserDashboard'
import { AlphaTerminal } from './components/AlphaTerminal'
import { useMarketStore } from './stores/marketStore'
import { useMarkets } from './hooks/useMarkets'

function App() {
    const { selectedMarket, setSelectedMarket } = useMarketStore()
    const { data: marketsData } = useMarkets()
    const [activeTab, setActiveTab] = useState<'news' | 'whales' | 'holders' | 'stats' | 'debate'>('news')
    const [activeView, setActiveView] = useState<'markets' | 'alpha' | 'user'>('alpha')

    const totalVolume = marketsData?.markets.reduce((acc, m) => acc + (m.volume_24h || 0), 0) || 0
    const topMarkets = marketsData?.markets.slice(0, 6) || []

    return (
        <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col selection:bg-primary-500 selection:text-white relative overflow-x-hidden">
            {/* Ambient Background Glow Highlights */}
            <div className="fixed top-0 left-1/4 w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[140px] pointer-events-none -z-10" />
            <div className="fixed top-1/3 right-10 w-[450px] h-[450px] bg-rose-600/10 rounded-full blur-[140px] pointer-events-none -z-10" />
            <div className="fixed bottom-10 left-10 w-[400px] h-[400px] bg-amber-500/10 rounded-full blur-[130px] pointer-events-none -z-10" />

            {/* Header */}
            <header className="glass border-b border-white/10 sticky top-0 z-50 backdrop-blur-xl bg-[#030816]/90 shadow-2xl">
                <div className="max-w-[1920px] mx-auto px-4 py-3 flex flex-col md:flex-row items-center justify-between gap-3">
                    {/* Brand & Wolf Logic Logo */}
                    <div className="flex items-center gap-3.5 w-full md:w-auto justify-between md:justify-start">
                        <div className="flex items-center gap-3.5">
                            {/* Wolf Logic Logo with Cyberpunk Pulse Ring */}
                            <div className="relative group cursor-pointer">
                                <div className="absolute -inset-1 bg-gradient-to-r from-red-600 via-primary-500 to-amber-500 rounded-full blur-sm opacity-60 group-hover:opacity-100 transition duration-300 animate-pulse"></div>
                                <img
                                    src="/wolf-logic-logo.png"
                                    alt="Wolf Logic - Wolf of All Streets"
                                    className="relative w-11 h-11 rounded-full object-cover ring-2 ring-white/30 shadow-2xl group-hover:scale-105 transition-transform"
                                />
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h1 className="text-xl font-black font-display tracking-tight text-white flex items-center gap-1.5">
                                        <span className="text-gradient-gold font-black tracking-wide drop-shadow-sm">
                                            WOLF LOGIC
                                        </span>
                                        <span className="text-slate-600 font-light text-base">/</span>
                                        <span className="text-gradient font-black">
                                            POLYMARKET
                                        </span>
                                    </h1>
                                    <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider rounded-full bg-primary-500/15 text-primary-300 border border-primary-500/30 shadow-sm">
                                        <Globe className="w-2.5 h-2.5" />
                                        polymarket.complexsimplicity-ai.com
                                    </span>
                                </div>
                                <div className="flex items-center gap-2.5 text-xs text-slate-400 mt-0.5 font-mono">
                                    <span className="text-amber-400 font-bold text-[11px] tracking-wider uppercase">
                                        Wolf of All Streets
                                    </span>
                                    <span className="text-slate-600">•</span>
                                    <span className="flex items-center gap-1.5 text-[11px]">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                        </span>
                                        <span className="text-emerald-400 font-semibold">CLOB LIVE</span>
                                    </span>
                                    <span className="text-slate-600 hidden lg:inline">•</span>
                                    <span className="hidden lg:flex items-center gap-1 text-[11px] text-cyan-300 font-medium">
                                        <Cpu className="w-3 h-3 text-cyan-400" />
                                        AI REASONING ENGINE ACTIVE
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Mobile quick volume */}
                        <div className="flex md:hidden items-center gap-2 font-mono text-xs bg-surface-900/80 px-2.5 py-1 rounded-lg border border-white/5">
                            <span className="text-slate-400">Vol:</span>
                            <span className="text-emerald-400 font-bold">
                                ${(totalVolume / 1_000_000).toFixed(1)}M
                            </span>
                        </div>
                    </div>

                    {/* Navigation View Switcher & Search */}
                    <div className="flex-1 flex flex-col sm:flex-row items-center justify-end gap-3 w-full">
                        {/* Global Metrics Strip */}
                        <div className="hidden xl:flex items-center gap-4 px-3.5 py-1.5 rounded-xl bg-surface-900/70 border border-white/10 text-xs font-mono shadow-inner">
                            <div>
                                <span className="text-slate-500">24H VOL: </span>
                                <span className="text-emerald-400 font-bold">
                                    ${(totalVolume / 1_000_000).toFixed(2)}M
                                </span>
                            </div>
                            <span className="text-slate-700">|</span>
                            <div>
                                <span className="text-slate-500">INDEXED: </span>
                                <span className="text-white font-semibold">{marketsData?.total ?? 100}</span>
                            </div>
                        </div>

                        {/* View Switcher Pill */}
                        <div className="flex items-center gap-1 bg-surface-900/95 border border-white/15 rounded-xl p-1 shadow-2xl">
                            <button
                                onClick={() => setActiveView('alpha')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'alpha'
                                        ? 'bg-gradient-to-r from-amber-500/40 via-primary-500/40 to-accent-500/40 text-white border border-amber-500/50 shadow-lg shadow-amber-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <Flame className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                                Alpha Terminal
                            </button>
                            <button
                                onClick={() => setActiveView('markets')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'markets'
                                        ? 'bg-primary-500/30 text-white border border-primary-500/50 shadow-lg shadow-primary-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <BarChart3 className="w-3.5 h-3.5 text-primary-400" />
                                Markets & Charts
                            </button>
                            <button
                                onClick={() => setActiveView('user')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'user'
                                        ? 'bg-indigo-500/30 text-white border border-indigo-500/50 shadow-lg shadow-indigo-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <User className="w-3.5 h-3.5 text-indigo-400" />
                                Whale Lab
                            </button>
                        </div>

                        {activeView === 'markets' && (
                            <div className="w-full sm:w-64">
                                <SearchBar />
                            </div>
                        )}
                    </div>
                </div>

                {/* Live Ticker Bar */}
                {topMarkets.length > 0 && (
                    <div className="border-t border-white/5 bg-surface-950/60 px-4 py-1.5 overflow-x-auto flex items-center gap-3 text-xs font-mono scrollbar-none">
                        <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 uppercase tracking-wider shrink-0">
                            <Zap className="w-3 h-3" />
                            TOP MOVERS:
                        </span>
                        <div className="flex items-center gap-4 shrink-0">
                            {topMarkets.map((m) => (
                                <button
                                    key={m.id}
                                    onClick={() => {
                                        setSelectedMarket(m)
                                        if (activeView !== 'markets') setActiveView('markets')
                                    }}
                                    className="flex items-center gap-2 hover:bg-white/5 px-2 py-0.5 rounded transition-colors group text-left shrink-0"
                                >
                                    <span className="text-slate-300 group-hover:text-white truncate max-w-[180px] sm:max-w-[240px]">
                                        {m.title}
                                    </span>
                                    <span className="px-1.5 py-0.2 rounded font-bold text-[11px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                        {m.yes_percentage.toFixed(0)}% Yes
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </header>

            {/* Main Content Area */}
            <main className="max-w-[1920px] mx-auto p-4 flex-1 w-full">
                {activeView === 'markets' && (
                    <div className="grid grid-cols-12 gap-4 lg:gap-6">
                        {/* Sidebar - Market List */}
                        <aside className="col-span-12 lg:col-span-4 xl:col-span-3">
                            <div className="glass-card rounded-2xl p-4 sticky top-28 border border-white/10 shadow-2xl">
                                <div className="flex items-center justify-between gap-2 mb-4 pb-3 border-b border-white/10">
                                    <div className="flex items-center gap-2">
                                        <BarChart3 className="w-5 h-5 text-primary-400" />
                                        <h2 className="font-bold font-display text-white text-base">Top 100 Markets</h2>
                                    </div>
                                    <span className="text-[11px] font-mono text-slate-400 px-2 py-0.5 rounded-md bg-surface-900 border border-white/5">
                                        By 7D Volume
                                    </span>
                                </div>
                                <MarketList />
                            </div>
                        </aside>

                        {/* Main Content Area */}
                        <div className="col-span-12 lg:col-span-8 xl:col-span-9 space-y-4 lg:space-y-6">
                            {/* Chart Hero Section */}
                            <section className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl relative overflow-hidden">
                                <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl pointer-events-none" />

                                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4 pb-4 border-b border-white/10 relative z-10">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="px-2.5 py-0.5 text-[10px] font-bold font-mono uppercase tracking-wider rounded bg-primary-500/20 text-primary-300 border border-primary-500/40">
                                                ACTIVE CLOB ORDERBOOK
                                            </span>
                                            {selectedMarket?.category && (
                                                <span className="px-2.5 py-0.5 text-[10px] font-semibold rounded bg-surface-800 text-slate-300 border border-white/5">
                                                    {selectedMarket.category}
                                                </span>
                                            )}
                                        </div>
                                        <h2 className="text-xl sm:text-2xl font-black font-display text-white truncate tracking-tight">
                                            {selectedMarket?.title || 'Select a market from the sidebar'}
                                        </h2>

                                        {selectedMarket && (
                                            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-300 mt-2.5">
                                                <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-900/80 border border-white/10 shadow-sm">
                                                    <span className="text-slate-400">YES ODDS:</span>
                                                    <span className="text-emerald-400 font-bold text-sm">
                                                        {selectedMarket.yes_percentage.toFixed(1)}%
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-900/80 border border-white/10 shadow-sm">
                                                    <span className="text-slate-400">NO ODDS:</span>
                                                    <span className="text-rose-400 font-bold text-sm">
                                                        {(100 - selectedMarket.yes_percentage).toFixed(1)}%
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-900/80 border border-white/10 shadow-sm">
                                                    <span className="text-slate-400">24H VOLUME:</span>
                                                    <span className="text-white font-bold">
                                                        {new Intl.NumberFormat('en-US', {
                                                            style: 'currency',
                                                            currency: 'USD',
                                                            maximumFractionDigits: 0,
                                                        }).format(selectedMarket.volume_24h)}
                                                    </span>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="shrink-0">
                                        <TimeframeSelector />
                                    </div>
                                </div>

                                <PriceChart />
                            </section>

                            {/* Deep Analysis & News Tabbed Section */}
                            <section className="glass-card rounded-2xl p-4 lg:p-6 border border-white/10 shadow-2xl">
                                <div className="flex items-center gap-2 sm:gap-3 mb-4 border-b border-white/10 pb-3 overflow-x-auto">
                                    <button
                                        onClick={() => setActiveTab('news')}
                                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-display font-semibold relative transition-all whitespace-nowrap ${
                                            activeTab === 'news'
                                                ? 'bg-accent-500/25 text-accent-300 border border-accent-500/40 shadow-sm shadow-accent-500/10'
                                                : 'text-slate-400 hover:text-white'
                                        }`}
                                    >
                                        <Newspaper className="w-4 h-4 text-accent-400" />
                                        <span>Related News</span>
                                    </button>

                                    <button
                                        onClick={() => setActiveTab('whales')}
                                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-display font-semibold relative transition-all whitespace-nowrap ${
                                            activeTab === 'whales'
                                                ? 'bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 shadow-sm shadow-emerald-500/10'
                                                : 'text-slate-400 hover:text-white'
                                        }`}
                                    >
                                        <Wallet className="w-4 h-4 text-emerald-400" />
                                        <span>Whale Orders</span>
                                    </button>

                                    <button
                                        onClick={() => setActiveTab('holders')}
                                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-display font-semibold relative transition-all whitespace-nowrap ${
                                            activeTab === 'holders'
                                                ? 'bg-amber-500/25 text-amber-300 border border-amber-500/40 shadow-sm shadow-amber-500/10'
                                                : 'text-slate-400 hover:text-white'
                                        }`}
                                    >
                                        <Trophy className="w-4 h-4 text-amber-400" />
                                        <span>Top Holders</span>
                                    </button>

                                    <button
                                        onClick={() => setActiveTab('stats')}
                                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-display font-semibold relative transition-all whitespace-nowrap ${
                                            activeTab === 'stats'
                                                ? 'bg-purple-500/25 text-purple-300 border border-purple-500/40 shadow-sm shadow-purple-500/10'
                                                : 'text-slate-400 hover:text-white'
                                        }`}
                                    >
                                        <Activity className="w-4 h-4 text-purple-400" />
                                        <span>Price Analysis</span>
                                    </button>

                                    <button
                                        onClick={() => setActiveTab('debate')}
                                        className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-display font-semibold relative transition-all whitespace-nowrap ${
                                            activeTab === 'debate'
                                                ? 'bg-blue-500/25 text-blue-300 border border-blue-500/40 shadow-sm shadow-blue-500/10'
                                                : 'text-slate-400 hover:text-white'
                                        }`}
                                    >
                                        <MessageSquare className="w-4 h-4 text-blue-400" />
                                        <span>AI Debate Floor</span>
                                    </button>
                                </div>

                                <div className="mt-4">
                                    {activeTab === 'news' && <NewsFeed />}
                                    {activeTab === 'whales' && <WhaleList />}
                                    {activeTab === 'holders' && <TopHolders />}
                                    {activeTab === 'stats' && <PriceMovement />}
                                    {activeTab === 'debate' && <DebateFloor marketId={selectedMarket?.id || null} />}
                                </div>
                            </section>
                        </div>
                    </div>
                )}

                {activeView === 'alpha' && <AlphaTerminal />}

                {activeView === 'user' && <UserDashboard />}
            </main>

            {/* Polished Footer with Wolf of All Streets Branding */}
            <footer className="glass border-t border-white/10 mt-12 py-6 px-4 bg-[#030816]/95">
                <div className="max-w-[1920px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400 font-mono">
                    <div className="flex items-center gap-3">
                        <img
                            src="/wolf-logic-logo.png"
                            alt="Wolf Logic"
                            className="w-6 h-6 rounded-full object-cover ring-1 ring-white/20"
                        />
                        <span className="text-slate-200 font-bold">WOLF LOGIC</span>
                        <span className="text-slate-600">•</span>
                        <span>Wolf of All Streets Alpha Terminal</span>
                        <span className="text-slate-600">•</span>
                        <span>Direct CLOB Gateway</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-slate-500">
                            Status: <strong className="text-emerald-400 font-semibold">Operational</strong>
                        </span>
                        <span className="text-slate-700">|</span>
                        <span className="text-slate-500">
                            Data Feed: <strong className="text-slate-300">Live Polymarket CLOB</strong>
                        </span>
                    </div>
                </div>
            </footer>
        </div>
    )
}

export default App

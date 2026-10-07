import { useEffect, useState } from 'react'
import {
    Newspaper,
    BarChart3,
    Wallet,
    Trophy,
    Activity,
    Zap,
    Gauge,
} from 'lucide-react'
import { MarketList } from './components/MarketList'
import PriceChart from './components/PriceChart'
import MatchupPanel from './components/MatchupPanel'
import HeadToHead from './components/HeadToHead'
import { NewsFeed } from './components/NewsFeed'
import { WhaleList } from './components/WhaleList'
import { TopHolders } from './components/TopHolders'
import { PriceMovement } from './components/PriceMovement'
import { TimeframeSelector } from './components/TimeframeSelector'
import { SearchBar } from './components/SearchBar'
import AccountPage from './components/AccountPage'
import LiveStream from './components/LiveStream'
import TeamsPage from './components/TeamsPage'
import { LatencyPanel } from './components/LatencyPanel'
import { GlobalLatencyTicker } from './components/GlobalLatencyTicker'
import { CommandDashboard } from './components/CommandDashboard'
import { useMarketStore } from './stores/marketStore'
import { useMarkets } from './hooks/useMarkets'
import { AuthGate } from './components/AuthGate'
import { useAuthStore } from './stores/authStore'
import { marketSides } from './utils/sides'
import { ExternalLink, LogOut, LayoutDashboard } from 'lucide-react'


function App() {
    const { selectedMarket, setSelectedMarket } = useMarketStore()
    const { data: marketsData } = useMarkets()
    const { logout, user } = useAuthStore()
    const [activeTab, setActiveTab] = useState<'news' | 'whales' | 'holders' | 'stats'>('news')
    const [activeView, setActiveView] = useState<'dashboard' | 'markets' | 'teams' | 'account' | 'latency'>('dashboard')


    useEffect(() => {
        const list = marketsData?.markets
        if (selectedMarket || !list?.length) return
        const live = list.find((m) => m.yes_percentage > 3 && m.yes_percentage < 97)
        setSelectedMarket(live ?? list[0])
    }, [marketsData, selectedMarket, setSelectedMarket])

    const totalVolume = marketsData?.markets.reduce((acc, m) => acc + (m.volume_24h || 0), 0) || 0
    const topMarkets = marketsData?.markets.slice(0, 6) || []

    return (
        <AuthGate>
            <LiveStream />
            <div className="min-h-screen bg-[#020617] text-slate-100 flex flex-col selection:bg-primary-500 selection:text-white relative overflow-x-hidden">
                {/* Ambient Background Glow Highlights */}
                <div className="fixed top-0 left-1/4 w-[500px] h-[500px] bg-primary-600/10 rounded-full blur-[140px] pointer-events-none -z-10" />
                <div className="fixed top-1/3 right-10 w-[450px] h-[450px] bg-rose-600/10 rounded-full blur-[140px] pointer-events-none -z-10" />
                <div className="fixed bottom-10 left-10 w-[400px] h-[400px] bg-amber-500/10 rounded-full blur-[130px] pointer-events-none -z-10" />

            {/* Header */}
            <header className="glass border-b border-white/10 sticky top-0 z-50 backdrop-blur-xl bg-[#030816]/90 shadow-2xl">
                <div className="max-w-[1920px] mx-auto px-4 py-3 flex flex-col md:flex-row items-center justify-between gap-3">
                    {/* Brand & CSMP Logo */}
                    <div className="flex items-center gap-3.5 w-full md:w-auto justify-between md:justify-start">
                        <div className="flex items-center gap-3.5">
                            {/* Wolf Logic emblem: opens Polymarket US in a new tab */}
                            <a
                                href="https://polymarket.us"
                                target="_blank"
                                rel="noopener noreferrer"
                                title="Open Polymarket US in a new tab"
                                className="shrink-0"
                            >
                                <img
                                    src="/wolf-emblem.png"
                                    alt="Wolf Logic: open Polymarket US"
                                    className="h-11 w-11 rounded-full object-cover shadow-lg ring-1 ring-white/20 hover:ring-primary-400/60 transition"
                                />
                            </a>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h1 className="text-xl font-black font-display tracking-tight text-white flex items-center gap-1.5">
                                        <span className="text-gradient font-black">
                                            MARKET INTELLIGENCE
                                        </span>
                                    </h1>
                                </div>
                                <div className="flex items-center gap-2.5 text-xs text-slate-400 mt-0.5 font-mono">
                                    <span className="flex items-center gap-1.5 text-[11px]">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                        </span>
                                        <span className="text-emerald-400 font-semibold">LIVE INSTITUTIONAL FEED</span>
                                    </span>
                                    <span className="text-slate-600 hidden sm:inline">•</span>
                                    <span className="hidden sm:inline-flex text-[11px] text-cyan-300 font-medium">
                                        ANALYTICAL ENGINE
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
                        {/* Omni-Present Multi-Feed Latency Ticker */}
                        <GlobalLatencyTicker />

                        {/* Global Metrics Strip */}
                        <div className="hidden 2xl:flex items-center gap-4 px-3.5 py-1.5 rounded-xl bg-surface-900/70 border border-white/10 text-xs font-mono shadow-inner">
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
                                onClick={() => setActiveView('dashboard')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'dashboard'
                                        ? 'bg-primary-500/30 text-white border border-primary-500/50 shadow-lg shadow-primary-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <LayoutDashboard className="w-3.5 h-3.5 text-primary-400" />
                                Dashboard
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
                                onClick={() => setActiveView('teams')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'teams'
                                        ? 'bg-amber-500/30 text-white border border-amber-500/50 shadow-lg shadow-amber-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <Trophy className="w-3.5 h-3.5 text-amber-400" />
                                Teams
                            </button>
                            <button
                                onClick={() => setActiveView('account')}
                                className={`px-4 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'account'
                                        ? 'bg-emerald-500/30 text-white border border-emerald-500/50 shadow-lg shadow-emerald-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                                My Account
                            </button>
                            <button
                                onClick={() => setActiveView('latency')}
                                className={`px-3.5 py-1.5 text-xs font-bold font-display rounded-lg transition-all duration-200 flex items-center gap-1.5 ${
                                    activeView === 'latency'
                                        ? 'bg-cyan-500/30 text-white border border-cyan-500/50 shadow-lg shadow-cyan-500/15'
                                        : 'text-slate-400 hover:text-white'
                                }`}
                            >
                                <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                                Latency
                            </button>
                        </div>

                        <a
                            href="https://polymarket.us"
                            target="_blank"
                            rel="noopener noreferrer"
                            title="Open Polymarket in a new tab"
                            className="px-3 py-1.5 rounded-xl bg-surface-900/90 hover:bg-primary-500/20 text-slate-300 hover:text-white border border-white/10 transition-colors flex items-center gap-1.5 text-xs font-bold font-display"
                        >
                            <ExternalLink className="w-3.5 h-3.5 text-primary-400" />
                            Polymarket
                        </a>

                        {/* Operator / Lock Button */}
                        <div className="flex items-center gap-2">
                            {/* WatchReopenButton removed */}
                            {user && (
                                <span className="hidden xl:inline text-[11px] font-mono text-slate-400 bg-surface-900/80 px-2.5 py-1 rounded-lg border border-white/5">
                                    {user.name}
                                </span>
                            )}
                            <button
                                onClick={logout}
                                title="Lock Terminal / Sign Out"
                                className="px-3 py-1.5 rounded-xl bg-surface-900/90 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-white/10 transition-colors flex items-center gap-1.5 text-xs font-mono"
                            >
                                <LogOut className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">Lock</span>
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
                                        {(() => {
                                            const sd = marketSides(m)
                                            return sd.named
                                                ? `${(sd.a.pct >= sd.b.pct ? sd.a : sd.b).label} ${Math.max(sd.a.pct, sd.b.pct).toFixed(0)}%`
                                                : `${sd.a.pct.toFixed(0)}% Yes`
                                        })()}
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
                                        <h2 className="font-bold font-display text-white text-base">Top 100 Sports Markets</h2>
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
                                            <div className="mt-3">
                                                <HeadToHead market={selectedMarket} />
                                            </div>
                                        )}
                                    </div>

                                    <div className="shrink-0">
                                        <TimeframeSelector />
                                    </div>
                                </div>

                                <PriceChart />
                            </section>

                            <MatchupPanel market={selectedMarket} />

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
                                </div>

                                <div className="mt-4">
                                    {activeTab === 'news' && <NewsFeed />}
                                    {activeTab === 'whales' && <WhaleList />}
                                    {activeTab === 'holders' && <TopHolders />}
                                    {activeTab === 'stats' && <PriceMovement />}
                                </div>
                            </section>
                        </div>
                    </div>
                )}

                {activeView === 'dashboard' && <CommandDashboard />}
                {activeView === 'account' && <AccountPage />}
                {activeView === 'teams' && <TeamsPage />}
                {activeView === 'latency' && <LatencyPanel />}

            </main>

            {/* Polished Footer with CSMP Branding */}
            <footer className="glass border-t border-white/10 mt-12 py-6 px-4 bg-[#030816]/95">
                <div className="max-w-[1920px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400 font-mono">
                    <div className="flex items-center gap-3">
                        <img
                            src="/wolf-emblem.png"
                            alt="Wolf Logic"
                            className="w-6 h-6 rounded-full object-cover"
                        />
                        <span className="text-slate-200 font-bold">COMPLEX SIMPLICITY MEDIA</span>
                        <span className="text-slate-600">•</span>
                        <span>Institutional Market Intelligence</span>
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
        </AuthGate>
    )
}

export default App

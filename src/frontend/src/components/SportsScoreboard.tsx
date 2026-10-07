import { useState, useMemo } from 'react'
import {
    Flame,
    Clock3,
    Heart,
    Star,
    TrendingUp,
    ExternalLink,
    Search,
    Grid3X3,
    LayoutGrid,
    Columns2,
    Square,
    Zap,
    ChevronDown
} from 'lucide-react'
import { SportsMatch, SportCode, FeedProviderId, FeedProviderConfig } from '../types/sports'
import { useMarketStore, Market } from '../stores/marketStore'
import { useMarkets } from '../hooks/useMarkets'

interface SportsScoreboardProps {
    onSelectMarket?: (market: Market) => void
}

const FEED_PROVIDERS: FeedProviderConfig[] = [
    {
        id: 'mlb_statsapi',
        name: 'MLB StatsAPI Direct',
        short: 'STATS-API',
        latencyMs: 42,
        status: 'optimal',
        description: 'Official direct stadium feed (lowest baseball latency)'
    },
    {
        id: 'poly_radar',
        name: 'Polymarket BBO Radar',
        short: 'POLY-RADAR',
        latencyMs: 18,
        status: 'optimal',
        description: 'Sub-20ms WebSocket tick order book feed'
    },
    {
        id: 'espn_fast',
        name: 'ESPN Fast Wire',
        short: 'ESPN-WIRE',
        latencyMs: 85,
        status: 'backup',
        description: 'Multi-sport commentary & broadcast scores'
    },
    {
        id: 'thescore_wire',
        name: 'TheScore Rapid',
        short: 'THESCORE',
        latencyMs: 115,
        status: 'delayed',
        description: 'Fallback backup sports aggregator'
    }
]

const DEMO_MATCHES: SportsMatch[] = [
    {
        id: 'mlb-dodgers-braves',
        sport: 'mlb',
        leagueId: 'mlb',
        leagueName: 'MLB NLDS Game 4',
        status: 'live',
        statusDetail: 'Top 7th',
        startTime: new Date().toISOString(),
        homeTeam: {
            id: 'lad',
            name: 'Los Angeles Dodgers',
            shortName: 'LAD',
            badgeColor: '#005A9C',
            record: '2-1 Series'
        },
        awayTeam: {
            id: 'atl',
            name: 'Atlanta Braves',
            shortName: 'ATL',
            badgeColor: '#CE1141',
            record: '1-2 Series'
        },
        score: { home: 5, away: 2 },
        scoreSegments: [
            { label: '1-3', home: 2, away: 0 },
            { label: '4-6', home: 3, away: 2 },
            { label: '7th', home: 0, away: 0, active: true }
        ],
        baseballSituation: {
            balls: 2,
            strikes: 2,
            outs: 2,
            runnerOnFirst: true,
            runnerOnSecond: false,
            runnerOnThird: true,
            currentPitcher: {
                name: 'Yoshinobu Yamamoto',
                hand: 'R',
                pitchCount: 94,
                era: '1.88',
                strikeouts: 10
            },
            currentBatter: {
                name: 'Matt Olson',
                avg: '.282',
                hits: 1,
                atBats: 3
            }
        },
        venue: 'Dodger Stadium',
        marketSlug: 'dodgers-vs-braves-nlds-game-4',
        marketTitle: 'Dodgers to Win NLDS Game 4 vs Braves',
        impliedOdds: { home: 84, away: 16 }
    },
    {
        id: 'mlb-padres-brewers',
        sport: 'mlb',
        leagueId: 'mlb',
        leagueName: 'MLB NLDS Game 4',
        status: 'live',
        statusDetail: 'Bot 8th',
        startTime: new Date().toISOString(),
        homeTeam: {
            id: 'sd',
            name: 'San Diego Padres',
            shortName: 'SD',
            badgeColor: '#2F241D',
            record: '3-1 Series'
        },
        awayTeam: {
            id: 'mil',
            name: 'Milwaukee Brewers',
            shortName: 'MIL',
            badgeColor: '#12284C',
            record: '1-3 Series'
        },
        score: { home: 4, away: 3 },
        scoreSegments: [
            { label: '1-3', home: 1, away: 2 },
            { label: '4-6', home: 2, away: 1 },
            { label: '7-8', home: 1, away: 0, active: true }
        ],
        baseballSituation: {
            balls: 1,
            strikes: 1,
            outs: 1,
            runnerOnFirst: true,
            runnerOnSecond: true,
            runnerOnThird: false,
            currentPitcher: {
                name: 'Michael King',
                hand: 'R',
                pitchCount: 32,
                era: '2.14',
                strikeouts: 4
            },
            currentBatter: {
                name: 'Christian Yelich',
                avg: '.315',
                hits: 2,
                atBats: 4
            }
        },
        venue: 'Petco Park',
        marketSlug: 'padres-vs-brewers-nlds-game-4',
        marketTitle: 'Padres to Win vs Brewers (+1.5)',
        impliedOdds: { home: 68, away: 32 }
    },
    {
        id: 'nfl-eagles-rams',
        sport: 'nfl',
        leagueId: 'nfl',
        leagueName: 'NFL Week 5',
        status: 'live',
        statusDetail: '4th Qtr 03:12',
        startTime: new Date().toISOString(),
        homeTeam: {
            id: 'phi',
            name: 'Philadelphia Eagles',
            shortName: 'PHI',
            badgeColor: '#004C54',
            record: '4-0'
        },
        awayTeam: {
            id: 'lar',
            name: 'Los Angeles Rams',
            shortName: 'LAR',
            badgeColor: '#003594',
            record: '2-2'
        },
        score: { home: 24, away: 17 },
        scoreSegments: [
            { label: 'Q1', home: 7, away: 3 },
            { label: 'Q2', home: 10, away: 7 },
            { label: 'Q3', home: 0, away: 7 },
            { label: 'Q4', home: 7, away: 0, active: true }
        ],
        footballSituation: {
            down: 3,
            distance: 4,
            yardLine: 'LAR 32',
            possession: 'home',
            redZone: true
        },
        venue: 'Lincoln Financial Field',
        marketSlug: 'will-philadelphia-eagles-win-vs-rams',
        marketTitle: 'Philadelphia Eagles to Win vs Los Angeles Rams',
        impliedOdds: { home: 78, away: 22 }
    },
    {
        id: 'nfl-lions-panthers',
        sport: 'nfl',
        leagueId: 'nfl',
        leagueName: 'NFL Week 5',
        status: 'upcoming',
        statusDetail: 'Today 4:05 PM',
        startTime: new Date(Date.now() + 7200000).toISOString(),
        homeTeam: {
            id: 'det',
            name: 'Detroit Lions',
            shortName: 'DET',
            badgeColor: '#0076B6',
            record: '3-1'
        },
        awayTeam: {
            id: 'car',
            name: 'Carolina Panthers',
            shortName: 'CAR',
            badgeColor: '#0085CA',
            record: '1-3'
        },
        score: { home: 0, away: 0 },
        scoreSegments: [],
        venue: 'Ford Field',
        marketSlug: 'panthers-vs-lions-moneyline',
        marketTitle: 'Carolina Panthers to Win vs Detroit Lions',
        impliedOdds: { home: 65, away: 35 }
    },
    {
        id: 'cfb-byu-iowast',
        sport: 'cfb',
        leagueId: 'cfb',
        leagueName: 'College Football',
        status: 'upcoming',
        statusDetail: 'Tonight 7:30 PM',
        startTime: new Date(Date.now() + 18000000).toISOString(),
        homeTeam: {
            id: 'isu',
            name: 'Iowa State Cyclones',
            shortName: 'ISU',
            badgeColor: '#C8102E',
            record: '5-0'
        },
        awayTeam: {
            id: 'byu',
            name: 'BYU Cougars',
            shortName: 'BYU',
            badgeColor: '#002E5D',
            record: '5-0'
        },
        score: { home: 0, away: 0 },
        scoreSegments: [],
        venue: 'Jack Trice Stadium',
        marketSlug: 'byu-vs-iowa-state-cfb',
        marketTitle: 'Iowa State (-7.5) vs BYU Cougars',
        impliedOdds: { home: 62, away: 38 }
    },
    {
        id: 'nba-lakers-warriors',
        sport: 'nba',
        leagueId: 'nba',
        leagueName: 'NBA Preseason',
        status: 'finished',
        statusDetail: 'Final',
        startTime: new Date(Date.now() - 86400000).toISOString(),
        homeTeam: {
            id: 'lal',
            name: 'Los Angeles Lakers',
            shortName: 'LAL',
            badgeColor: '#552583',
            record: '1-1'
        },
        awayTeam: {
            id: 'gsw',
            name: 'Golden State Warriors',
            shortName: 'GSW',
            badgeColor: '#1D428A',
            record: '2-0'
        },
        score: { home: 107, away: 111 },
        scoreSegments: [
            { label: 'Q1', home: 28, away: 31 },
            { label: 'Q2', home: 25, away: 27 },
            { label: 'Q3', home: 29, away: 26 },
            { label: 'Q4', home: 25, away: 27 }
        ],
        venue: 'Crypto.com Arena'
    },
    {
        id: 'mlb-yankees-rays',
        sport: 'mlb',
        leagueId: 'mlb',
        leagueName: 'MLB ALDS Game 4',
        status: 'upcoming',
        statusDetail: 'Today 8:08 PM',
        startTime: new Date(Date.now() + 28800000).toISOString(),
        homeTeam: {
            id: 'nyy',
            name: 'New York Yankees',
            shortName: 'NYY',
            badgeColor: '#003087',
            record: '2-1 Series'
        },
        awayTeam: {
            id: 'tb',
            name: 'Tampa Bay Rays',
            shortName: 'TB',
            badgeColor: '#092C5C',
            record: '1-2 Series'
        },
        score: { home: 0, away: 0 },
        scoreSegments: [],
        venue: 'Yankee Stadium',
        marketSlug: 'yankees-vs-rays-alds-game-4',
        marketTitle: 'Rays vs Yankees ALDS Game 4',
        impliedOdds: { home: 54, away: 46 }
    },
    {
        id: 'nfl-ravens-cowboys',
        sport: 'nfl',
        leagueId: 'nfl',
        leagueName: 'NFL Week 5',
        status: 'upcoming',
        statusDetail: 'Tomorrow 1:00 PM',
        startTime: new Date(Date.now() + 86400000).toISOString(),
        homeTeam: {
            id: 'bal',
            name: 'Baltimore Ravens',
            shortName: 'BAL',
            badgeColor: '#241773',
            record: '3-1'
        },
        awayTeam: {
            id: 'dal',
            name: 'Dallas Cowboys',
            shortName: 'DAL',
            badgeColor: '#041E42',
            record: '2-2'
        },
        score: { home: 0, away: 0 },
        scoreSegments: [],
        venue: 'M&T Bank Stadium',
        marketSlug: 'ravens-vs-cowboys-nfl',
        marketTitle: 'Baltimore Ravens (-7.5) vs Dallas Cowboys',
        impliedOdds: { home: 71, away: 29 }
    }
]

export function SportsScoreboard({ onSelectMarket }: SportsScoreboardProps) {
    const { setSelectedMarket } = useMarketStore()
    const { data: marketsData } = useMarkets()

    const [sportFilter, setSportFilter] = useState<SportCode>('all')
    const [stateFilter, setStateFilter] = useState<'ALL' | 'LIVE' | 'UPCOMING' | 'FINISHED'>('ALL')
    const [searchTerm, setSearchTerm] = useState('')
    const [columnCount, setColumnCount] = useState<1 | 2 | 3 | 4>(2) // Default to 2 columns for 2X double size!
    const [activeProvider, setActiveProvider] = useState<FeedProviderId>('mlb_statsapi')
    const [isProviderMenuOpen, setIsProviderMenuOpen] = useState(false)

    const [favorites, setFavorites] = useState<string[]>(() => {
        try {
            const saved = localStorage.getItem('poly_sports_favorites')
            return saved ? JSON.parse(saved) : ['mlb-dodgers-braves']
        } catch {
            return ['mlb-dodgers-braves']
        }
    })

    const toggleFavorite = (id: string) => {
        setFavorites(prev => {
            const next = prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]
            try {
                localStorage.setItem('poly_sports_favorites', JSON.stringify(next))
            } catch {
                // ignore
            }
            return next
        })
    }

    const currentProviderConfig = useMemo(() => {
        return FEED_PROVIDERS.find(p => p.id === activeProvider) || FEED_PROVIDERS[0]
    }, [activeProvider])

    // Merge Polymarket markets
    const matchesWithMarkets = useMemo(() => {
        const polyList = marketsData?.markets || []
        return DEMO_MATCHES.map(match => {
            const matchedMarket = polyList.find(m => {
                const t = m.title.toLowerCase()
                return (
                    t.includes(match.homeTeam.name.toLowerCase()) ||
                    t.includes(match.awayTeam.name.toLowerCase()) ||
                    (match.marketSlug && m.slug?.includes(match.marketSlug))
                )
            })
            if (matchedMarket) {
                return {
                    ...match,
                    marketId: matchedMarket.id,
                    marketTitle: matchedMarket.title,
                    marketSlug: matchedMarket.slug,
                    impliedOdds: {
                        home: Math.round(matchedMarket.yes_percentage),
                        away: Math.round(100 - matchedMarket.yes_percentage)
                    }
                }
            }
            return match
        })
    }, [marketsData])

    // Filtered matches
    const filteredMatches = useMemo(() => {
        return matchesWithMarkets.filter(match => {
            if (sportFilter !== 'all' && match.sport !== sportFilter) return false
            if (stateFilter === 'LIVE' && match.status !== 'live') return false
            if (stateFilter === 'UPCOMING' && match.status !== 'upcoming') return false
            if (stateFilter === 'FINISHED' && match.status !== 'finished') return false

            if (searchTerm.trim()) {
                const term = searchTerm.toLowerCase()
                const matchesSearch =
                    match.homeTeam.name.toLowerCase().includes(term) ||
                    match.awayTeam.name.toLowerCase().includes(term) ||
                    match.leagueName.toLowerCase().includes(term) ||
                    (match.venue && match.venue.toLowerCase().includes(term))
                if (!matchesSearch) return false
            }
            return true
        })
    }, [matchesWithMarkets, sportFilter, stateFilter, searchTerm])

    const pinnedMatches = useMemo(() => {
        return matchesWithMarkets.filter(m => favorites.includes(m.id))
    }, [matchesWithMarkets, favorites])

    const handleMarketClick = (match: SportsMatch) => {
        if (!match.marketId) return
        const market = marketsData?.markets?.find(m => m.id === match.marketId)
        if (market) {
            setSelectedMarket(market)
            if (onSelectMarket) onSelectMarket(market)
        }
    }

    // Dynamic grid classes based on Wolf's column choice
    const gridColsClass = useMemo(() => {
        if (columnCount === 1) return 'grid-cols-1'
        if (columnCount === 2) return 'grid-cols-1 lg:grid-cols-2'
        if (columnCount === 3) return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
        return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4'
    }, [columnCount])

    return (
        <div className="w-full glass-card rounded-2xl p-4 sm:p-5 border border-white/10 shadow-2xl relative space-y-4">
            {/* Top Command Bar */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                        <Flame className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2.5">
                            <h2 className="text-base font-black font-display uppercase tracking-wider text-white">
                                Multi-Sport Live Tactical Board
                            </h2>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                {matchesWithMarkets.filter(m => m.status === 'live').length} IN-PLAY
                            </span>
                        </div>
                        <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                            Real-Time Pitches, Counts & Situations • Linked to Polymarket Clob
                        </p>
                    </div>
                </div>

                {/* Right Controls: Provider Switcher & Layout Toggles */}
                <div className="flex flex-wrap items-center gap-2.5">
                    {/* Live API Provider Switcher */}
                    <div className="relative">
                        <button
                            onClick={() => setIsProviderMenuOpen(prev => !prev)}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-950/90 border border-white/15 hover:border-emerald-500/40 text-xs font-mono shadow-inner transition-all"
                            title="Switch Active Sports API Provider"
                        >
                            <Zap className="w-3.5 h-3.5 text-amber-400" />
                            <span className="text-slate-300 font-bold">{currentProviderConfig.short}</span>
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px] border border-emerald-500/30">
                                {currentProviderConfig.latencyMs}ms
                            </span>
                            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                        </button>

                        {/* Dropdown Menu */}
                        {isProviderMenuOpen && (
                            <div className="absolute right-0 top-full mt-2 w-72 p-2 rounded-2xl bg-surface-950 border border-white/20 shadow-2xl backdrop-blur-2xl z-50 font-mono text-xs space-y-1">
                                <div className="px-2.5 py-1 text-[10px] uppercase font-bold text-slate-400 tracking-wider border-b border-white/10">
                                    Switch Real-Time Feed Provider
                                </div>
                                {FEED_PROVIDERS.map(p => (
                                    <button
                                        key={p.id}
                                        onClick={() => {
                                            setActiveProvider(p.id)
                                            setIsProviderMenuOpen(false)
                                        }}
                                        className={`w-full flex items-center justify-between p-2 rounded-xl text-left transition-all ${
                                            activeProvider === p.id
                                                ? 'bg-primary-500/20 border border-primary-500/40 text-white'
                                                : 'hover:bg-white/5 text-slate-300'
                                        }`}
                                    >
                                        <div>
                                            <div className="font-bold flex items-center gap-1.5">
                                                <span>{p.name}</span>
                                                {activeProvider === p.id && <span className="text-[9px] text-primary-400 font-bold">● ACTIVE</span>}
                                            </div>
                                            <div className="text-[10px] text-slate-400 font-normal">{p.description}</div>
                                        </div>
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                            p.latencyMs < 50 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                                        }`}>
                                            {p.latencyMs}ms
                                        </span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Column Layout Selector (1X Jumbotron, 2X Arena, 3X Balanced, 4X Compact) */}
                    <div className="flex items-center gap-1 bg-surface-950/80 p-1 rounded-xl border border-white/10 font-mono text-xs">
                        <button
                            onClick={() => setColumnCount(1)}
                            className={`p-1.5 rounded-lg transition-all ${
                                columnCount === 1 ? 'bg-primary-500 text-white shadow-md' : 'text-slate-400 hover:text-white'
                            }`}
                            title="1 Column (Theater / Jumbotron)"
                        >
                            <Square className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => setColumnCount(2)}
                            className={`p-1.5 rounded-lg transition-all ${
                                columnCount === 2 ? 'bg-primary-500 text-white shadow-md' : 'text-slate-400 hover:text-white'
                            }`}
                            title="2 Columns (Dual Arena - 2X Double Size)"
                        >
                            <Columns2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => setColumnCount(3)}
                            className={`p-1.5 rounded-lg transition-all ${
                                columnCount === 3 ? 'bg-primary-500 text-white shadow-md' : 'text-slate-400 hover:text-white'
                            }`}
                            title="3 Columns (Balanced 3x3)"
                        >
                            <Grid3X3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => setColumnCount(4)}
                            className={`p-1.5 rounded-lg transition-all ${
                                columnCount === 4 ? 'bg-primary-500 text-white shadow-md' : 'text-slate-400 hover:text-white'
                            }`}
                            title="4 Columns (Compact Grid)"
                        >
                            <LayoutGrid className="w-3.5 h-3.5" />
                        </button>
                    </div>

                    {/* Search Bar */}
                    <div className="relative">
                        <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                        <input
                            type="text"
                            placeholder="Filter teams..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            className="bg-surface-950/80 border border-white/10 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary-500 w-36 sm:w-44 font-mono"
                        />
                    </div>
                </div>
            </div>

            {/* Filter Ribbons: Sport Badges & Match States */}
            <div className="flex flex-wrap items-center justify-between gap-3">
                {/* Sport Filters */}
                <div className="flex items-center gap-1.5 bg-surface-950/80 p-1 rounded-xl border border-white/10 font-mono text-[11px]">
                    {(['all', 'mlb', 'nfl', 'nba', 'cfb'] as const).map(sport => (
                        <button
                            key={sport}
                            onClick={() => setSportFilter(sport)}
                            className={`px-3 py-1 rounded-lg font-bold uppercase transition-all ${
                                sportFilter === sport
                                    ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/25'
                                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            {sport}
                        </button>
                    ))}
                </div>

                {/* State Filters */}
                <div className="flex items-center gap-1 bg-surface-950/80 p-1 rounded-xl border border-white/10 font-mono text-[11px]">
                    {(['ALL', 'LIVE', 'UPCOMING', 'FINISHED'] as const).map(st => (
                        <button
                            key={st}
                            onClick={() => setStateFilter(st)}
                            className={`px-2.5 py-1 rounded-lg font-bold transition-all ${
                                stateFilter === st
                                    ? 'bg-surface-800 text-amber-400 border border-white/10'
                                    : 'text-slate-500 hover:text-slate-300'
                            }`}
                        >
                            {st}
                        </button>
                    ))}
                </div>
            </div>

            {/* Pinned Favorites Strip */}
            {pinnedMatches.length > 0 && (
                <div className="space-y-2 pb-2 border-b border-white/5">
                    <div className="flex items-center gap-1.5 text-[11px] font-mono text-amber-400 font-bold uppercase tracking-wider">
                        <Star className="w-3.5 h-3.5 fill-amber-400" />
                        <span>Pinned Matches ({pinnedMatches.length})</span>
                    </div>
                    <div className={`grid ${gridColsClass} gap-3.5`}>
                        {pinnedMatches.map(match => (
                            <TacticalMatchCard
                                key={`fav-${match.id}`}
                                match={match}
                                isFavorite={true}
                                onToggleFavorite={toggleFavorite}
                                onSelectMarket={handleMarketClick}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Main Scoreboard Grid */}
            <div className={`grid ${gridColsClass} gap-3.5`}>
                {filteredMatches.length === 0 ? (
                    <div className="col-span-full py-16 text-center text-slate-500 font-mono text-xs">
                        No matches found matching active filters.
                    </div>
                ) : (
                    filteredMatches.map(match => (
                        <TacticalMatchCard
                            key={match.id}
                            match={match}
                            isFavorite={favorites.includes(match.id)}
                            onToggleFavorite={toggleFavorite}
                            onSelectMarket={handleMarketClick}
                        />
                    ))
                )}
            </div>
        </div>
    )
}

function TacticalMatchCard({
    match,
    isFavorite,
    onToggleFavorite,
    onSelectMarket
}: {
    match: SportsMatch
    isFavorite: boolean
    onToggleFavorite: (id: string) => void
    onSelectMarket: (match: SportsMatch) => void
}) {
    const isLive = match.status === 'live'
    const isFinished = match.status === 'finished'
    const b = match.baseballSituation
    const f = match.footballSituation

    return (
        <div className="group relative rounded-3xl bg-surface-900/95 border border-white/10 hover:border-primary-500/50 p-6 sm:p-8 transition-all duration-300 shadow-2xl flex flex-col justify-between min-h-[460px] sm:min-h-[500px]">
            {/* Top Bar: League & Live Status */}
            <div className="flex items-center justify-between gap-3 mb-4 pb-3.5 border-b border-white/10 font-mono text-xs sm:text-sm">
                <div className="flex items-center gap-2.5">
                    <span className="px-3 py-1 rounded-xl bg-white/5 border border-white/15 text-white font-black text-xs sm:text-sm tracking-wider uppercase">
                        {match.leagueName}
                    </span>
                    {match.venue && (
                        <span className="hidden sm:inline text-slate-400 text-xs sm:text-sm font-medium truncate max-w-[220px]">
                            {match.venue}
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2.5">
                    {/* Status Pill */}
                    {isLive ? (
                        <span className="flex items-center gap-2 px-3.5 py-1 rounded-full bg-rose-500/20 border border-rose-500/40 text-rose-400 font-black text-xs sm:text-sm tracking-wider animate-pulse">
                            <span className="w-2 h-2 rounded-full bg-rose-400" />
                            {match.statusDetail}
                        </span>
                    ) : isFinished ? (
                        <span className="px-3 py-1 rounded-xl bg-slate-800 border border-white/10 text-slate-400 font-bold text-xs sm:text-sm">
                            {match.statusDetail}
                        </span>
                    ) : (
                        <span className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 font-bold text-xs sm:text-sm">
                            <Clock3 className="w-4 h-4" />
                            {match.statusDetail}
                        </span>
                    )}

                    {/* Favorite Heart Button */}
                    <button
                        onClick={e => {
                            e.stopPropagation()
                            onToggleFavorite(match.id)
                        }}
                        className={`p-2 rounded-xl transition-all ${
                            isFavorite
                                ? 'text-rose-400 bg-rose-500/20 shadow-md shadow-rose-500/20'
                                : 'text-slate-500 hover:text-rose-400 hover:bg-white/5'
                        }`}
                        title={isFavorite ? 'Remove from favorites' : 'Pin to favorites'}
                    >
                        <Heart className={`w-5 h-5 ${isFavorite ? 'fill-rose-400' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Score Center & Teams (Large Stadium Board Style) */}
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 sm:gap-6 my-4 py-2">
                {/* Home Team */}
                <div className="flex items-center justify-end gap-3 sm:gap-4 text-right">
                    <div className="min-w-0">
                        <div className="font-black text-white text-base sm:text-2xl truncate group-hover:text-primary-300 transition-colors tracking-tight">
                            {match.homeTeam.name}
                        </div>
                        {match.homeTeam.record && (
                            <div className="text-xs sm:text-sm font-mono text-slate-400 mt-1 font-semibold">
                                {match.homeTeam.record}
                            </div>
                        )}
                    </div>
                    <span
                        className="w-14 h-14 sm:w-20 sm:h-20 rounded-2xl sm:rounded-3xl flex items-center justify-center font-black font-display text-base sm:text-2xl text-white shrink-0 shadow-2xl border-2 border-white/20"
                        style={{ backgroundColor: match.homeTeam.badgeColor }}
                    >
                        {match.homeTeam.shortName}
                    </span>
                </div>

                {/* Score Numbers (Giant Stadium LED Display) */}
                <div className="px-4 sm:px-6 text-center min-w-[110px] sm:min-w-[150px]">
                    <div className={`font-display text-4xl sm:text-6xl md:text-7xl font-black tracking-tight leading-none ${isLive ? 'text-amber-400 drop-shadow-[0_0_25px_rgba(251,191,36,0.35)]' : 'text-white'}`}>
                        {match.score.home} <span className="text-slate-600 font-normal text-2xl sm:text-4xl align-middle">-</span> {match.score.away}
                    </div>
                    {isLive && (
                        <div className="text-xs font-mono font-bold text-amber-400 mt-2 uppercase tracking-widest flex items-center justify-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                            In Play
                        </div>
                    )}
                </div>

                {/* Away Team */}
                <div className="flex items-center justify-start gap-3 sm:gap-4 text-left">
                    <span
                        className="w-14 h-14 sm:w-20 sm:h-20 rounded-2xl sm:rounded-3xl flex items-center justify-center font-black font-display text-base sm:text-2xl text-white shrink-0 shadow-2xl border-2 border-white/20"
                        style={{ backgroundColor: match.awayTeam.badgeColor }}
                    >
                        {match.awayTeam.shortName}
                    </span>
                    <div className="min-w-0">
                        <div className="font-black text-white text-base sm:text-2xl truncate group-hover:text-primary-300 transition-colors tracking-tight">
                            {match.awayTeam.name}
                        </div>
                        {match.awayTeam.record && (
                            <div className="text-xs sm:text-sm font-mono text-slate-400 mt-1 font-semibold">
                                {match.awayTeam.record}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Deep Situational Telemetry: Outs, Strikes, Diamond, Pitchers (MLB) */}
            {isLive && b && (
                <div className="my-4 p-4 rounded-2xl bg-surface-950/90 border border-white/10 font-mono space-y-3">
                    <div className="flex items-center justify-between gap-4">
                        {/* Ball-Strike-Out Count */}
                        <div className="flex flex-wrap items-center gap-2.5">
                            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-surface-900 border border-white/10 text-xs sm:text-sm font-bold shadow-inner">
                                <span className="text-slate-400">COUNT:</span>
                                <span className="text-blue-400 font-black">{b.balls}B</span>
                                <span className="text-slate-600">-</span>
                                <span className="text-amber-400 font-black">{b.strikes}S</span>
                            </div>
                            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400 text-xs sm:text-sm font-black shadow-inner">
                                <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />
                                <span>{b.outs} {b.outs === 1 ? 'OUT' : 'OUTS'}</span>
                            </div>
                        </div>

                        {/* Base Diamond Graphic (Double Size: 48px) */}
                        <div className="relative w-12 h-12 flex items-center justify-center bg-black/50 rounded-2xl border border-white/10 shrink-0 p-1">
                            {/* Infield Baseline Diamond outline */}
                            <div className="absolute w-7 h-7 rotate-45 border border-dashed border-white/20" />
                            {/* 2nd Base (Top) */}
                            <span
                                title={b.runnerOnSecond ? "Runner on 2nd" : "2nd Base Empty"}
                                className={`absolute top-1.5 w-3.5 h-3.5 rotate-45 border transition-all ${
                                    b.runnerOnSecond
                                        ? 'bg-amber-400 border-amber-300 shadow-lg shadow-amber-400/50 scale-110'
                                        : 'bg-white/10 border-white/30'
                                }`}
                            />
                            {/* 3rd Base (Left) */}
                            <span
                                title={b.runnerOnThird ? "Runner on 3rd" : "3rd Base Empty"}
                                className={`absolute left-1.5 w-3.5 h-3.5 rotate-45 border transition-all ${
                                    b.runnerOnThird
                                        ? 'bg-amber-400 border-amber-300 shadow-lg shadow-amber-400/50 scale-110'
                                        : 'bg-white/10 border-white/30'
                                }`}
                            />
                            {/* 1st Base (Right) */}
                            <span
                                title={b.runnerOnFirst ? "Runner on 1st" : "1st Base Empty"}
                                className={`absolute right-1.5 w-3.5 h-3.5 rotate-45 border transition-all ${
                                    b.runnerOnFirst
                                        ? 'bg-amber-400 border-amber-300 shadow-lg shadow-amber-400/50 scale-110'
                                        : 'bg-white/10 border-white/30'
                                }`}
                            />
                            {/* Home Plate (Bottom indicator) */}
                            <span className="absolute bottom-1 w-2.5 h-2.5 rotate-45 bg-slate-500/50 border border-slate-400/40" />
                        </div>
                    </div>

                    {/* Pitcher & Batter Telemetry (Full 2-column tactical telemetry) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-slate-300 border-t border-white/10 pt-3 text-xs sm:text-sm">
                        {b.currentPitcher && (
                            <div className="flex items-center gap-2.5 bg-surface-900/80 p-2.5 rounded-xl border border-white/5">
                                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-black text-[11px] tracking-wider">
                                    PITCHER
                                </span>
                                <div className="truncate">
                                    <div className="font-bold text-white text-xs sm:text-sm truncate">{b.currentPitcher.name} ({b.currentPitcher.hand}HP)</div>
                                    <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                                        {b.currentPitcher.pitchCount}P • {b.currentPitcher.strikeouts ?? 0} Ks • {b.currentPitcher.era ?? '—'} ERA
                                    </div>
                                </div>
                            </div>
                        )}
                        {b.currentBatter && (
                            <div className="flex items-center gap-2.5 bg-surface-900/80 p-2.5 rounded-xl border border-white/5">
                                <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 font-black text-[11px] tracking-wider">
                                    AT BAT
                                </span>
                                <div className="truncate">
                                    <div className="font-bold text-white text-xs sm:text-sm truncate">{b.currentBatter.name}</div>
                                    <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                                        AVG {b.currentBatter.avg} • {b.currentBatter.hits ?? 0} for {b.currentBatter.atBats ?? 0} Today
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* NFL Down & Distance Telemetry */}
            {isLive && f && (
                <div className="my-3 p-3.5 rounded-2xl bg-surface-950/90 border border-white/10 font-mono text-xs sm:text-sm flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                        <span className="px-2.5 py-1 rounded-xl bg-amber-500/20 text-amber-400 font-black border border-amber-500/30 text-xs sm:text-sm">
                            {f.down}rd & {f.distance}
                        </span>
                        <span className="text-slate-400">Ball on:</span>
                        <span className="text-white font-black text-sm">{f.yardLine}</span>
                    </div>
                    {f.redZone && (
                        <span className="px-3 py-1 rounded-xl bg-rose-500/20 text-rose-400 font-black text-xs border border-rose-500/40 animate-pulse flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-rose-400" />
                            RED ZONE THREAT
                        </span>
                    )}
                </div>
            )}

            {/* Period Breakdown Segments */}
            {match.scoreSegments.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-2 my-2.5 font-mono text-xs">
                    {match.scoreSegments.map(seg => (
                        <span
                            key={seg.label}
                            className={`px-3 py-1 rounded-xl border ${
                                seg.active
                                    ? 'bg-amber-500/15 border-amber-500/40 text-amber-300 font-bold shadow-md shadow-amber-500/10'
                                    : 'bg-white/5 border-white/5 text-slate-400'
                            }`}
                        >
                            <span className="font-semibold text-slate-500 mr-1">{seg.label}:</span>
                            {seg.home}–{seg.away}
                        </span>
                    ))}
                </div>
            )}

            {/* Bottom Bar: Polymarket Probability & Quick Trade */}
            {match.impliedOdds && (
                <div
                    onClick={() => onSelectMarket(match)}
                    className="mt-4 pt-3.5 border-t border-white/10 space-y-2.5 cursor-pointer group-hover:bg-primary-500/5 p-3 rounded-2xl transition-all"
                >
                    <div className="flex items-center justify-between text-xs sm:text-sm font-mono">
                        <div className="flex items-center gap-2">
                            <TrendingUp className="w-4 h-4 text-emerald-400" />
                            <span className="text-slate-400">Polymarket Odds:</span>
                            <span className="font-black text-emerald-400">{match.impliedOdds.home}% {match.homeTeam.shortName}</span>
                            <span className="text-slate-600">vs</span>
                            <span className="font-black text-slate-300">{match.impliedOdds.away}% {match.awayTeam.shortName}</span>
                        </div>

                        <div className="flex items-center gap-1.5 font-bold text-primary-400 group-hover:underline">
                            <span>Trade Alpha</span>
                            <ExternalLink className="w-3.5 h-3.5" />
                        </div>
                    </div>

                    {/* Probability Meter */}
                    <div className="w-full h-2.5 rounded-full bg-white/10 overflow-hidden flex shadow-inner">
                        <div
                            className="h-full bg-emerald-500 transition-all duration-500"
                            style={{ width: `${match.impliedOdds.home}%` }}
                        />
                        <div
                            className="h-full bg-slate-600 transition-all duration-500"
                            style={{ width: `${match.impliedOdds.away}%` }}
                        />
                    </div>
                </div>
            )}
        </div>
    )
}

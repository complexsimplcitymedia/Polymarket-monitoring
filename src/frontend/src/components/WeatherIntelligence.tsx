import { useState } from 'react'
import {
    CloudSun,
    Calendar,
    Compass,
    Search,
    Layers,
    Sun,
    CheckCircle2,
    Sparkles,
    AlertTriangle,
    RefreshCw,
    Flame,
} from 'lucide-react'
import {
    useTrackedCities,
    useCityWeatherMatrix,
} from '../hooks/useScanners'

export function WeatherIntelligence() {
    const [selectedCityKey, setSelectedCityKey] = useState<string>('sf')
    const [customCityInput, setCustomCityInput] = useState<string>('')
    const [activeCityQuery, setActiveCityQuery] = useState<string>('sf')
    const [underdogOnly, setUnderdogOnly] = useState<boolean>(false)

    // Data Hooks
    const { data: trackedCities, isLoading: citiesLoading } = useTrackedCities()
    const {
        data: matrix,
        isLoading: matrixLoading,
        isFetching: matrixFetching,
        refetch: refetchMatrix,
    } = useCityWeatherMatrix(activeCityQuery)

    const handleSelectCity = (key: string) => {
        setSelectedCityKey(key)
        setActiveCityQuery(key)
        setCustomCityInput('')
    }

    const handleCustomSearch = (e: React.FormEvent) => {
        e.preventDefault()
        if (customCityInput.trim()) {
            setActiveCityQuery(customCityInput.trim())
            setSelectedCityKey('')
        }
    }

    const topPills = [
        { key: 'sf', label: 'San Francisco (KSFO)' },
        { key: 'la', label: 'Los Angeles (KLAX)' },
        { key: 'chicago', label: 'Chicago (KORD)' },
        { key: 'nyc', label: 'New York (KNYC)' },
        { key: 'atlanta', label: 'Atlanta (KATL)' },
        { key: 'miami', label: 'Miami (KMIA)' },
        { key: 'dallas', label: 'Dallas (KDFW)' },
        { key: 'phoenix', label: 'Phoenix (KPHX)' },
    ]

    return (
        <div className="space-y-6">
            {/* Header & City Selector */}
            <div className="glass-card rounded-2xl p-6 border border-white/10 space-y-5 bg-gradient-to-br from-surface-950/90 via-surface-900/80 to-surface-950/90 shadow-2xl">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2.5">
                            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                <CloudSun className="w-6 h-6" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                                    <span>Weather Intelligence & Climatology Matrix</span>
                                    <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                        Top 25 Automated Stations
                                    </span>
                                </h2>
                                <p className="text-xs text-surface-300 mt-0.5">
                                    NWP Physics Multi-Model • 10-Year Historical Ground Truth • Cloud & Overcast Dynamics • 2° Dutching Engine
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setUnderdogOnly(!underdogOnly)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all flex items-center gap-1.5 shadow-sm ${
                                underdogOnly
                                    ? 'bg-amber-500/30 text-amber-200 border-amber-500/50 shadow-amber-900/30'
                                    : 'bg-surface-800 text-surface-300 border-white/10 hover:text-white'
                            }`}
                        >
                            <Flame className={`w-3.5 h-3.5 ${underdogOnly ? 'text-amber-400 animate-pulse' : 'text-surface-400'}`} />
                            <span>{underdogOnly ? 'Underdog Mode: ACTIVE' : 'Underdog Mode'}</span>
                        </button>

                        <button
                            onClick={() => refetchMatrix()}
                            disabled={matrixFetching}
                            className="p-2 rounded-xl bg-surface-800 text-surface-300 hover:text-white border border-white/10 transition-all hover:bg-surface-700"
                            title="Refresh Forecast & Obs"
                        >
                            <RefreshCw className={`w-4 h-4 ${matrixFetching ? 'animate-spin text-cyan-400' : ''}`} />
                        </button>
                    </div>
                </div>

                {/* Quick-Select Pills */}
                <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                    <span className="text-[11px] font-mono text-surface-400 uppercase tracking-wider shrink-0 mr-1">
                        Top Markets:
                    </span>
                    {topPills.map((pill) => (
                        <button
                            key={pill.key}
                            onClick={() => handleSelectCity(pill.key)}
                            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-all ${
                                activeCityQuery === pill.key
                                    ? 'bg-cyan-500 text-surface-950 font-bold shadow-md shadow-cyan-500/20'
                                    : 'bg-surface-800/80 text-surface-300 hover:text-white hover:bg-surface-700 border border-white/5'
                            }`}
                        >
                            {pill.label}
                        </button>
                    ))}
                </div>

                {/* Dropdown & Custom Search Bar */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-1 border-t border-white/5">
                    <div className="md:col-span-6 flex items-center gap-2">
                        <label className="text-xs text-surface-400 shrink-0">Tracked City (25):</label>
                        <select
                            value={selectedCityKey}
                            onChange={(e) => handleSelectCity(e.target.value)}
                            className="flex-1 bg-surface-900 border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 font-medium"
                        >
                            {citiesLoading ? (
                                <option>Loading 25 cities...</option>
                            ) : (
                                trackedCities?.map((c) => (
                                    <option key={c.key} value={c.key}>
                                        {c.name} ({c.station})
                                    </option>
                                ))
                            )}
                        </select>
                    </div>

                    <form onSubmit={handleCustomSearch} className="md:col-span-6 flex items-center gap-2">
                        <div className="relative flex-1">
                            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
                            <input
                                type="text"
                                value={customCityInput}
                                onChange={(e) => setCustomCityInput(e.target.value)}
                                placeholder="Or type ANY global city (e.g. Honolulu, Tokyo, Paris)..."
                                className="w-full bg-surface-900 border border-white/10 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-surface-500 focus:outline-none focus:border-cyan-500"
                            />
                        </div>
                        <button
                            type="submit"
                            className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition-colors shrink-0 shadow-md"
                        >
                            Analyze City
                        </button>
                    </form>
                </div>
            </div>

            {/* Matrix Loading State */}
            {matrixLoading ? (
                <div className="p-16 text-center glass-card rounded-2xl border border-white/10 space-y-3">
                    <RefreshCw className="w-8 h-8 mx-auto animate-spin text-cyan-400" />
                    <p className="text-sm font-semibold text-white">Analyzing Meteorological & Climatological Datasets...</p>
                    <p className="text-xs text-surface-400">
                        Querying 10-year historical observations, cloud cover curves, ECMWF/GFS/ICON models, and Polymarket 2° brackets.
                    </p>
                </div>
            ) : !matrix ? (
                <div className="p-12 text-center glass-card rounded-2xl border border-white/10 text-surface-400">
                    No data returned for "{activeCityQuery}". Try picking from the 25 top tracked cities.
                </div>
            ) : (
                <div className="space-y-6">
                    {/* Live Overview Strip */}
                    <div className="glass-card rounded-2xl p-5 border border-white/10 bg-surface-900/60 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-2">
                                <h3 className="text-lg font-bold text-white">{matrix.city.name}</h3>
                                <span className="px-2 py-0.5 text-[11px] font-mono font-bold rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                    Station: {matrix.live_observation.station_id || matrix.city.station}
                                </span>
                                <span className="text-xs text-surface-400 font-mono">
                                    Date: {matrix.target_date}
                                </span>
                            </div>
                            <p className="text-xs text-surface-300 mt-1">
                                {matrix.live_observation.nws_forecast_discussion || 'Official meteorological station boundary conditions loaded.'}
                            </p>
                        </div>

                        <div className="flex items-center gap-4 self-end md:self-center shrink-0">
                            <div className="text-right">
                                <div className="text-[10px] text-surface-400 uppercase font-mono">Live Station Temp</div>
                                <div className="text-xl font-bold font-mono text-white">
                                    {matrix.live_observation.temp_f !== null ? `${matrix.live_observation.temp_f}°F` : 'N/A'}
                                </div>
                                <div className="text-[10px] text-surface-400">
                                    {matrix.live_observation.weather_text || 'Active Station'}
                                </div>
                            </div>
                            <div className="h-8 w-px bg-white/10" />
                            <div className="text-right">
                                <div className="text-[10px] text-cyan-400 uppercase font-mono font-semibold">Consensus Peak</div>
                                <div className="text-xl font-bold font-mono text-cyan-300">
                                    {matrix.consensus_peak_f}°F
                                </div>
                                <div className="text-[10px] text-surface-400">
                                    Spread: ±{matrix.multi_model_nwp.model_spread_f}°F
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 4 CORE ANALYTICAL CARDS */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* 1. 10-YEAR HISTORICAL CLIMATOLOGY */}
                        <div className="glass-card rounded-2xl p-5 border border-white/10 space-y-4 shadow-xl">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="p-2 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                        <Calendar className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-bold text-white">10-Year Historical Climatology</h4>
                                        <p className="text-[11px] text-surface-400">Ground-truth historical records for this calendar window</p>
                                    </div>
                                </div>
                                <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                    2015 – 2025
                                </span>
                            </div>

                            {/* Anomaly Gauge */}
                            <div className="p-3.5 rounded-xl bg-surface-900/80 border border-white/5 space-y-2">
                                <div className="flex justify-between items-center text-xs">
                                    <span className="text-surface-400">Atmospheric Anomaly Regime:</span>
                                    <span className="font-bold text-purple-300">{matrix.ten_year_climatology.anomaly_regime}</span>
                                </div>
                                <div className="flex justify-between items-center text-xs font-mono">
                                    <span className="text-surface-400">Anomaly Z-Score:</span>
                                    <span className="font-bold text-white">
                                        {matrix.ten_year_climatology.anomaly_z_score >= 0 ? `+${matrix.ten_year_climatology.anomaly_z_score}` : matrix.ten_year_climatology.anomaly_z_score}σ
                                    </span>
                                </div>
                            </div>

                            {/* Key Climatological Metrics */}
                            <div className="grid grid-cols-4 gap-2 text-center">
                                <div className="p-2 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">10-Yr Mean</div>
                                    <div className="text-sm font-bold font-mono text-white mt-0.5">
                                        {matrix.ten_year_climatology.mean_high_f}°F
                                    </div>
                                </div>
                                <div className="p-2 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">Std Dev</div>
                                    <div className="text-sm font-bold font-mono text-white mt-0.5">
                                        ±{matrix.ten_year_climatology.std_dev_f}°F
                                    </div>
                                </div>
                                <div className="p-2 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">10-Yr Low</div>
                                    <div className="text-sm font-bold font-mono text-blue-300 mt-0.5">
                                        {matrix.ten_year_climatology.min_high_f}°F
                                    </div>
                                </div>
                                <div className="p-2 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">10-Yr High</div>
                                    <div className="text-sm font-bold font-mono text-rose-300 mt-0.5">
                                        {matrix.ten_year_climatology.max_high_f}°F
                                    </div>
                                </div>
                            </div>

                            {/* Year-by-Year Historical Record Strip */}
                            {matrix.ten_year_climatology.historical_records && matrix.ten_year_climatology.historical_records.length > 0 && (
                                <div className="space-y-1.5 pt-1">
                                    <div className="text-[11px] font-mono text-surface-400 uppercase tracking-wider">
                                        Year-by-Year Observed Highs:
                                    </div>
                                    <div className="grid grid-cols-5 gap-1.5">
                                        {matrix.ten_year_climatology.historical_records.slice(-10).map((rec, rIdx) => (
                                            <div key={rIdx} className="p-1.5 rounded-lg bg-surface-900/40 border border-white/5 text-center">
                                                <div className="text-[10px] text-surface-400">{rec.year}</div>
                                                <div className="text-xs font-bold font-mono text-white">{rec.high}°F</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 2. CLOUD PATTERNS & OVERCAST MATRIX */}
                        <div className="glass-card rounded-2xl p-5 border border-white/10 space-y-4 shadow-xl">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="p-2 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                        <Sun className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-bold text-white">Cloud Cover & Overcast Matrix</h4>
                                        <p className="text-[11px] text-surface-400">Daylight solar insolation & cloud boundary dynamics</p>
                                    </div>
                                </div>
                                <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded-full border ${
                                    matrix.cloud_and_overcast_matrix.mean_daylight_cloud_cover_pct >= 70
                                        ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                                        : matrix.cloud_and_overcast_matrix.mean_daylight_cloud_cover_pct <= 30
                                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                }`}>
                                    {matrix.cloud_and_overcast_matrix.overcast_regime}
                                </span>
                            </div>

                            {/* Cloud Metrics */}
                            <div className="grid grid-cols-3 gap-2 text-center">
                                <div className="p-2.5 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">Daylight Mean</div>
                                    <div className="text-base font-bold font-mono text-white mt-0.5">
                                        {matrix.cloud_and_overcast_matrix.mean_daylight_cloud_cover_pct}%
                                    </div>
                                </div>
                                <div className="p-2.5 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">Morning (8-12)</div>
                                    <div className="text-base font-bold font-mono text-cyan-300 mt-0.5">
                                        {matrix.cloud_and_overcast_matrix.morning_cloud_cover_pct}%
                                    </div>
                                </div>
                                <div className="p-2.5 rounded-xl bg-surface-900/60 border border-white/5">
                                    <div className="text-[10px] text-surface-400 uppercase font-mono">Afternoon (12-17)</div>
                                    <div className="text-base font-bold font-mono text-amber-300 mt-0.5">
                                        {matrix.cloud_and_overcast_matrix.afternoon_cloud_cover_pct}%
                                    </div>
                                </div>
                            </div>

                            {/* Insolation Impact Thesis */}
                            <div className="p-3.5 rounded-xl bg-surface-900/80 border border-white/5 text-xs space-y-1">
                                <span className="font-semibold text-amber-300 uppercase tracking-wider text-[10px] block font-mono">
                                    Solar Heating Impact Analysis:
                                </span>
                                <p className="text-surface-200 leading-relaxed">
                                    {matrix.cloud_and_overcast_matrix.insolation_impact}
                                </p>
                            </div>

                            {/* Hourly Daylight Cloud Cover Timeline */}
                            <div className="space-y-1.5 pt-1">
                                <div className="text-[11px] font-mono text-surface-400 uppercase tracking-wider">
                                    Daylight Cloud Cover Timeline (06:00 – 20:00):
                                </div>
                                <div className="grid grid-cols-7 sm:grid-cols-8 gap-1">
                                    {matrix.cloud_and_overcast_matrix.hourly_curve.slice(0, 15).map((hp, hIdx) => (
                                        <div
                                            key={hIdx}
                                            className="p-1.5 rounded-lg bg-surface-900/40 border border-white/5 text-center flex flex-col justify-between"
                                            title={`${hp.time} - ${hp.cloud_cover_pct}% Cloud Cover, ${hp.temp_f ?? 'N/A'}°F`}
                                        >
                                            <div className="text-[9px] text-surface-400 font-mono">{hp.time}</div>
                                            <div className={`text-[10px] font-bold font-mono my-0.5 ${
                                                hp.cloud_cover_pct >= 80 ? 'text-blue-400' : hp.cloud_cover_pct >= 40 ? 'text-surface-300' : 'text-amber-300'
                                            }`}>
                                                {hp.cloud_cover_pct}%
                                            </div>
                                            <div className="text-[9px] font-mono text-surface-400">{hp.temp_f ?? ''}°</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* 3. MULTI-MODEL NWP CONSENSUS */}
                        <div className="glass-card rounded-2xl p-5 border border-white/10 space-y-4 shadow-xl">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                        <Compass className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-bold text-white">Multi-Model NWP Consensus</h4>
                                        <p className="text-[11px] text-surface-400">High-resolution numerical weather prediction models</p>
                                    </div>
                                </div>
                                <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                    Consensus: {matrix.multi_model_nwp.consensus_mean_f}°F
                                </span>
                            </div>

                            {/* Model High Comparison Bars */}
                            <div className="space-y-2.5 pt-1">
                                {Object.entries(matrix.multi_model_nwp.models).map(([mName, mVal]) => (
                                    <div key={mName} className="space-y-1">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="font-mono text-surface-300 uppercase">
                                                {mName.replace('_seamless', '').replace('_ifs025', '')}
                                            </span>
                                            <span className="font-mono font-bold text-white">{mVal}°F</span>
                                        </div>
                                        <div className="w-full h-1.5 rounded-full bg-surface-800 overflow-hidden">
                                            <div
                                                className="h-full bg-gradient-to-r from-cyan-500 to-primary-500 rounded-full"
                                                style={{ width: `${Math.min(100, Math.max(10, ((mVal - 50) / 50) * 100))}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}

                                {matrix.live_observation.nws_forecast_high && (
                                    <div className="space-y-1 pt-1 border-t border-white/5">
                                        <div className="flex justify-between items-center text-xs">
                                            <span className="font-mono text-emerald-400 font-bold uppercase">
                                                NWS Official (Human Forecaster)
                                            </span>
                                            <span className="font-mono font-bold text-emerald-300">
                                                {matrix.live_observation.nws_forecast_high}°F
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Live Station Metrics */}
                            <div className="p-3 rounded-xl bg-surface-900/60 border border-white/5 grid grid-cols-3 gap-2 text-center text-xs font-mono">
                                <div>
                                    <span className="text-[10px] text-surface-400 block uppercase">Humidity</span>
                                    <span className="text-white font-bold">{matrix.live_observation.humidity_pct ?? 'N/A'}%</span>
                                </div>
                                <div>
                                    <span className="text-[10px] text-surface-400 block uppercase">Dew Point</span>
                                    <span className="text-white font-bold">{matrix.live_observation.dew_f ?? 'N/A'}°F</span>
                                </div>
                                <div>
                                    <span className="text-[10px] text-surface-400 block uppercase">Wind</span>
                                    <span className="text-white font-bold">{matrix.live_observation.wind_mph ?? 0} mph</span>
                                </div>
                            </div>
                        </div>

                        {/* 4. POLYMARKET 2-DEGREE BRACKET & HEDGE CALCULATOR */}
                        <div className="glass-card rounded-2xl p-5 border border-white/10 space-y-4 shadow-xl">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                        <Layers className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-bold text-white">2° Polymarket Bracket & Hedge Matrix</h4>
                                        <p className="text-[11px] text-surface-400">Odd-Even bracket odds & Dutching capital split</p>
                                    </div>
                                </div>
                                <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                    Dutch Win: {matrix.polymarket_bracket_matrix.dutched_win_prob_pct}%
                                </span>
                            </div>

                            {/* Primary & Hedge Duo */}
                            <div className="grid grid-cols-2 gap-3">
                                {matrix.polymarket_bracket_matrix.primary_bracket && (
                                    <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/40 space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[10px] font-bold font-mono text-emerald-400 uppercase tracking-wider">
                                                Primary Target (#1)
                                            </span>
                                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                                        </div>
                                        <div className="text-lg font-bold font-mono text-white">
                                            {matrix.polymarket_bracket_matrix.primary_bracket.bracket}
                                        </div>
                                        <div className="text-xs font-mono font-bold text-emerald-300">
                                            {matrix.polymarket_bracket_matrix.primary_bracket.probability.toFixed(1)}% True Prob
                                        </div>
                                    </div>
                                )}

                                {matrix.polymarket_bracket_matrix.hedge_bracket && (
                                    <div className="p-3 rounded-xl bg-cyan-950/30 border border-cyan-500/40 space-y-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[10px] font-bold font-mono text-cyan-400 uppercase tracking-wider">
                                                Recommended Hedge (#2)
                                            </span>
                                            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                                        </div>
                                        <div className="text-lg font-bold font-mono text-white">
                                            {matrix.polymarket_bracket_matrix.hedge_bracket.bracket}
                                        </div>
                                        <div className="text-xs font-mono font-bold text-cyan-300">
                                            {matrix.polymarket_bracket_matrix.hedge_bracket.probability.toFixed(1)}% True Prob
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Dutch Capital Allocation Strategy */}
                            <div className="p-3 rounded-xl bg-surface-900/80 border border-white/5 text-xs space-y-1">
                                <span className="font-semibold text-emerald-400 uppercase tracking-wider text-[10px] font-mono block">
                                    Optimal Capital Allocation (Dutching):
                                </span>
                                <p className="text-surface-200 font-mono">
                                    {matrix.polymarket_bracket_matrix.recommended_capital_split}
                                </p>
                                <p className="text-[11px] text-surface-400">
                                    Guarantees a profitable payout if the peak lands within the combined 4° physical window.
                                </p>
                            </div>

                            {/* Trap to Fade Alert */}
                            {matrix.polymarket_bracket_matrix.trap_to_fade && (
                                <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-500/30 text-xs flex items-start gap-2.5">
                                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                                    <div>
                                        <span className="font-bold text-rose-300 font-mono block">
                                            TRAP TO FADE: {matrix.polymarket_bracket_matrix.trap_to_fade.bracket} ({matrix.polymarket_bracket_matrix.trap_to_fade.probability.toFixed(1)}% Prob)
                                        </span>
                                        <p className="text-[11px] text-surface-300 mt-0.5">
                                            {matrix.polymarket_bracket_matrix.trap_to_fade.reason}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Full Bracket Odds Table */}
                            <div className="space-y-1.5 pt-1">
                                <div className="text-[11px] font-mono text-surface-400 uppercase tracking-wider">
                                    All 2-Degree Brackets Probability Distribution:
                                </div>
                                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                                    {matrix.polymarket_bracket_matrix.brackets.map((b) => (
                                        <div
                                            key={b.bracket}
                                            className={`p-2 rounded-lg border text-center transition-all ${
                                                b.rank === 1
                                                    ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200 font-bold'
                                                    : b.rank === 2
                                                    ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-200 font-bold'
                                                    : 'bg-surface-900/40 border-white/5 text-surface-400'
                                            }`}
                                        >
                                            <div className="text-[10px] font-mono text-surface-400">Rank #{b.rank}</div>
                                            <div className="text-xs font-mono text-white font-bold">{b.bracket}</div>
                                            <div className="text-[11px] font-mono">{b.probability.toFixed(1)}%</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

// Floating watch window: the Architect's tablet (MLB app) streamed by noVNC, floating over the app.
// Position/size persist in localStorage. Game-aware two ways:
//   1. selected market is a named game        -> "on card"
//   2. any OPEN PORTFOLIO position has a live game leg -> "in your portfolio" (green, auto-reopens)
// Dockable: fills the unused right-side space next to the account column (1400px column in a wide browser).
import { useCallback, useEffect, useRef, useState } from 'react'
import { useMarketStore } from '../stores/marketStore'
import { marketSides } from '../utils/sides'
import { useAccount } from '../hooks/useAccount'

// Watch feed (Architect-supplied): the tablet's own droidVNC-NG noVNC web client on 108:5800 — no VM4 bridge.
const WATCH_URL = 'http://100.110.82.108:5800/vnc.html?autoconnect=true&show_dot=true&host=100.110.82.108&port=5900'

const STORE_KEY = 'wolf-watch-window'

interface Box {
    x: number
    y: number
    w: number
    h: number
    min: boolean
    hidden: boolean
    dock?: boolean | null
}

const DEFAULT_BOX: Box = { x: 24, y: 96, w: 420, h: 300, min: false, hidden: false, dock: null }

function loadBox(): Box {
    try {
        const raw = localStorage.getItem(STORE_KEY)
        if (raw) return { ...DEFAULT_BOX, ...JSON.parse(raw), hidden: false } // hide is session-only: the window always comes back
    } catch { /* fall through */ }
    return { ...DEFAULT_BOX, x: Math.max(24, window.innerWidth - 468), y: Math.max(24, window.innerHeight - 404) }
}

/** First live game from the portfolio's open legs, else the selected market's game title. */
function useOnCardGame(): { title: string | null; live: boolean } {
    const { selectedMarket } = useMarketStore()
    const { data: account } = useAccount()

    for (const pos of account?.open_positions?.items ?? []) {
        const leg = pos.legs.find((l) => l.live?.state === 'in')
        if (leg) return { title: leg.title || pos.title || pos.slug, live: true }
    }
    const fromMarket = selectedMarket && marketSides(selectedMarket).named ? selectedMarket.title : null
    return { title: fromMarket, live: false }
}

/** Game-aware floating noVNC player. Mounted once in App, always on top; docks into the right void. */
export default function FloatingWatch() {
    const game = useOnCardGame()
    const [box, setBox] = useState<Box>(() => loadBox())
    const [reloadKey, setReloadKey] = useState(0)
    const drag = useRef<{ mode: 'move' | 'resize'; dx: number; dy: number } | null>(null)
    const [rightVoid, setRightVoid] = useState(0)

    const save = useCallback((b: Box) => {
        setBox(b)
        try { localStorage.setItem(STORE_KEY, JSON.stringify(b)) } catch { /* private mode */ }
    }, [])

    // Measure the unused right margin: window minus the app's centered 1400px content column.
    useEffect(() => {
        const measure = () => setRightVoid(Math.max(0, (window.innerWidth - 1400) / 2 - 12))
        measure()
        window.addEventListener('resize', measure)
        return () => window.removeEventListener('resize', measure)
    }, [])

    useEffect(() => {
        const onMove = (e: PointerEvent) => {
            const d = drag.current
            if (!d) return
            e.preventDefault()
            if (d.mode === 'move') {
                save({ ...box, dock: false, x: Math.max(0, e.clientX - d.dx), y: Math.max(0, e.clientY - d.dy) })
            } else {
                save({ ...box, dock: false, w: Math.max(320, e.clientX - box.x), h: Math.max(240, e.clientY - box.y) })
            }
        }
        const onUp = () => { drag.current = null }
        window.addEventListener('pointermove', onMove, { passive: false })
        window.addEventListener('pointerup', onUp)
        return () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp) }
    }, [box, save])

    // Auto-populate: a live game on the card (or in the portfolio) reopens the window docked, minimized
    useEffect(() => {
        if (game.title && box.hidden) save({ ...loadBox(), hidden: false, dock: true, min: true })
    }, [game.title, box.hidden, save])

    if (box.hidden) return null

    const docked = !!box.dock && rightVoid >= 380
    const geo = docked
        ? { left: window.innerWidth - rightVoid + 6, top: 150, width: rightVoid - 24, height: window.innerHeight - 210 }
        : { left: box.x, top: box.y, width: box.min ? 240 : box.w, height: box.min ? 40 : box.h }

    const title = game.title ?? 'no game in portfolio'

    return (
        <div className="fixed z-[70]" style={geo}>
            <div className={`glass-card border border-white/15 shadow-2xl rounded-xl overflow-hidden h-full flex flex-col ${box.min ? 'backdrop-blur-md bg-surface-950/95' : ''}`}>
                {/* Titlebar */}
                <div
                    className="flex items-center gap-2 px-2 h-10 shrink-0 bg-surface-950/95 border-b border-white/10 cursor-grab active:cursor-grabbing select-none"
                    onPointerDown={(e) => {
                        if (box.min || docked) return
                        drag.current = { mode: 'move', dx: e.clientX - box.x, dy: e.clientY - box.y }
                    }}
                >
                    <span className={`relative flex shrink-0 h-2 w-2 ${game.title ? '' : 'opacity-40'}`}>
                        {game.live && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />}
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                    </span>
                    <span className="text-[11px] font-mono truncate flex-1 min-w-0" title={title}>
                        <span className="text-slate-500">WATCH·</span>
                        <span className={game.title ? 'text-emerald-300 font-semibold' : 'text-slate-400'}>{title}</span>
                        {game.live && <span className="ml-1.5 text-[10px] text-amber-300 shrink-0">in your portfolio</span>}
                    </span>
                    <button
                        type="button"
                        title={docked ? 'Undock (float anywhere)' : 'Dock into the empty right-side browser space'}
                        onClick={() => save({ ...box, dock: !docked })}
                        className="px-1.5 text-slate-400 hover:text-white text-xs"
                    >
                        {docked ? '⇤' : '⇥'}
                    </button>
                    <button
                        type="button"
                        title="Minimize / Expand"
                        onClick={() => save({ ...box, min: !box.min })}
                        className="px-1.5 text-slate-400 hover:text-white text-sm leading-none"
                    >
                        {box.min ? '▣' : '▁'}
                    </button>
                    <button
                        type="button"
                        title="Reload stream"
                        onClick={() => { setReloadKey((k) => k + 1); if (box.min) save({ ...box, min: false }) }}
                        className="px-1.5 text-slate-400 hover:text-white text-xs"
                    >
                        ⟳
                    </button>
                    <button
                        type="button"
                        title="Hide — a live portfolio game or a game on the card brings it back"
                        onClick={() => save({ ...box, hidden: true })}
                        className="px-1.5 text-slate-400 hover:text-rose-400 text-sm leading-none"
                    >
                        ✕
                    </button>
                </div>

                {!box.min && (
                    <>
                        <iframe
                            key={reloadKey}
                            src={WATCH_URL}
                            title="Watch: tablet MLB feed"
                            allow="autoplay; fullscreen; picture-in-picture"
                            className="flex-1 w-full bg-black/70 min-h-0"
                        />
                        <div className="flex items-center justify-between px-2 h-7 shrink-0 bg-surface-950/95 border-t border-white/10 text-[10px] font-mono">
                            <a
                                href="https://www.mlb.com/tv"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-500 hover:text-emerald-300 transition-colors truncate"
                            >
                                open on tablet ↗
                            </a>
                            <span className={game.live ? 'text-emerald-400' : game.title ? 'text-slate-400' : 'text-slate-600'}>
                                {game.live ? 'LIVE · in portfolio' : game.title ? 'on card' : 'idle'}
                            </span>
                        </div>
                        {!docked && (
                            <div
                                className="absolute right-0 bottom-0 w-4 h-4 cursor-nwse-resize"
                                onPointerDown={(e) => {
                                    e.stopPropagation()
                                    drag.current = { mode: 'resize', dx: 0, dy: 0 }
                                }}
                            />
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

/** Reopen affordance for the top bar, for when the window is hidden. */
export function WatchReopenButton() {
    return (
        <button
            type="button"
            title="Show the watch window (docks right if there's room)"
            onClick={() => {
                try {
                    const b = loadBox()
                    localStorage.setItem(STORE_KEY, JSON.stringify({ ...b, hidden: false, dock: true, min: false }))
                } catch { /* ignore */ }
                window.dispatchEvent(new CustomEvent('wolf-watch-show'))
            }}
            className="px-2.5 py-1.5 rounded-xl bg-surface-900/90 hover:bg-emerald-500/20 text-slate-300 hover:text-emerald-300 border border-white/10 transition-colors flex items-center gap-1.5 text-xs font-bold font-display"
        >
            ▶ Watch
        </button>
    )
}
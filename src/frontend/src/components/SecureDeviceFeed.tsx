import { ExternalLink, LockKeyhole, Radio, ShieldCheck } from 'lucide-react'

const SOURCE_VNC_URL =
    'http://100.110.82.108:5800/vnc.html?autoconnect=true&show_dot=true&host=100.110.82.108&port=5900'

function getSecureVncUrl(): string {
    const url = new URL('/vnc/vnc.html', window.location.origin)
    const securePort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
    url.searchParams.set('autoconnect', 'true')
    url.searchParams.set('show_dot', 'true')
    url.searchParams.set('encrypt', 'true')
    url.searchParams.set('host', window.location.hostname)
    url.searchParams.set('port', securePort)
    url.searchParams.set('path', 'vnc/websockify')
    return url.toString()
}

export function SecureDeviceFeed() {
    const secureVncUrl = getSecureVncUrl()
    const isHttps = window.location.protocol === 'https:'

    return (
        <section className="glass-card rounded-2xl border border-emerald-400/20 shadow-2xl overflow-hidden">
            <div className="flex flex-col gap-4 border-b border-white/10 p-4 sm:flex-row sm:items-start sm:justify-between lg:p-6">
                <div>
                    <div className="mb-2 flex items-center gap-2">
                        <Radio className="h-5 w-5 text-rose-400" />
                        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-rose-300">
                            Live device feed
                        </span>
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                            <LockKeyhole className="h-3 w-3" />
                            {isHttps ? 'HTTPS / WSS' : 'HTTPS required'}
                        </span>
                    </div>
                    <h2 className="text-xl font-black tracking-tight text-white sm:text-2xl">
                        Secure Device Viewer
                    </h2>
                    <p className="mt-1 max-w-2xl text-sm text-slate-400">
                        The original device link remains the source target. This view routes the noVNC page and WebSocket through the current HTTPS origin.
                    </p>
                </div>
                <a
                    href={secureVncUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-bold text-emerald-200 transition-colors hover:bg-emerald-400/20"
                >
                    <ExternalLink className="h-4 w-4" />
                    Open secure viewer
                </a>
            </div>

            <div className="relative aspect-video min-h-[520px] bg-slate-950">
                <iframe
                    title="Secure live device feed"
                    src={secureVncUrl}
                    className="absolute inset-0 h-full w-full border-0"
                    allow="fullscreen; clipboard-read; clipboard-write"
                    allowFullScreen
                    sandbox="allow-forms allow-modals allow-pointer-lock allow-same-origin allow-scripts"
                />
            </div>

            <div className="flex flex-col gap-3 border-t border-white/10 bg-slate-950/60 p-4 text-xs sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-2 text-slate-400">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    <span>
                        Secure mode uses HTTPS for the page and WSS for the VNC tunnel when the dashboard is served over HTTPS.
                    </span>
                </div>
                <a
                    href={SOURCE_VNC_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-[10px] text-slate-500 underline decoration-slate-700 underline-offset-2 hover:text-slate-300"
                >
                    View original source link
                </a>
            </div>
        </section>
    )
}

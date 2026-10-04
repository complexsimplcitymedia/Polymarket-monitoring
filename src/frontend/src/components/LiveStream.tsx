import { X } from 'lucide-react'
import { useMarketStore } from '../stores/marketStore'

export default function LiveStream() {
    const { streamUrl, setStreamUrl } = useMarketStore()
    if (!streamUrl) return null

    return (
        <div className="fixed inset-0 z-[60] bg-[#020617]">
            <button
                onClick={() => setStreamUrl(null)}
                className="absolute top-3 right-3 z-[70] p-2 rounded-lg bg-surface-900/90 border border-white/20 text-white hover:bg-red-500/30 transition"
            >
                <X className="w-5 h-5" />
            </button>
            <iframe
                src={streamUrl}
                className="w-full h-full border-0"
                allow="fullscreen"
                title="MLB Stream"
            />
        </div>
    )
}

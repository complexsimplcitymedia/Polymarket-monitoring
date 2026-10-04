import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bot, Send } from 'lucide-react'

interface AiStatus {
    configured: boolean
}

interface AiGame {
    league: string
    game_id: string
    title: string
    detail: string | null
}

interface AiAnswer {
    answer: string
    model: string
    context_chars: number
}

async function ask(body: { question: string; game_id: string | null; model: string }): Promise<AiAnswer> {
    const response = await fetch('/api/ai/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data.detail ?? 'The AI did not answer')
    return data
}

export default function AiPanel() {
    const [question, setQuestion] = useState('')
    const [gameId, setGameId] = useState<string>('')
    const [model, setModel] = useState<string>(() => {
        try {
            return localStorage.getItem('ai-model') ?? ''
        } catch {
            return ''
        }
    })

    const status = useQuery<AiStatus>({
        queryKey: ['ai-status'],
        queryFn: async () => (await fetch('/api/ai/status')).json(),
        staleTime: 60000,
    })
    const games = useQuery<AiGame[]>({
        queryKey: ['ai-games'],
        queryFn: async () => (await fetch('/api/ai/games')).json(),
        refetchInterval: 30000,
    })
    const models = useQuery<string[]>({
        queryKey: ['ai-models'],
        queryFn: async () => {
            const response = await fetch('/api/ai/models')
            if (!response.ok) throw new Error('models')
            return response.json()
        },
        enabled: status.data?.configured === true,
        staleTime: 600000,
    })
    const mutation = useMutation({ mutationFn: ask })

    const chooseModel = (value: string) => {
        setModel(value)
        try {
            localStorage.setItem('ai-model', value)
        } catch {
            /* a private window just forgets the choice */
        }
    }

    const submit = () => {
        if (!question.trim() || !model.trim() || mutation.isPending) return
        mutation.mutate({ question: question.trim(), game_id: gameId || null, model: model.trim() })
    }

    return (
        <div className="max-w-3xl mx-auto p-4 space-y-4">
            <div className="flex items-center gap-2 text-white">
                <Bot className="w-5 h-5 text-primary-400" />
                <h2 className="text-lg font-bold font-display">AI</h2>
                {status.data && !status.data.configured && (
                    <span className="text-xs text-amber-400">Off: set NANOGPT_API_KEY in .env</span>
                )}
            </div>

            <div className="glass-card p-4 space-y-3 rounded-xl border border-white/10 bg-surface-900/60">
                <div className="flex flex-wrap gap-2 items-center">
                    <select
                        value={gameId}
                        onChange={(e) => setGameId(e.target.value)}
                        className="bg-surface-900 border border-white/15 rounded-lg px-3 py-1.5 text-sm text-white"
                    >
                        <option value="">All live games</option>
                        {(games.data ?? []).map((g) => (
                            <option key={`${g.league}-${g.game_id}`} value={g.game_id}>
                                {g.league.toUpperCase()} {g.title}
                            </option>
                        ))}
                    </select>
                    <input
                        list="ai-model-list"
                        value={model}
                        onChange={(e) => chooseModel(e.target.value)}
                        placeholder={models.isLoading ? 'Loading models…' : 'Model (type or pick)'}
                        className="flex-1 min-w-[14rem] bg-surface-900 border border-white/15 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500"
                    />
                    <datalist id="ai-model-list">
                        {(models.data ?? []).map((id) => (
                            <option key={id} value={id} />
                        ))}
                    </datalist>
                </div>

                <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
                    }}
                    rows={3}
                    placeholder="Ask about the live games: what just happened, did the price react, what looks off?"
                    className="w-full bg-surface-900 border border-white/15 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500"
                />
                <button
                    onClick={submit}
                    disabled={!question.trim() || !model.trim() || mutation.isPending}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-primary-500/30 border border-primary-500/50 text-white text-sm font-bold disabled:opacity-40"
                >
                    <Send className="w-4 h-4" />
                    {mutation.isPending ? 'Thinking…' : 'Ask'}
                </button>
            </div>

            {mutation.isError && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
                    {(mutation.error as Error).message}
                </div>
            )}
            {mutation.data && (
                <div className="rounded-xl border border-white/10 bg-surface-900/60 p-4">
                    <div className="whitespace-pre-wrap text-sm text-slate-100">{mutation.data.answer}</div>
                    <div className="mt-3 text-[11px] text-slate-500">{mutation.data.model}</div>
                </div>
            )}
        </div>
    )
}

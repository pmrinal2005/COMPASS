'use client'

import { useEffect, useState } from 'react'
import { Columns2, Compass, Square, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { api, hasBackend, type Health } from '@/lib/api'
import type { Lens } from '@/lib/types'
import type { BackendMode } from '@/lib/useSession'
import { CommandCenter } from '@/components/CommandCenter'
import { cn } from '@/lib/utils'

export default function Page() {
  const [lens, setLens] = useState<Lens>('go')
  const [split, setSplit] = useState(false)
  const [backend, setBackend] = useState<BackendMode>(hasBackend() ? 'checking' : 'offline')
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    if (!hasBackend()) return
    let alive = true
    // Render free tier cold-starts in up to ~60s: this request also warms it up.
    const ping = async (attempt = 0) => {
      try {
        const h = await api.health(attempt === 0 ? 8000 : 25000)
        if (!alive) return
        setHealth(h)
        setBackend('live')
      } catch {
        if (!alive) return
        if (attempt < 3) setTimeout(() => ping(attempt + 1), 4000)
        else setBackend('offline')
      }
    }
    ping()
    return () => {
      alive = false
    }
  }, [])

  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 grid-bg" />
      <div className="pointer-events-none fixed -left-40 -top-40 -z-10 h-[520px] w-[520px] animate-aurora rounded-full bg-violet-600/20 blur-[120px]" />
      <div className="pointer-events-none fixed -right-40 top-40 -z-10 h-[480px] w-[480px] animate-aurora rounded-full bg-cyan-500/10 blur-[120px]" />

      <header className="sticky top-0 z-20 border-b border-white/5 bg-ink-950/70 backdrop-blur-xl" id="top-bar">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-lg shadow-violet-500/30">
              <Compass size={17} />
            </span>
            <div>
              <h1 className="text-sm font-extrabold tracking-tight"><span className="shimmer-text">COMPASS</span> <span className="text-slate-400">Agent Command Center</span></h1>
              <p className="text-[10px] text-slate-500">One decision engine, infinite verticals · Plan → Search → Compare → Act</p>
            </div>
          </div>

          <nav className="ml-auto flex items-center gap-2" aria-label="lens controls">
            {!split && (
              <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-0.5" role="tablist" id="lens-toggle">
                {(['go', 'pro'] as Lens[]).map((l) => (
                  <button key={l} role="tab" aria-selected={lens === l} onClick={() => setLens(l)}
                    className={cn('rounded-lg px-3 py-1 text-xs font-bold transition', lens === l ? (l === 'go' ? 'bg-cyan-400 text-ink-950' : 'bg-amber-300 text-ink-950') : 'text-slate-400 hover:text-white')}>
                    {l === 'go' ? 'Go · casual' : 'Pro · enterprise'}
                  </button>
                ))}
              </div>
            )}
            <button className="btn-ghost" onClick={() => setSplit((v) => !v)} id="split-toggle" title="Split-screen: both lenses on the same backend">
              {split ? <Square size={13} /> : <Columns2 size={13} />} {split ? 'Single' : 'Split-screen'}
            </button>
            <BackendBadge mode={backend} health={health} />
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] px-4 py-4">
        {split ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <CommandCenter key="go" lens="go" backend={backend} compact />
            <CommandCenter key="pro" lens="pro" backend={backend} compact />
          </div>
        ) : (
          <CommandCenter key={lens} lens={lens} backend={backend} />
        )}
        <footer className="mt-8 pb-6 text-center text-[10.5px] text-slate-600">
          SerpApi async fan-out · LangGraph agents · Supabase pgvector hybrid RAG · Upstash dedupe · Langfuse traces · HITL actions.
          {backend !== 'live' && ' Running the pre-cached Demo Mode recordings (no backend connected).'}
        </footer>
      </div>
    </main>
  )
}

function BackendBadge({ mode, health }: { mode: BackendMode; health: Health | null }) {
  if (mode === 'checking')
    return <span className="chip"><Loader2 size={11} className="animate-spin" /> waking backend…</span>
  if (mode === 'offline')
    return <span className="chip text-amber-200" title="Set NEXT_PUBLIC_API_URL to a running backend"><WifiOff size={11} /> offline demo</span>
  const i = health?.integrations || {}
  const live = Object.entries(i).filter(([k, v]) => k !== 'serpapi' && v === true).map(([k]) => k)
  return (
    <span className="chip text-emerald-200" title={`integrations: ${live.join(', ') || 'none'} · llm ${health?.llm} · store ${health?.store} · cache ${health?.cache?.backend}`}>
      <Wifi size={11} /> backend · serpapi {health?.demo_mode ? 'demo' : 'live'}
    </span>
  )
}

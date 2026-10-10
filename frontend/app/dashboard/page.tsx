'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, BookOpen, Columns2, Compass, Square, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { api, API_URL, hasBackend, type Health } from '@/lib/api'
import type { Lens } from '@/lib/types'
import type { BackendMode } from '@/lib/useSession'
import { CommandCenter, type Inject } from '@/components/CommandCenter'
import { PlaybookLibrary } from '@/components/PlaybookLibrary'
import { AccountMeter } from '@/components/AccountMeter'
import { cn } from '@/lib/utils'

export default function Page() {
  const [lens, setLens] = useState<Lens>('go')
  const [split, setSplit] = useState(false)
  const [backend, setBackend] = useState<BackendMode>(hasBackend() ? 'checking' : 'offline')
  const [health, setHealth] = useState<Health | null>(null)
  const [library, setLibrary] = useState(false)
  const [inject, setInject] = useState<(Inject & { lens: Lens }) | null>(null)
  const [creditsKey, setCreditsKey] = useState(0)

  /** Run a Playbook example: switch to the matching lens (single view) and push the prompt into that Command Center. */
  const runExample = (prompt: string, forLens: Lens) => {
    if (!split) setLens(forLens)
    setInject({ prompt, lens: forLens, n: Date.now() })
    setLibrary(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const [pingNonce, setPingNonce] = useState(0)

  // Health check + auto-reconnect. Render's free tier cold-starts in up to ~60 s, so a few quick failures must NOT lock the page into the
  // offline demo: after the first rounds fail we keep probing every 15 s and flip to "live" the moment the backend answers.
  useEffect(() => {
    if (!hasBackend()) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const ping = async (attempt = 0) => {
      try {
        const h = await api.health(attempt === 0 ? 8000 : 30000)
        if (!alive) return
        setHealth(h)
        setBackend('live')
      } catch {
        if (!alive) return
        if (attempt >= 2) setBackend('offline')
        timer = setTimeout(() => ping(attempt + 1), attempt < 2 ? 3000 : 15000)
      }
    }
    setBackend((b) => (b === 'live' ? b : 'checking'))
    ping()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [pingNonce])

  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 grid-bg" />
      <div className="pointer-events-none fixed -left-40 -top-40 -z-10 h-[520px] w-[520px] animate-aurora rounded-full bg-violet-600/20 blur-[120px]" />
      <div className="pointer-events-none fixed -right-40 top-40 -z-10 h-[480px] w-[480px] animate-aurora rounded-full bg-cyan-500/10 blur-[120px]" />

      <header className="sticky top-0 z-20 border-b border-white/5 bg-ink-950/70 backdrop-blur-xl" id="top-bar">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <Link href="/" id="back-to-landing" aria-label="Back to the COMPASS landing page" title="Back to landing page" className="btn-ghost !px-2"><ArrowLeft size={13} /></Link>
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
            <AccountMeter live={backend === 'live'} refreshKey={creditsKey} />
            <button className="btn-ghost" onClick={() => setLibrary((v) => !v)} id="library-toggle" aria-expanded={library} title="Browse the declarative Playbook library">
              <BookOpen size={13} /> Playbooks
            </button>
            <button className="btn-ghost" onClick={() => setSplit((v) => !v)} id="split-toggle" title="Split-screen: both lenses on the same backend">
              {split ? <Square size={13} /> : <Columns2 size={13} />} {split ? 'Single' : 'Split-screen'}
            </button>
            <BackendBadge mode={backend} health={health} onRetry={() => setPingNonce((n) => n + 1)} />
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] px-4 py-4">
        <AnimatePresence initial={false}>
          {library && (
            <motion.div key="lib" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="mb-4 overflow-hidden">
              <div className="h-[520px]">
                <PlaybookLibrary live={backend === 'live'} lens={lens} onRun={runExample} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        {split ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <CommandCenter key="go" lens="go" backend={backend} compact inject={inject?.lens === 'go' ? inject : null} onInjected={() => setInject(null)} onCreditsChange={() => setCreditsKey((k) => k + 1)} />
            <CommandCenter key="pro" lens="pro" backend={backend} compact inject={inject?.lens === 'pro' ? inject : null} onInjected={() => setInject(null)} onCreditsChange={() => setCreditsKey((k) => k + 1)} />
          </div>
        ) : (
          <CommandCenter key={lens} lens={lens} backend={backend} inject={inject?.lens === lens ? inject : null} onInjected={() => setInject(null)} onCreditsChange={() => setCreditsKey((k) => k + 1)} />
        )}
        <footer className="mt-8 pb-6 text-center text-[10.5px] text-slate-600">
          SerpApi async fan-out · LangGraph agents · Supabase pgvector hybrid RAG · Upstash dedupe · Langfuse traces · HITL actions.
          {backend !== 'live' && ' Running the pre-cached Demo Mode recordings (no backend connected).'}
        </footer>
      </div>
    </main>
  )
}

function BackendBadge({ mode, health, onRetry }: { mode: BackendMode; health: Health | null; onRetry: () => void }) {
  if (mode === 'checking')
    return <span className="chip"><Loader2 size={11} className="animate-spin" /> waking backend…</span>
  if (mode === 'offline')
    return (
      <button type="button" onClick={onRetry} className="chip cursor-pointer text-amber-200 hover:border-amber-300/40"
        title={hasBackend() ? `Backend ${API_URL} is unreachable - still retrying every 15 s. Click to retry now.` : 'NEXT_PUBLIC_API_URL is set to "offline" - showing recorded sessions'}>
        <WifiOff size={11} /> offline demo{hasBackend() ? ' · retry' : ''}
      </button>
    )
  const i = health?.integrations || {}
  const live = Object.entries(i).filter(([k, v]) => k !== 'serpapi' && v === true).map(([k]) => k)
  return (
    <span className="chip text-emerald-200" title={`integrations: ${live.join(', ') || 'none'} · llm ${health?.llm} · store ${health?.store} · cache ${health?.cache?.backend}`}>
      <Wifi size={11} /> backend · serpapi {health?.demo_mode ? 'demo' : 'live'}
    </span>
  )
}

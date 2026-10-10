'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Coins, Flame, Loader2, Mic, MicOff, Play, RefreshCw, Sparkles, Zap, Ban, TrendingDown, ArrowDownWideNarrow } from 'lucide-react'
import type { Lens } from '@/lib/types'
import { SCENARIOS, useSession, type BackendMode } from '@/lib/useSession'
import { cn } from '@/lib/utils'
import { AgentRail, ThoughtTree } from './ThoughtTree'
import { SerpLog } from './SerpLog'
import { RetrievalHeatmap } from './RetrievalHeatmap'
import { DecisionMatrix } from './DecisionMatrix'
import { ActionCards } from './ActionCards'
import { RawCalls } from './RawCalls'
import { PipelineStepper } from './PipelineStepper'
import { IntentBars } from './IntentBars'
import { InsightsPanel } from './InsightsPanel'
import { WatchesPanel } from './WatchesPanel'
import { AnimatedNumber } from './AnimatedNumber'
import { useSpeechToText } from '@/lib/useSpeechToText'

const LENS_META: Record<Lens, { name: string; tagline: string; accent: string }> = {
  go: { name: 'COMPASS Go', tagline: 'Casual lens · trips, deals, jobs', accent: 'from-cyan-400 to-violet-500' },
  pro: { name: 'COMPASS Pro', tagline: 'Enterprise lens · procurement, prior-art, sourcing', accent: 'from-amber-300 to-pink-500' },
}

export interface Inject { prompt: string; n: number }

export function CommandCenter({ lens, backend, compact = false, inject, onInjected, onCreditsChange }: {
  lens: Lens; backend: BackendMode; compact?: boolean; inject?: Inject | null; onInjected?: () => void; onCreditsChange?: () => void
}) {
  const ses = useSession(lens, backend)
  const s = ses.state
  const chips = useMemo(() => {
    const own = SCENARIOS.filter((x) => x.lens === lens)
    const other = SCENARIOS.filter((x) => x.lens !== lens)
    return [...own, ...other].slice(0, compact ? 3 : 5)
  }, [lens, compact])
  const [prompt, setPrompt] = useState(chips[0]?.prompt || '')
  const [tab, setTab] = useState<'live' | 'watches' | 'raw'>('live')
  const handled = useRef(0)
  // native Web Speech API dictation: finalised phrases are appended to the prompt box (interim words are previewed live)
  const speech = useSpeechToText((text) => setPrompt((p) => (p && !/\s$/.test(p) ? `${p} ${text}` : `${p}${text}`)))
  // a prompt pushed from the Playbook library: fill the box and run it once
  useEffect(() => {
    if (!inject || inject.n === handled.current) return
    handled.current = inject.n
    setPrompt(inject.prompt)
    setTab('live')
    ses.start(inject.prompt)
    onInjected?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inject?.n])
  // refresh the header's real SerpApi credit meter whenever a live session settles
  useEffect(() => {
    if (s.status === 'done' && !s.replay) onCreditsChange?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.status])
  const running = s.status === 'running' || s.status === 'connecting' || s.status === 'awaiting_budget'
  const meta = LENS_META[lens]
  const RANK: Record<string, number> = { pending: 0, modified: 0, approved: 1, executed: 2, failed: 2, rejected: 3 }
  const actions = s.actionOrder
    .map((id) => s.actions[id])
    .filter(Boolean)
    .reverse()
    .sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9) || Number(b.requires_approval) - Number(a.requires_approval))
  const canDisrupt = !!s.matrix && !running

  return (
    <div className="flex flex-col gap-3" data-lens={lens}>
      {/* lens header + prompt */}
      <section className="panel p-4" id={`prompt-${lens}`}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className={cn('bg-gradient-to-r bg-clip-text text-lg font-extrabold tracking-tight text-transparent', meta.accent)}>{meta.name}</h2>
          <span className="text-[11px] text-slate-500">{meta.tagline}</span>
          <div className="ml-auto flex items-center gap-1.5">
            {s.replay && <span className="chip text-amber-200">offline replay</span>}
            {s.credits && (
              <span className="chip font-mono" title="SerpApi credit meter (1 live search = 1 credit; cache hits are free)">
                <Coins size={11} className="text-amber-300" /> <AnimatedNumber value={s.credits.spent} duration={0.4} />/{s.credits.budget} credits · <AnimatedNumber value={s.credits.cached} duration={0.4} /> cached
              </span>
            )}
          </div>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            speech.stop()
            if (prompt.trim()) ses.start(prompt.trim())
          }}
        >
          <div className="relative min-w-0 flex-1">
            <input
              id={`prompt-input-${lens}`}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={speech.listening ? 'Listening… speak your request' : lens === 'go' ? 'Plan a 4-day Tokyo trip under $1,200, flights + hotel' : 'Source 3 reliable suppliers for bulk Bluetooth earbuds…'}
              className={cn('w-full rounded-xl border bg-black/30 py-2 pl-3 text-sm outline-none placeholder:text-slate-600 focus:border-violet-400/50', 'pr-11', speech.listening ? 'border-rose-400/60' : 'border-white/10')}
            />
            <button
                type="button"
                id={`mic-${lens}`}
                onClick={speech.toggle}
                aria-pressed={speech.listening}
                aria-label={speech.listening ? 'Stop voice input' : 'Start voice input'}
                title={!speech.supported ? 'Voice input is not supported in this browser' : speech.listening ? 'Listening… click to stop' : 'Speak your request (browser speech recognition)'}
                className={cn('absolute right-1.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-lg transition',
                  speech.listening ? 'bg-rose-500 text-[#fff]' : 'text-slate-400 hover:bg-white/10 hover:text-white')}
              >
                {speech.listening && <span className="absolute inset-0 animate-pulse-ring rounded-lg" style={{ boxShadow: '0 0 0 2px rgb(244 63 94)' }} />}
                {speech.listening ? <Mic size={14} className="relative animate-pulse" /> : (speech.error || !speech.supported) ? <MicOff size={14} /> : <Mic size={14} />}
              </button>
          </div>
          <button className="btn-primary px-4" disabled={running || !prompt.trim()}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {running ? 'Running' : 'Run'}
          </button>
        </form>
        {(speech.listening || speech.error || speech.interim) && (
          <p role="status" aria-live="polite" className={cn('mt-1.5 flex items-center gap-1.5 text-[11px]', speech.error ? 'text-amber-300' : 'text-rose-300')} id={`speech-status-${lens}`}>
            {speech.error ? <MicOff size={11} /> : <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-400" />}
            {speech.error ? speech.error : speech.interim ? <>Hearing: <i className="text-slate-300">{speech.interim}</i></> : 'Listening… speak now, click the mic to stop.'}
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {chips.map((c) => (
            <button key={c.key} type="button" disabled={running}
              onClick={() => { setPrompt(c.prompt); ses.start(c.prompt) }}
              className="chip cursor-pointer hover:border-violet-400/40 hover:text-white disabled:opacity-40">
              <Sparkles size={10} className="text-violet-300" /> {c.prompt.length > 58 ? c.prompt.slice(0, 56) + '…' : c.prompt}
            </button>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/5 pt-3">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">Edge-case injection</span>
          {(() => {
            const pid = s.intent?.playbook_id
            const d = pid === 'lifeops_local'
              ? { kind: 'rating_drop' as const, label: 'Rating drop −45%', tip: "Top venue's rating falls on every platform at the next fresh poll", Icon: TrendingDown }
              : pid === 'research_seo'
                ? { kind: 'rank_drop' as const, label: 'Rank drop −8', tip: 'Tracked domain slips 8 positions in every search engine', Icon: ArrowDownWideNarrow }
                : { kind: 'price_spike' as const, label: 'Price spike +45%', tip: "Top option's price spikes on the next fresh poll", Icon: Flame }
            return (
              <button className="btn-ghost" disabled={!canDisrupt} onClick={() => ses.disrupt(d.kind)} title={d.tip} id={`disrupt-${lens}`}>
                <d.Icon size={12} className="text-rose-300" /> {d.label}
              </button>
            )
          })()}
          {!s.replay && (
            <>
              <button className="btn-ghost" disabled={!canDisrupt} onClick={() => ses.disrupt('unavailable')}><Ban size={12} className="text-rose-300" /> Sold out</button>
              <button className="btn-ghost" disabled={!canDisrupt} onClick={() => ses.repoll()}><RefreshCw size={12} /> Re-poll (cron tick)</button>
            </>
          )}
          <span className="ml-auto text-[10px] font-mono text-slate-500">stage: {s.stage}{s.round ? ` · round ${s.round}` : ''}</span>
        </div>
        {s.error && <p className="mt-2 text-[11px] text-amber-300">{s.error}</p>}
      </section>

      <PipelineStepper s={s} />
      <AgentRail s={s} />

      {/* budget guard */}
      <AnimatePresence>
        {s.budgetPrompt && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="panel flex flex-wrap items-center gap-3 border-amber-400/30 p-3 text-xs">
            <Zap size={14} className="text-amber-300" />
            <span>Expensive fan-out: <b>{s.budgetPrompt.calls}</b> SerpApi calls ({s.budgetPrompt.essential} essential). {s.budgetPrompt.credits.remaining} credits left.</span>
            <div className="ml-auto flex gap-1.5">
              <button className="btn-ok" onClick={() => ses.confirmBudget('all')}>Fire all</button>
              <button className="btn-ghost" onClick={() => ses.confirmBudget('essential')}>Essential only</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex gap-1">
        {(['live', 'watches', 'raw'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} id={`tab-${t}-${lens}`} className={cn('btn', tab === t ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200')}>
            {t === 'live' ? 'Live command center' : t === 'watches' ? 'Watches' : 'Raw calls'}
          </button>
        ))}
      </div>

      {tab === 'raw' ? (
        <RawCalls s={s} />
      ) : tab === 'watches' ? (
        <div className={compact ? 'h-[420px]' : 'h-[460px]'}><WatchesPanel s={s} live={backend === 'live' && !s.replay} /></div>
      ) : (
        <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'lg:grid-cols-3')}>
          <div className={cn(compact ? 'h-[360px]' : 'h-[400px] lg:col-span-1')}><ThoughtTree s={s} /></div>
          <div className={cn(compact ? 'h-[280px]' : 'h-[400px]')}><SerpLog s={s} /></div>
          <div className={cn(compact ? 'h-[320px]' : 'h-[400px]')}><RetrievalHeatmap s={s} /></div>
          <div className={cn(compact ? 'h-[460px]' : 'h-[500px] lg:col-span-2')}><DecisionMatrix s={s} /></div>
          <div className={cn(compact ? 'h-[460px]' : 'h-[500px]')}>
            <ActionCards actions={actions} onApprove={ses.approve} onReject={ses.reject} onModify={ses.modify} icsUrl={ses.icsUrl} />
          </div>
          <div className={cn(compact ? 'h-[380px]' : 'h-[460px]')}><IntentBars s={s} /></div>
          <div className={cn(compact ? 'h-[500px]' : 'h-[460px] lg:col-span-2')}><InsightsPanel s={s} /></div>
        </div>
      )}

      {s.watchTicks.length > 0 && (
        <section className="panel p-3 text-[11px]" id={`watch-ticks-${lens}`}>
          <div className="panel-title mb-1">Watch polls</div>
          {s.watchTicks.slice(-5).map((t, i) => {
            const f = (v?: number | null) => (v === null || v === undefined ? '—' : t.metric === 'rating' ? `★${v.toFixed(2)}` : t.metric === 'position' ? `#${Math.round(v)}` : `$${v.toFixed(0)}`)
            return (
              <div key={i} className="font-mono text-slate-400">
                {t.label}: {f(t.price)} vs {f(t.baseline)} ({t.change_pct > 0 ? '+' : ''}{t.change_pct}%) {t.triggered ? '⚠ triggered → re-plan' : 'ok'}
              </div>
            )
          })}
        </section>
      )}
    </div>
  )
}

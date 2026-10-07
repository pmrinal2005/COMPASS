'use client'

import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Coins, Flame, Loader2, Play, RefreshCw, Sparkles, Zap, Ban } from 'lucide-react'
import type { Lens } from '@/lib/types'
import { SCENARIOS, useSession, type BackendMode } from '@/lib/useSession'
import { cn } from '@/lib/utils'
import { AgentRail, ThoughtTree } from './ThoughtTree'
import { SerpLog } from './SerpLog'
import { RetrievalHeatmap } from './RetrievalHeatmap'
import { DecisionMatrix } from './DecisionMatrix'
import { ActionCards } from './ActionCards'
import { RawCalls } from './RawCalls'

const LENS_META: Record<Lens, { name: string; tagline: string; accent: string }> = {
  go: { name: 'COMPASS Go', tagline: 'Casual lens · trips, deals, jobs', accent: 'from-cyan-400 to-violet-500' },
  pro: { name: 'COMPASS Pro', tagline: 'Enterprise lens · procurement, prior-art, sourcing', accent: 'from-amber-300 to-pink-500' },
}

export function CommandCenter({ lens, backend, compact = false }: { lens: Lens; backend: BackendMode; compact?: boolean }) {
  const ses = useSession(lens, backend)
  const s = ses.state
  const chips = useMemo(() => {
    const own = SCENARIOS.filter((x) => x.lens === lens)
    const other = SCENARIOS.filter((x) => x.lens !== lens)
    return [...own, ...other].slice(0, compact ? 3 : 5)
  }, [lens, compact])
  const [prompt, setPrompt] = useState(chips[0]?.prompt || '')
  const [tab, setTab] = useState<'live' | 'raw'>('live')
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
                <Coins size={11} className="text-amber-300" /> {s.credits.spent}/{s.credits.budget} credits · {s.credits.cached} cached
              </span>
            )}
          </div>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (prompt.trim()) ses.start(prompt.trim())
          }}
        >
          <input
            id={`prompt-input-${lens}`}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={lens === 'go' ? 'Plan a 4-day Tokyo trip under $1,200, flights + hotel' : 'Source 3 reliable suppliers for bulk Bluetooth earbuds…'}
            className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-600 focus:border-violet-400/50"
          />
          <button className="btn-primary px-4" disabled={running || !prompt.trim()}>
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} {running ? 'Running' : 'Run'}
          </button>
        </form>
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
          <button className="btn-ghost" disabled={!canDisrupt} onClick={() => ses.disrupt('price_spike')} title="Top option's price spikes on the next fresh poll">
            <Flame size={12} className="text-rose-300" /> Price spike +45%
          </button>
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
        {(['live', 'raw'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn('btn', tab === t ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-slate-200')}>
            {t === 'live' ? 'Live command center' : 'Raw calls'}
          </button>
        ))}
      </div>

      {tab === 'raw' ? (
        <RawCalls s={s} />
      ) : (
        <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'lg:grid-cols-3')}>
          <div className={cn(compact ? 'h-[360px]' : 'h-[400px] lg:col-span-1')}><ThoughtTree s={s} /></div>
          <div className={cn(compact ? 'h-[280px]' : 'h-[400px]')}><SerpLog s={s} /></div>
          <div className={cn(compact ? 'h-[320px]' : 'h-[400px]')}><RetrievalHeatmap s={s} /></div>
          <div className={cn(compact ? 'h-[460px]' : 'h-[500px] lg:col-span-2')}><DecisionMatrix s={s} /></div>
          <div className={cn(compact ? 'h-[460px]' : 'h-[500px]')}>
            <ActionCards actions={actions} onApprove={ses.approve} onReject={ses.reject} onModify={ses.modify} icsUrl={ses.icsUrl} />
          </div>
        </div>
      )}

      {s.watchTicks.length > 0 && (
        <section className="panel p-3 text-[11px]" id={`watch-ticks-${lens}`}>
          <div className="panel-title mb-1">Watch polls</div>
          {s.watchTicks.slice(-5).map((t, i) => (
            <div key={i} className="font-mono text-slate-400">
              {t.label}: ${t.price?.toFixed?.(0)} vs ${t.baseline?.toFixed?.(0)} ({t.change_pct > 0 ? '+' : ''}{t.change_pct}%) {t.triggered ? '⚠ triggered → re-plan' : 'ok'}
            </div>
          ))}
        </section>
      )}
    </div>
  )
}

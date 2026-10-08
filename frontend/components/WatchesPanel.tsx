'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, BellRing, CheckCircle2, Eye, Loader2, RefreshCw, Timer } from 'lucide-react'
import type { SessionState, WatchRecord, WatchTick } from '@/lib/types'
import { useWatches } from '@/lib/useWatches'
import { ago, cn, engineColor, money } from '@/lib/utils'
import { AnimatedNumber } from './AnimatedNumber'

const fmt = (m: WatchRecord['metric'], v?: number | null) =>
  v === null || v === undefined ? '—' : m === 'rating' ? `★ ${v.toFixed(2)}` : m === 'position' ? `#${Math.round(v)}` : money(v)

function Spark({ pts, color, bad }: { pts: number[]; color: string; bad: boolean }) {
  if (pts.length < 2) return <div className="grid h-8 w-24 place-items-center text-[9px] text-slate-600">no history</div>
  const min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${(i / (pts.length - 1)) * 96},${30 - ((p - min) / span) * 26}`).join(' ')
  const last = pts[pts.length - 1]
  return (
    <svg viewBox="0 0 96 32" className="h-8 w-24" aria-label="watch history sparkline">
      <motion.path d={d} fill="none" stroke={bad ? '#f43f5e' : color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8 }} />
      <motion.circle cx="96" cy={30 - ((last - min) / span) * 26} r="2.6" fill={bad ? '#f43f5e' : color} initial={{ scale: 0 }} animate={{ scale: [0, 1.6, 1] }} transition={{ delay: 0.7 }} />
    </svg>
  )
}

function Row({ w, tick, busy, onCheck }: { w: WatchRecord; tick?: WatchTick; busy: boolean; onCheck: () => void }) {
  const m = w.metric ?? 'price'
  const base = w.baseline_price ?? null
  const cur = w.last_price ?? null
  const pctMove = base && cur ? ((cur - base) / base) * 100 : 0
  const hist = (w.history || []).map((h) => h.price).filter((x): x is number => typeof x === 'number')
  const bad = !!tick?.triggered
  const color = engineColor(w.engine)
  return (
    <motion.li layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -12 }}
      className={cn('rounded-xl border px-3 py-2', bad ? 'animate-glow border-rose-400/40 bg-rose-500/[0.06]' : 'border-white/[0.07] bg-white/[0.02]')} data-watch={w.id}>
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color, boxShadow: `0 0 8px ${color}` }} />
        <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-slate-100" title={w.label}>{w.label}</span>
        <span className="chip font-mono">{m}</span>
        <span className="chip font-mono" style={{ color }}>{w.engine}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500">baseline → now</div>
          <div className="font-mono text-[12px] text-slate-200">
            {fmt(m, base)} <span className="text-slate-600">→</span>{' '}
            <span className={cn('font-bold', pctMove === 0 ? 'text-slate-100' : (m === 'rating' ? pctMove < 0 : pctMove > 0) ? 'text-rose-300' : 'text-emerald-300')}>
              {m === 'price' ? <AnimatedNumber value={cur} prefix="$" /> : m === 'rating' ? <AnimatedNumber value={cur} digits={2} prefix="★ " /> : <AnimatedNumber value={cur} prefix="#" />}
            </span>
            {pctMove !== 0 && <span className="ml-1 text-[10px] text-slate-500">({pctMove > 0 ? '+' : ''}{pctMove.toFixed(1)}%)</span>}
          </div>
        </div>
        <Spark pts={hist} color={color} bad={bad} />
        <div className="ml-auto flex flex-col items-end gap-1">
          <button className="btn-ghost px-2 py-1" onClick={onCheck} disabled={busy} aria-label={`check ${w.label} now`}>
            {busy ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />} Check now
          </button>
        </div>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
        <span className="inline-flex items-center gap-0.5"><Timer size={10} /> every {w.cadence_minutes} min</span>
        <span>±{w.threshold_pct}% threshold</span>
        <span>checked {ago(w.last_checked)}</span>
        {!!w.alerts && <span className="inline-flex items-center gap-0.5 text-amber-300"><BellRing size={10} /> {w.alerts} alert(s)</span>}
        {tick && (tick.triggered
          ? <span className="inline-flex items-center gap-0.5 text-rose-300"><AlertTriangle size={10} /> triggered {tick.change_pct > 0 ? '+' : ''}{tick.change_pct}%{tick.replan ? ' · re-plan scheduled' : ''}</span>
          : <span className="inline-flex items-center gap-0.5 text-emerald-300"><CheckCircle2 size={10} /> within threshold</span>)}
      </div>
    </motion.li>
  )
}

/** Standing SerpApi watches (price / rating / rank): live from the backend, plus a clearly-labelled simulation offline. */
export function WatchesPanel({ s, live }: { s: SessionState; live: boolean }) {
  const w = useWatches(s, live)
  const last = new Map<string, WatchTick>()
  w.ticks.forEach((t) => last.set(t.id, t))
  return (
    <section className="panel flex h-full flex-col p-4" id={`watches-${s.lens}`}>
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="panel-title"><Eye size={13} /> Watches · standing SerpApi consumers</h3>
        <span className="chip font-mono">{w.watches.length}</span>
        {w.simulated && <span className="chip text-amber-200" title="No backend connected: polls are simulated locally with deterministic drift.">simulated polls</span>}
        {live && <button className="btn-ghost ml-auto px-2 py-1" onClick={w.refresh}><RefreshCw size={11} /> Refresh</button>}
      </header>
      {w.error && <p className="mb-1 text-[10.5px] text-rose-300">{w.error}</p>}
      <div className="scroll-thin min-h-0 flex-1 overflow-auto pr-1">
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {w.watches.map((x) => <Row key={x.id} w={x} tick={last.get(x.id)} busy={w.busy === x.id} onCheck={() => w.check(x)} />)}
          </AnimatePresence>
        </ul>
        {w.watches.length === 0 && (
          <div className="grid place-items-center px-4 py-8 text-center text-xs text-slate-500">
            No watches yet. Approve a “Watch this fare / venue / rank” card in the Actor panel and it lands here; a scheduler tick (GitHub Actions → <code className="mx-1 text-slate-400">POST /api/watch/tick</code>) then re-polls it with a fresh SerpApi call.
          </div>
        )}
      </div>
    </section>
  )
}

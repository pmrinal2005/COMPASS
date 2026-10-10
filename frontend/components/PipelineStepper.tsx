'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { BarChart3, Bot, Brain, Check, Pause, RotateCcw, Search, ShieldCheck, Workflow } from 'lucide-react'
import type { SessionState } from '@/lib/types'
import { usePipeline, type StepKey } from '@/lib/pipeline'
import { AGENT_META, cn } from '@/lib/utils'
import { useTheme } from '@/lib/theme'

const ICON: Record<StepKey, any> = { plan: Brain, search: Search, verify: ShieldCheck, compare: BarChart3, act: Bot }
const COLOR: Record<StepKey, string> = {
  plan: AGENT_META.orchestrator.color, search: AGENT_META.researcher.color, verify: '#38bdf8', compare: AGENT_META.analyst.color, act: AGENT_META.actor.color,
}
const fmtMs = (ms: number | null) => (ms === null ? '' : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`)

/** Plan → Search → Verify → Compare → Act, driven purely by the SSE `stage` events (incl. the bounded re-plan loop). */
export function PipelineStepper({ s }: { s: SessionState }) {
  const p = usePipeline(s)
  const light = useTheme().theme === 'light'
  const idleRing = light ? 'rgba(15,23,42,0.18)' : 'rgba(255,255,255,0.12)'
  const idleFill = light ? 'rgba(15,23,42,0.04)' : 'rgba(255,255,255,0.03)'
  return (
    <section className="panel p-3" id={`pipeline-${s.lens}`} aria-label="agent pipeline">
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="panel-title"><Workflow size={13} /> Pipeline</h3>
        <AnimatePresence>
          {p.loops > 0 && (
            <motion.span key="loops" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              className="chip border-pink-400/30 text-pink-200" title="bounded re-planning loop (hard cap)">
              <motion.span animate={{ rotate: -360 }} transition={{ repeat: Infinity, duration: 2.4, ease: 'linear' }} className="inline-flex">
                <RotateCcw size={10} />
              </motion.span>
              re-plan {p.loops}/{p.maxLoops}
            </motion.span>
          )}
          {p.waiting && (
            <motion.span key="wait" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="chip animate-glow border-amber-300/40 text-amber-200">
              <Pause size={10} /> waiting for budget confirmation
            </motion.span>
          )}
          {p.finished && (
            <motion.span key="fin" initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} className="chip border-emerald-400/30 text-emerald-200">
              <Check size={10} /> complete
            </motion.span>
          )}
        </AnimatePresence>
        <span className="ml-auto font-mono text-[10px] text-slate-500">{Math.round(p.progress * 100)}%</span>
      </header>

      <ol className="flex items-start" role="list">
        {p.steps.map((st, i) => {
          const Icon = ICON[st.key]
          const col = COLOR[st.key]
          const active = st.state === 'active'
          const done = st.state === 'done'
          return (
            <li key={st.key} className="flex min-w-0 flex-1 items-start" data-state={st.state} aria-current={active ? 'step' : undefined}>
              <div className="flex min-w-0 flex-col items-center text-center" style={{ width: 'max-content', maxWidth: '100%' }}>
                <motion.div
                  className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full border"
                  animate={{ scale: active ? 1.12 : 1, borderColor: done || active ? col : idleRing, backgroundColor: done ? col : active ? `${col}26` : idleFill }}
                  transition={{ type: 'spring', stiffness: 320, damping: 22 }}
                >
                  {active && <span className="absolute inset-0 animate-pulse-ring rounded-full" style={{ boxShadow: `0 0 0 2px ${col}` }} />}
                  <AnimatePresence mode="wait" initial={false}>
                    {done ? (
                      <motion.span key="ok" initial={{ scale: 0, rotate: -90 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: 'spring', stiffness: 500, damping: 18 }} className="text-ink-950">
                        <Check size={16} strokeWidth={3} />
                      </motion.span>
                    ) : (
                      <motion.span key="ic" initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ color: active ? col : '#64748b' }}>
                        <Icon size={15} />
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {st.visits > 1 && (
                    <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-pink-500 px-1 text-[9px] font-bold text-[#fff]">
                      ×{st.visits}
                    </motion.span>
                  )}
                </motion.div>
                <div className={cn('mt-1 text-[11px] font-semibold', active ? 'text-white' : done ? 'text-slate-200' : 'text-slate-500')}>{st.label}</div>
                <div className="hidden max-w-[130px] truncate text-[9.5px] text-slate-500 md:block">{st.hint}</div>
                <div className="h-3 font-mono text-[9.5px] text-slate-500">{fmtMs(st.ms)}</div>
              </div>
              {i < p.steps.length - 1 && (
                <div className="relative mx-1 mt-[17px] h-[3px] min-w-3 flex-1 overflow-hidden rounded-full bg-white/10" aria-hidden>
                  <motion.div className="absolute inset-y-0 left-0 rounded-full" initial={{ width: 0 }} animate={{ width: done ? '100%' : '0%' }}
                    transition={{ duration: 0.6, ease: 'easeOut' }} style={{ background: `linear-gradient(90deg, ${col}, ${COLOR[p.steps[i + 1].key]})` }} />
                  {active && <span className="absolute inset-y-0 w-1/4 animate-sweep rounded-full" style={{ background: `linear-gradient(90deg, transparent, ${col}, transparent)` }} />}
                </div>
              )}
            </li>
          )
        })}
      </ol>

      <div className="mt-2 h-[3px] overflow-hidden rounded-full bg-white/5" role="progressbar" aria-valuenow={Math.round(p.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
        <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-400 via-cyan-400 to-emerald-400" animate={{ width: `${p.progress * 100}%` }} transition={{ type: 'spring', stiffness: 120, damping: 24 }} />
      </div>
    </section>
  )
}

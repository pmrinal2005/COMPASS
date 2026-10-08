'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, Bot, ChevronDown, Globe2, Sparkles, TrendingDown, TrendingUp, X, Check } from 'lucide-react'
import type { Insights, SeoGridCell } from '@/lib/types'
import { cn, engineColor, positionHeat } from '@/lib/utils'
import { AnimatedNumber } from './AnimatedNumber'

type SeoIns = Extract<Insights, { kind: 'seo' }>

function Kpi({ label, children, sub }: { label: string; children: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-2 py-1.5 text-center">
      <div className="text-base font-bold text-slate-100">{children}</div>
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      {sub && <div className="font-mono text-[9px] text-slate-600">{sub}</div>}
    </div>
  )
}

/** Multi-engine SEO visibility: where the tracked domain ranks on each search engine, AI citations, and the competitor leaderboard. */
export function SeoGrid({ ins, prev }: { ins: SeoIns; prev?: Insights | null }) {
  const [openAi, setOpenAi] = useState<string | null>(null)
  const before = new Map<string, SeoGridCell>()
  if (prev?.kind === 'seo') prev.grid.forEach((c) => before.set(c.engine, c))
  const maxVis = Math.max(1, ...ins.leaders.map((l) => l.visibility))
  return (
    <div className="flex h-full flex-col gap-2" id="seo-grid">
      <div className="flex flex-wrap items-center gap-1.5 text-[10.5px] text-slate-400">
        <Globe2 size={12} className="text-cyan-300" />
        <span className="font-semibold text-slate-100">{ins.domain}</span> for <span className="text-slate-200">“{ins.keyword}”</span>
        <span className="chip">market {String(ins.market || 'us').toUpperCase()}</span>
        {ins.anomaly && <span className="chip animate-alert border-rose-400/40 text-rose-200"><AlertTriangle size={10} /> {ins.anomaly}</span>}
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        <Kpi label="Visibility"><AnimatedNumber value={ins.visibility} digits={1} /></Kpi>
        <Kpi label="Share of voice"><AnimatedNumber value={ins.share_of_voice} digits={1} suffix="%" /></Kpi>
        <Kpi label="Domain rank" sub={`of ${ins.total_domains}`}>{ins.rank_of ? <>#<AnimatedNumber value={ins.rank_of} /></> : '—'}</Kpi>
        <Kpi label="Avg position" sub={`${Math.round(ins.coverage * 100)}% engines`}>{ins.avg_position != null ? <AnimatedNumber value={ins.avg_position} digits={1} /> : '—'}</Kpi>
      </div>

      <div className="grid grid-cols-7 gap-1.5" aria-label="rank by search engine">
        {ins.grid.map((c, i) => {
          const old = before.get(c.engine)
          const d = old?.position != null && c.position != null ? c.position - old.position : 0
          return (
            <motion.div key={c.engine} layout initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05, type: 'spring', stiffness: 260, damping: 20 }}
              className="relative overflow-hidden rounded-lg border border-white/10 px-1 py-1.5 text-center" title={`${c.label}: ${c.found ? `position ${c.position}` : 'not in top results'} · weight ${Math.round(c.weight * 100)}% · est. CTR ${(c.ctr * 100).toFixed(1)}%${c.leader ? ` · leader ${c.leader}` : ''}`}>
              <motion.div className="absolute inset-0" animate={{ backgroundColor: `${positionHeat(c.found ? c.position : null)}${c.found ? '33' : '15'}` }} transition={{ duration: 0.6 }} />
              <div className="relative">
                <div className="truncate text-[9px] font-semibold uppercase tracking-wide" style={{ color: engineColor(c.engine) }}>{c.label}</div>
                <motion.div key={String(c.position)} initial={{ y: -8, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="font-mono text-lg font-extrabold" style={{ color: positionHeat(c.found ? c.position : null) }}>
                  {c.found ? c.position : '—'}
                </motion.div>
                <div className="h-3 text-[9px]">
                  {d !== 0 ? (
                    <span className={cn('inline-flex items-center', d > 0 ? 'text-rose-300' : 'text-emerald-300')}>
                      {d > 0 ? <TrendingDown size={9} /> : <TrendingUp size={9} />}{Math.abs(d)}
                    </span>
                  ) : <span className="font-mono text-slate-600">{Math.round(c.weight * 100)}%</span>}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {ins.ai.map((a) => (
          <button key={a.engine} type="button" onClick={() => setOpenAi(openAi === a.engine ? null : a.engine)} disabled={!ins.ai_text?.[a.engine]}
            className={cn('chip cursor-pointer gap-1 disabled:cursor-default', a.cited ? 'border-emerald-400/40 text-emerald-200' : 'border-rose-400/30 text-rose-200')}>
            <Bot size={10} /> {a.label}: {a.cited ? <><Check size={10} /> cited</> : <><X size={10} /> not cited</>}
            {ins.ai_text?.[a.engine] && <ChevronDown size={10} className={cn('transition', openAi === a.engine && 'rotate-180')} />}
          </button>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {openAi && ins.ai_text?.[openAi] && (
          <motion.p key={openAi} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="scroll-thin max-h-24 overflow-auto rounded-lg border border-violet-300/15 bg-violet-400/[0.05] px-2.5 py-1.5 text-[10.5px] leading-relaxed text-slate-300">
            <Sparkles size={10} className="mr-1 inline text-violet-300" />{ins.ai_text[openAi]}
          </motion.p>
        )}
      </AnimatePresence>

      <div className="scroll-thin min-h-0 flex-1 space-y-1 overflow-auto pr-1">
        <div className="text-[9.5px] uppercase tracking-wider text-slate-500">Competitor leaderboard (weighted visibility)</div>
        {ins.leaders.map((l, i) => {
          const me = l.domain === ins.domain
          return (
            <div key={l.domain} className={cn('relative overflow-hidden rounded-md border px-2 py-1', me ? 'border-cyan-400/40' : 'border-white/5')}>
              <motion.div className="absolute inset-y-0 left-0" initial={{ width: 0 }} animate={{ width: `${(l.visibility / maxVis) * 100}%` }} transition={{ type: 'spring', stiffness: 90, damping: 18, delay: i * 0.06 }}
                style={{ background: me ? 'linear-gradient(90deg,#22d3ee55,transparent)' : 'linear-gradient(90deg,#64748b44,transparent)' }} />
              <div className="relative flex items-center gap-2 text-[10.5px]">
                <span className="w-4 font-mono text-slate-500">{i + 1}</span>
                <span className={cn('min-w-0 flex-1 truncate', me ? 'font-bold text-cyan-200' : 'text-slate-300')}>{l.domain}</span>
                <span className="font-mono text-slate-500">{l.found} eng</span>
                <span className="w-10 text-right font-mono text-slate-200">{l.visibility.toFixed(1)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

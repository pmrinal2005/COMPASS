'use client'

import { motion, LayoutGroup } from 'framer-motion'
import { AlertTriangle, BarChart3, ShieldCheck, ExternalLink, TrendingUp, TrendingDown } from 'lucide-react'
import type { SessionState } from '@/lib/types'
import { cn, money, pct } from '@/lib/utils'

const DIM_COLORS = ['#a78bfa', '#22d3ee', '#fbbf24', '#34d399', '#f472b6', '#fb923c']

function fmtPrice(cat: string, v?: number | null) {
  if (v === null || v === undefined) return '—'
  if (cat === 'job') return `${money(v)}/yr`
  return money(v, v < 100 ? 2 : 0)
}

/** Weighted multi-criteria decision matrix with confidence gauge, anomalies and rank movement. */
export function DecisionMatrix({ s }: { s: SessionState }) {
  const m = s.matrix
  const conf = s.confidence ?? 0
  const thr = s.threshold ?? 0.62
  return (
    <section className="panel flex h-full flex-col p-4" id="decision-matrix">
      <header className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="panel-title"><BarChart3 size={13} /> Decision matrix</h3>
        {m && (
          <div className="ml-auto flex items-center gap-2">
            <div className="relative h-2 w-28 overflow-hidden rounded-full bg-white/10">
              <motion.div className="h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${conf * 100}%` }}
                style={{ background: conf >= thr ? 'linear-gradient(90deg,#22d3ee,#34d399)' : 'linear-gradient(90deg,#f43f5e,#fbbf24)' }} />
              <div className="absolute inset-y-0 w-px bg-white/70" style={{ left: `${thr * 100}%` }} title="re-plan threshold" />
            </div>
            <span className={cn('font-mono text-xs font-bold', conf >= thr ? 'text-emerald-300' : 'text-amber-300')}>{pct(conf)}</span>
          </div>
        )}
      </header>

      {!m ? (
        <div className="grid flex-1 place-items-center text-xs text-slate-500">The Analyst populates this once evidence is verified.</div>
      ) : (
        <>
          {s.rationale && <p className="mb-2 rounded-lg border border-amber-300/10 bg-amber-300/[0.04] px-3 py-2 text-[11.5px] leading-relaxed text-amber-50/90">{s.rationale}</p>}
          {s.caveat && <p className="mb-2 rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-1.5 text-[11px] text-rose-200">{s.caveat}</p>}
          {s.reasons.length > 0 && conf < thr && (
            <p className="mb-2 text-[10.5px] text-amber-300/80">Low-confidence reasons: {s.reasons.join(' · ')}</p>
          )}
          <div className="mb-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
            {m.dimensions.map((d, i) => (
              <span key={d.key} className="inline-flex items-center gap-1">
                <span className="h-2 w-2 rounded-sm" style={{ background: DIM_COLORS[i % DIM_COLORS.length] }} />
                {d.label} {Math.round(d.weight * 100)}% {d.direction === 'min' ? '↓' : '↑'}
              </span>
            ))}
          </div>
          <div className="scroll-thin flex-1 overflow-auto">
            <LayoutGroup>
              <ol className="space-y-1.5">
                {m.rows.slice(0, 8).map((r, i) => {
                  const prev = s.prevOrder.indexOf(r.id)
                  const moved = prev >= 0 && prev !== i ? prev - i : 0
                  return (
                    <motion.li layout key={r.id} transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                      className={cn('rounded-xl border px-3 py-2', i === 0 ? 'border-emerald-400/30 bg-emerald-400/[0.05]' : 'border-white/[0.06] bg-white/[0.02]')}>
                      <div className="flex items-center gap-2">
                        <span className={cn('grid h-5 w-5 shrink-0 place-items-center rounded-md text-[10px] font-bold', i === 0 ? 'bg-emerald-400 text-emerald-950' : 'bg-white/10 text-slate-300')}>{i + 1}</span>
                        <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-slate-100" title={r.title}>{r.title}</span>
                        {moved !== 0 && (
                          <span className={cn('inline-flex items-center text-[10px]', moved > 0 ? 'text-emerald-300' : 'text-rose-300')}>
                            {moved > 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}{Math.abs(moved)}
                          </span>
                        )}
                        <span className="font-mono text-[11px] text-slate-200">{fmtPrice(r.category, r.price)}</span>
                        <span className="w-10 text-right font-mono text-[11px] font-bold text-cyan-300">{(r.score ?? 0).toFixed(2)}</span>
                      </div>
                      <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-white/5">
                        {m.dimensions.map((d, j) => (
                          <motion.div key={d.key} initial={{ width: 0 }} animate={{ width: `${(r.breakdown[d.key] || 0) * 100}%` }}
                            style={{ background: DIM_COLORS[j % DIM_COLORS.length] }} title={`${d.label}: ${(r.breakdown[d.key] || 0).toFixed(3)}`} />
                        ))}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500">
                        <span>{r.source}</span>
                        {r.rating ? <span>★ {r.rating}{r.reviews ? ` (${r.reviews.toLocaleString()})` : ''}</span> : null}
                        {r.attributes?.stops !== undefined && <span>{r.attributes.stops} stop(s)</span>}
                        {r.attributes?.moq ? <span>MOQ {r.attributes.moq}</span> : null}
                        {r.attributes?.cited_by ? <span>cited {r.attributes.cited_by}</span> : null}
                        {r.verified ? (
                          <span className="inline-flex items-center gap-0.5 text-emerald-300" title={r.sources.join(', ')}><ShieldCheck size={10} /> {r.sources.length} sources</span>
                        ) : (
                          <span className="text-amber-300" title={r.sources.join(', ')}>⚠ single-source</span>
                        )}
                        {r.anomaly && <span className="inline-flex items-center gap-0.5 text-rose-300"><AlertTriangle size={10} /> {r.anomaly}</span>}
                        {r.url && (
                          <a href={r.url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-0.5 text-slate-400 hover:text-slate-200">
                            open <ExternalLink size={9} />
                          </a>
                        )}
                      </div>
                    </motion.li>
                  )
                })}
              </ol>
            </LayoutGroup>
          </div>
          {s.anomalies.length > 0 && (
            <div className="mt-2 rounded-lg border border-rose-400/20 bg-rose-500/[0.06] px-3 py-1.5 text-[10.5px] text-rose-200">
              <AlertTriangle size={11} className="mr-1 inline" />{s.anomalies.length} anomaly flag(s): {s.anomalies.slice(0, 2).map((a) => `${a.title.slice(0, 30)} — ${a.reason}`).join(' · ')}
            </div>
          )}
        </>
      )}
    </section>
  )
}

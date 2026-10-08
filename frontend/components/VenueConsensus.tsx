'use client'

import { motion, LayoutGroup } from 'framer-motion'
import { AlertTriangle, ExternalLink, MapPin, ShieldCheck, TrendingDown, TrendingUp } from 'lucide-react'
import type { Insights, VenueInsight } from '@/lib/types'
import { cn, platformColor } from '@/lib/utils'
import { AnimatedNumber } from './AnimatedNumber'

type VenueIns = Extract<Insights, { kind: 'venues' }>

/** Cross-platform consensus: the same venue's rating on Google Maps / Yelp / Tripadvisor, merged by entity resolution. */
export function VenueConsensus({ ins, prev }: { ins: VenueIns; prev?: Insights | null }) {
  const before = new Map<string, VenueInsight>()
  if (prev?.kind === 'venues') prev.venues.forEach((v) => before.set(v.id, v))
  const venues = ins.venues.slice(0, 6)
  return (
    <div className="flex h-full flex-col" id="venue-consensus">
      <div className="mb-2 flex flex-wrap items-center gap-1.5 text-[10.5px] text-slate-400">
        <MapPin size={12} className="text-emerald-300" />
        <span className="text-slate-200">{ins.query || 'venues'}</span> in <span className="text-slate-200">{ins.city || '—'}</span>
        {ins.min_rating ? <span className="chip">≥ {ins.min_rating}★</span> : null}
        {ins.price_cap ? <span className="chip">{'$'.repeat(ins.price_cap)} max</span> : null}
        <span className="ml-auto flex gap-1.5">
          {ins.platforms.map((p) => (
            <span key={p} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: platformColor(p) }} />{p}</span>
          ))}
        </span>
      </div>
      {!ins.yelp_supported && <p className="mb-2 rounded border border-amber-300/20 bg-amber-300/5 px-2 py-1 text-[10px] text-amber-200">Yelp does not cover this country — consensus uses Google Maps + Tripadvisor.</p>}
      <div className="scroll-thin flex-1 overflow-auto pr-1">
        <LayoutGroup>
          <ol className="space-y-2">
            {venues.map((v, i) => {
              const old = before.get(v.id)
              const delta = old?.rating != null && v.rating != null ? +(v.rating - old.rating).toFixed(2) : 0
              return (
                <motion.li layout key={v.id} transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  className={cn('rounded-xl border px-3 py-2', i === 0 ? 'border-emerald-400/30 bg-emerald-400/[0.05]' : 'border-white/[0.06] bg-white/[0.02]', v.anomaly && 'border-rose-400/30')}>
                  <div className="flex items-center gap-2">
                    <span className={cn('grid h-5 w-5 shrink-0 place-items-center rounded-md text-[10px] font-bold', i === 0 ? 'bg-emerald-400 text-emerald-950' : 'bg-white/10 text-slate-300')}>{i + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-slate-100" title={v.title}>{v.title}</span>
                    {v.price_level ? <span className="font-mono text-[11px] text-slate-400">{'$'.repeat(v.price_level)}</span> : null}
                    {delta !== 0 && (
                      <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className={cn('inline-flex items-center gap-0.5 font-mono text-[10px]', delta < 0 ? 'text-rose-300' : 'text-emerald-300')}>
                        {delta < 0 ? <TrendingDown size={11} /> : <TrendingUp size={11} />}{delta > 0 ? '+' : ''}{delta}
                      </motion.span>
                    )}
                    <span className="font-mono text-sm font-bold text-amber-300">★ <AnimatedNumber value={v.rating ?? null} digits={2} duration={0.7} /></span>
                  </div>
                  <div className="mt-1.5 space-y-1">
                    {Object.entries(v.platforms).map(([name, p]) => (
                      <div key={name} className="flex items-center gap-2 text-[10px]">
                        <span className="w-[78px] shrink-0 truncate text-slate-400">{name}</span>
                        <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                          <motion.div className="absolute inset-y-0 left-0 rounded-full" initial={{ width: 0 }} animate={{ width: `${((p.rating ?? 0) / 5) * 100}%` }}
                            transition={{ type: 'spring', stiffness: 100, damping: 18, delay: i * 0.05 }} style={{ background: platformColor(name) }} />
                          {v.rating != null && <div className="absolute inset-y-0 w-px bg-white/70" style={{ left: `${(v.rating / 5) * 100}%` }} title="consensus" />}
                        </div>
                        <span className="w-8 text-right font-mono text-slate-200">{p.rating ?? '—'}</span>
                        <span className="w-14 text-right font-mono text-slate-500">{p.reviews != null ? p.reviews.toLocaleString() : ''}</span>
                        {p.url && <a href={p.url} target="_blank" rel="noreferrer" aria-label={`open on ${name}`} className="text-slate-500 hover:text-slate-200"><ExternalLink size={9} /></a>}
                      </div>
                    ))}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500">
                    <span>{(v.reviews ?? 0).toLocaleString()} reviews</span>
                    <span title="max − min rating across platforms (low = agreement)">spread {v.spread ?? 0}</span>
                    {v.meets_filters === false && <span className="text-amber-300">below your filters</span>}
                    {v.verified ? (
                      <span className="inline-flex items-center gap-0.5 text-emerald-300"><ShieldCheck size={10} /> {Object.keys(v.platforms).length} platforms agree</span>
                    ) : <span className="text-amber-300">⚠ single platform</span>}
                    {v.anomaly && <span className="inline-flex items-center gap-0.5 text-rose-300"><AlertTriangle size={10} /> {v.anomaly}</span>}
                    {v.score != null && <span className="ml-auto font-mono text-cyan-300">{v.score.toFixed(2)}</span>}
                  </div>
                </motion.li>
              )
            })}
          </ol>
        </LayoutGroup>
      </div>
    </div>
  )
}

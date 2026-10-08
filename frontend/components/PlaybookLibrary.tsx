'use client'

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { BookOpen, Layers, Play, Search } from 'lucide-react'
import { api } from '@/lib/api'
import type { Lens, Playbook } from '@/lib/types'
import { cn, engineColor } from '@/lib/utils'
import offlineLibrary from '@/lib/demo/playbooks.json'

const ECO: Record<string, { name: string; color: string }> = {
  A: { name: 'A · LifeOps', color: '#34d399' }, B: { name: 'B · Career & Talent', color: '#a78bfa' }, C: { name: 'C · Research & IP', color: '#22d3ee' },
}

/** The declarative Playbook library: engines, fallback engines, decision dimensions and action types per Playbook. Click an example to run it. */
export function PlaybookLibrary({ live, lens, onRun }: { live: boolean; lens: Lens; onRun: (prompt: string, lens: Lens) => void }) {
  const [books, setBooks] = useState<Playbook[]>(offlineLibrary as unknown as Playbook[])
  const [source, setSource] = useState<'offline' | 'live'>('offline')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    if (!live) return
    let alive = true
    api.playbooks().then((b) => { if (alive && Array.isArray(b) && b.length) { setBooks(b); setSource('live') } }).catch(() => {})
    return () => { alive = false }
  }, [live])

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase()
    return books.filter((b) => !t || [b.name, b.description, b.id, ...b.engine_list, ...b.keywords].join(' ').toLowerCase().includes(t))
  }, [books, q])

  return (
    <section className="panel flex h-full flex-col p-4" id="playbook-library">
      <header className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="panel-title"><BookOpen size={13} /> Playbook library</h3>
        <span className="chip font-mono">{books.length} playbooks</span>
        <span className={cn('chip', source === 'live' ? 'text-emerald-200' : 'text-amber-200')}>{source === 'live' ? 'GET /api/playbooks' : 'bundled copy'}</span>
        <label className="relative ml-auto">
          <Search size={11} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter by engine, keyword…" aria-label="filter playbooks"
            className="w-44 rounded-lg border border-white/10 bg-black/30 py-1 pl-6 pr-2 text-[11px] outline-none placeholder:text-slate-600 focus:border-violet-400/50" />
        </label>
      </header>
      <div className="scroll-thin stagger grid min-h-0 flex-1 gap-2 overflow-auto pr-1 sm:grid-cols-2">
        {shown.map((b) => {
          const eco = ECO[b.ecosystem] || { name: b.ecosystem, color: '#94a3b8' }
          const isOpen = open === b.id
          const dims = Object.entries(b.dimensions || {})
          return (
            <motion.article layout key={b.id} className={cn('rounded-xl border p-3', b.lens === lens ? 'border-white/15 bg-white/[0.035]' : 'border-white/[0.06] bg-white/[0.015]')}>
              <div className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: eco.color }} />
                <div className="min-w-0 flex-1">
                  <h4 className="truncate text-[12.5px] font-semibold text-slate-100" title={b.name}>{b.name}</h4>
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    <span className="chip" style={{ color: eco.color }}>{eco.name}</span>
                    <span className={cn('chip', b.lens === 'pro' ? 'text-amber-200' : 'text-cyan-200')}>{b.lens === 'pro' ? 'Pro' : 'Go'}</span>
                  </div>
                </div>
                <button className="btn-ghost px-2 py-1" onClick={() => setOpen(isOpen ? null : b.id)} aria-expanded={isOpen}><Layers size={11} /> {isOpen ? 'Less' : 'Spec'}</button>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-slate-400">{b.description}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {b.engine_list.map((e) => <span key={e} className="chip font-mono" style={{ color: engineColor(e), borderColor: `${engineColor(e)}33` }}>{e}</span>)}
              </div>
              {isOpen && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-2 space-y-2 overflow-hidden border-t border-white/5 pt-2">
                  {b.fallback_engine_list.length > 0 && (
                    <div className="text-[10px] text-slate-500">Re-plan fallbacks: {b.fallback_engine_list.map((e) => <span key={e} className="mr-1 font-mono text-slate-300">{e}</span>)}</div>
                  )}
                  <div className="space-y-1">
                    <div className="text-[9.5px] uppercase tracking-wider text-slate-500">Decision dimensions</div>
                    {dims.map(([k, d]) => (
                      <div key={k} className="flex items-center gap-2 text-[10px]">
                        <span className="w-24 shrink-0 truncate text-slate-400">{d.label} {d.direction === 'min' ? '↓' : '↑'}</span>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                          <motion.div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-cyan-400" initial={{ width: 0 }} animate={{ width: `${d.weight * 100}%` }} transition={{ type: 'spring', stiffness: 110, damping: 18 }} />
                        </div>
                        <span className="w-8 text-right font-mono text-slate-300">{Math.round(d.weight * 100)}%</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1 text-[10px] text-slate-500">Actions: {b.actions.map((a) => <span key={a} className="chip font-mono">{a}</span>)}</div>
                </motion.div>
              )}
              <div className="mt-2 space-y-1">
                {b.examples.slice(0, 2).map((ex) => (
                  <button key={ex} onClick={() => onRun(ex, b.lens)} className="group flex w-full items-center gap-1.5 rounded-lg border border-white/5 px-2 py-1 text-left text-[10.5px] text-slate-300 transition hover:border-violet-400/40 hover:text-white">
                    <Play size={10} className="shrink-0 text-violet-300 transition group-hover:translate-x-0.5" /> <span className="truncate">{ex}</span>
                  </button>
                ))}
              </div>
            </motion.article>
          )
        })}
        {shown.length === 0 && <div className="col-span-full py-8 text-center text-xs text-slate-500">No playbook matches “{q}”.</div>}
      </div>
    </section>
  )
}

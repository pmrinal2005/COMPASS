'use client'

import { motion } from 'framer-motion'
import { Target } from 'lucide-react'
import type { SessionState } from '@/lib/types'
import { cn } from '@/lib/utils'

/** Orchestrator intent classification: dense (embedding cosine) ⊕ keyword score per Playbook, winner highlighted. */
export function IntentBars({ s }: { s: SessionState }) {
  const it = s.intent
  const scores = [...(it?.scores || [])].sort((a, b) => b.score - a.score)
  const max = Math.max(1, ...scores.map((x) => x.score))
  const backend = scores[0]?.vector_backend
  return (
    <section className="panel flex h-full flex-col p-4" id={`intent-bars-${s.lens}`}>
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="panel-title"><Target size={13} /> Intent classification</h3>
        {backend && <span className="chip font-mono" title="where the Playbook-library cosine was computed">{backend === 'local' ? 'in-process cosine' : `${backend} · match_playbooks`}</span>}
      </header>
      {scores.length === 0 ? (
        <div className="grid flex-1 place-items-center py-6 text-xs text-slate-500">The Orchestrator scores the prompt against the Playbook library.</div>
      ) : (
        <ul className="stagger space-y-2" aria-label="playbook match scores">
          {scores.slice(0, 6).map((x, i) => {
            const win = x.id === it?.playbook_id
            return (
              <li key={x.id} className={cn('rounded-lg border px-2.5 py-1.5', win ? 'border-violet-400/40 bg-violet-400/[0.07]' : 'border-white/5 bg-white/[0.015]')}>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className={cn('min-w-0 flex-1 truncate', win ? 'font-semibold text-violet-100' : 'text-slate-400')} title={x.name}>{x.name}</span>
                  {win && <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} className="chip border-violet-400/40 text-violet-200">selected</motion.span>}
                  <span className="w-10 text-right font-mono text-slate-300">{x.score.toFixed(2)}</span>
                </div>
                <div className="relative mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                  <motion.div className="absolute inset-y-0 left-0 rounded-full" initial={{ width: 0 }} animate={{ width: `${(x.score / max) * 100}%` }}
                    transition={{ type: 'spring', stiffness: 110, damping: 20, delay: i * 0.06 }}
                    style={{ background: win ? 'linear-gradient(90deg,#a78bfa,#22d3ee)' : '#475569' }} />
                </div>
                <div className="mt-0.5 flex gap-3 font-mono text-[9.5px] text-slate-500">
                  <span title="embedding cosine similarity">cos {x.cosine.toFixed(2)}</span>
                  <span title="keyword hits in the prompt">{x.keyword_hits} kw</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

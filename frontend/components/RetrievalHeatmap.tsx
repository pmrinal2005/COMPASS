'use client'

import { motion } from 'framer-motion'
import { Database, Flame } from 'lucide-react'
import type { SessionState } from '@/lib/types'
import { engineColor, pct } from '@/lib/utils'

/** Retrieval heat-map: fresh web pull vs cached dedupe hit per call, plus hybrid (dense+FTS, RRF) RAG hits. */
export function RetrievalHeatmap({ s }: { s: SessionState }) {
  const calls = s.callOrder.map((id) => s.calls[id]).filter(Boolean)
  const fresh = calls.filter((c) => c.status === 'done').length
  const cached = calls.filter((c) => c.status === 'cached').length
  const hits = s.rag?.hits || []
  const maxRrf = Math.max(...hits.map((h) => h.rrf || 0), 0.0001)
  const v = s.verification

  return (
    <section className="panel flex h-full flex-col p-4" id="retrieval-heatmap">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="panel-title"><Database size={13} /> Retrieval heat-map</h3>
        <span className="chip font-mono">{s.rag?.backend || 'pgvector'} · {s.rag?.embedder || '—'}</span>
      </header>

      <div className="mb-3 grid grid-cols-3 gap-2 text-center">
        <Stat label="Fresh web pulls" value={fresh} color="#22d3ee" />
        <Stat label="Cached (dedupe)" value={cached} color="#fbbf24" />
        <Stat label="Verified ≥2 src" value={v ? `${v.verified}/${v.total}` : '—'} color="#34d399" sub={v ? pct(v.ratio) : undefined} />
      </div>

      <div className="mb-3 flex flex-wrap gap-1" aria-label="call cells">
        {calls.map((c) => (
          <motion.div
            key={c.id}
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            title={`${c.engine} · ${c.status}${c.ms ? ` · ${c.ms}ms` : ''}`}
            className="h-5 w-5 rounded"
            style={{
              background:
                c.status === 'cached' ? '#fbbf24' : c.status === 'done' ? '#22d3ee' : c.status === 'error' ? '#f43f5e' : c.status === 'inflight' ? '#22d3ee55' : '#1e293b',
              boxShadow: c.status === 'inflight' ? '0 0 10px #22d3ee' : undefined,
            }}
          />
        ))}
        {calls.length === 0 && <span className="text-[11px] text-slate-600">No calls yet.</span>}
      </div>

      <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500">
        <Flame size={11} /> Hybrid RAG hits (dense ⊕ full-text, RRF) · {s.rag?.indexed ?? 0} indexed
      </div>
      <div className="scroll-thin flex-1 space-y-1 overflow-auto pr-1">
        {hits.slice(0, 12).map((h, i) => {
          const w = (h.rrf || 0) / maxRrf
          return (
            <div key={i} className="relative overflow-hidden rounded-md border border-white/5 px-2 py-1">
              <motion.div
                className="absolute inset-y-0 left-0"
                initial={{ width: 0 }}
                animate={{ width: `${w * 100}%` }}
                style={{ background: `linear-gradient(90deg, ${engineColor(h.engine)}40, transparent)` }}
              />
              <div className="relative flex items-center gap-2 text-[10.5px]">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: engineColor(h.engine) }} />
                <span className="min-w-0 flex-1 truncate text-slate-200">{h.title}</span>
                <span className="font-mono text-slate-500">d{h.dense_rank ?? '–'} k{h.keyword_rank ?? '–'}</span>
                <span className="w-12 text-right font-mono text-slate-300">{(h.rrf || 0).toFixed(3)}</span>
              </div>
            </div>
          )
        })}
        {hits.length === 0 && <div className="text-[11px] text-slate-600">Vector index fills after the first fan-out.</div>}
      </div>
    </section>
  )
}

function Stat({ label, value, color, sub }: { label: string; value: any; color: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] py-1.5">
      <div className="text-lg font-bold" style={{ color }}>{value}</div>
      <div className="text-[9.5px] uppercase tracking-wider text-slate-500">{label}{sub ? ` · ${sub}` : ''}</div>
    </div>
  )
}

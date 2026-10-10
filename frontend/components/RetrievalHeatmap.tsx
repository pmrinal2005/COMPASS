'use client'

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, Database, Flame, Layers, Search as SearchIcon, Sparkles } from 'lucide-react'
import type { RagHit, SessionState } from '@/lib/types'
import { engineColor, pct } from '@/lib/utils'
import { AnimatedNumber } from './AnimatedNumber'

/** similarity buckets for the engine × similarity density matrix (cosine similarity of the dense retriever, 0‥1) */
const BINS = [
  { label: '<.1', lo: -Infinity, hi: 0.1 },
  { label: '.1–.2', lo: 0.1, hi: 0.2 },
  { label: '.2–.3', lo: 0.2, hi: 0.3 },
  { label: '.3–.5', lo: 0.3, hi: 0.5 },
  { label: '≥.5', lo: 0.5, hi: Infinity },
]
const binOf = (sim: number) => BINS.findIndex((b) => sim >= b.lo && sim < b.hi)

/** which retriever surfaced the hit: dense (vector), keyword (Postgres full-text) or both (the strongest hybrid signal) */
const kindOf = (h: RagHit): 'both' | 'dense' | 'keyword' | 'none' =>
  h.dense_rank != null && h.keyword_rank != null ? 'both' : h.dense_rank != null ? 'dense' : h.keyword_rank != null ? 'keyword' : 'none'

/** Retrieval heat-map: fresh web pull vs cached dedupe hit per call, plus hybrid (dense+FTS, RRF) RAG activity, a similarity-density matrix,
 *  live skeleton loaders while the vector index is still filling, and indexed-chunk preview chips once it has. */
export function RetrievalHeatmap({ s }: { s: SessionState }) {
  const calls = s.callOrder.map((id) => s.calls[id]).filter(Boolean)
  const fresh = calls.filter((c) => c.status === 'done').length
  const cached = calls.filter((c) => c.status === 'cached').length
  const inflight = calls.filter((c) => c.status === 'inflight').length
  const pending = calls.filter((c) => c.status === 'pending').length
  const pulled = calls.reduce((n, c) => n + (c.results || 0), 0)
  const hits = useMemo(() => s.rag?.hits ?? [], [s.rag?.hits])
  const v = s.verification
  const active = s.status === 'running' || s.status === 'connecting' || s.status === 'awaiting_budget'
  // RAG is "searching" while a session runs and the retrieval event has not landed yet
  const searching = active && !s.rag
  const idle = !active && !s.rag && calls.length === 0

  // what the index is made of: SerpApi results pulled per engine (available as soon as the first call answers)
  const composition = useMemo(() => {
    const by = new Map<string, { n: number; calls: number; cached: number }>()
    calls.forEach((c) => {
      if (c.status !== 'done' && c.status !== 'cached') return
      const e = by.get(c.engine) || { n: 0, calls: 0, cached: 0 }
      e.n += c.results || 0; e.calls += 1; if (c.status === 'cached') e.cached += 1
      by.set(c.engine, e)
    })
    const rows = [...by.entries()].map(([engine, v]) => ({ engine, ...v })).sort((a, b) => b.n - a.n)
    return { rows, max: Math.max(1, ...rows.map((r) => r.n)) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.calls, s.callOrder])

  const stats = useMemo(() => {
    const maxRrf = Math.max(...hits.map((h) => h.rrf || 0), 0.0001)
    const kinds = { both: 0, dense: 0, keyword: 0, none: 0 }
    hits.forEach((h) => { kinds[kindOf(h)]++ })
    const sims = hits.map((h) => h.similarity).filter((x): x is number => typeof x === 'number')
    const engines = Array.from(new Set(hits.map((h) => h.engine)))
    // matrix[engine][bin] = hit count
    const matrix = engines.map((e) => {
      const row = BINS.map(() => 0)
      hits.filter((h) => h.engine === e && typeof h.similarity === 'number').forEach((h) => { const b = binOf(h.similarity as number); if (b >= 0) row[b]++ })
      return { engine: e, row, total: hits.filter((h) => h.engine === e).length }
    })
    const hist = BINS.map((_, i) => sims.filter((x) => binOf(x) === i).length)
    return {
      maxRrf, kinds, engines, matrix, hist,
      maxCell: Math.max(1, ...matrix.flatMap((m) => m.row)),
      maxHist: Math.max(1, ...hist),
      top: sims.length ? Math.max(...sims) : null,
      avg: sims.length ? sims.reduce((a, b) => a + b, 0) / sims.length : null,
      hasSim: sims.length > 0,
    }
  }, [hits])


  const Composition = ({ title }: { title: string }) => composition.rows.length === 0 ? null : (
    <div>
      <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><BarChart3 size={11} /> {title}</div>
      <div className="space-y-1">
        {composition.rows.slice(0, 8).map((r, i) => (
          <div key={r.engine} className="flex items-center gap-2 text-[10.5px]" title={`${r.engine}: ${r.n} results from ${r.calls} call${r.calls === 1 ? '' : 's'}${r.cached ? ` (${r.cached} cached)` : ''}`}>
            <span className="w-24 shrink-0 truncate font-mono" style={{ color: engineColor(r.engine) }}>{r.engine}</span>
            <div className="relative h-3 flex-1 overflow-hidden rounded bg-white/[0.05]">
              <motion.div className="absolute inset-y-0 left-0 rounded" style={{ background: `linear-gradient(90deg, ${engineColor(r.engine)}99, ${engineColor(r.engine)}33)` }}
                initial={{ width: 0 }} animate={{ width: `${(r.n / composition.max) * 100}%` }} transition={{ duration: 0.6, delay: i * 0.04 }} />
            </div>
            <span className="w-8 text-right font-mono text-slate-300">{r.n}</span>
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <section className="panel flex h-full flex-col p-4" id="retrieval-heatmap">
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="panel-title"><Database size={13} /> Retrieval heat-map</h3>
        <span className="chip font-mono" title="vector backend · embedder">
          {searching && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />}
          {s.rag?.backend || 'pgvector'} · {s.rag?.embedder || (searching ? 'embedding…' : '—')}
        </span>
      </header>

      <div className="mb-2 grid grid-cols-3 gap-2 text-center">
        <Stat label="Fresh web pulls" value={fresh} color="#22d3ee" />
        <Stat label="Cached (dedupe)" value={cached} color="#fbbf24" />
        <Stat label="Verified ≥2 src" value={v ? `${v.verified}/${v.total}` : '—'} color="#34d399" sub={v ? pct(v.ratio) : undefined} loading={searching && !v} />
      </div>

      <div className="mb-2 flex flex-wrap gap-1" aria-label="call cells">
        {calls.map((c) => (
          <motion.div
            key={c.id}
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            title={`${c.engine} · ${c.status}${c.ms ? ` · ${c.ms}ms` : ''}`}
            className={`h-4 w-4 rounded ${c.status === 'inflight' ? 'animate-pulse' : ''}`}
            style={{
              background:
                c.status === 'cached' ? '#fbbf24' : c.status === 'done' ? '#22d3ee' : c.status === 'error' ? '#f43f5e' : c.status === 'inflight' ? '#22d3ee55' : '#64748b55',
              boxShadow: c.status === 'inflight' ? '0 0 10px #22d3ee' : undefined,
            }}
          />
        ))}
        {calls.length === 0 && <span className="text-[11px] text-slate-600">No calls yet.</span>}
      </div>

      <div className="scroll-thin min-h-0 flex-1 space-y-3 overflow-auto pr-1">
        {/* ───── 1. nothing has run yet: a self-explaining idle state instead of blank space ───── */}
        {idle && <IdleState />}

        {/* ───── 2. vector search in progress: live counters + skeleton loaders ───── */}
        {searching && calls.length > 0 && (
          <div aria-busy="true" aria-live="polite" className="space-y-2.5">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-cyan-300">
              <SearchIcon size={11} className="animate-pulse" /> Indexing &amp; hybrid search in progress
            </div>
            <div className="grid grid-cols-4 gap-1.5 text-center">
              <Mini label="in flight" value={inflight} color="#22d3ee" />
              <Mini label="queued" value={pending} color="#94a3b8" />
              <Mini label="results pulled" value={pulled} color="#a78bfa" />
              <Mini label="calls done" value={fresh + cached} color="#34d399" />
            </div>
            <div className="skeleton h-2.5 w-full" />
            <div className="grid grid-cols-5 gap-1">{Array.from({ length: 10 }).map((_, i) => <div key={i} className="skeleton h-5" style={{ animationDelay: `${i * 90}ms` }} />)}</div>
            {Composition({ title: 'Results landing in the index (live)' })}
            {[88, 72, 56].map((w, i) => (
              <div key={i} className="skeleton h-5" style={{ width: `${w}%`, animationDelay: `${i * 140}ms` }} />
            ))}
          </div>
        )}

        {/* ───── 3. retrieval finished: stats, density matrix, hits, chunk chips ───── */}
        {s.rag && (
          <>
            <div className="grid grid-cols-4 gap-1.5 text-center">
              <Mini label="chunks indexed" value={s.rag.indexed ?? 0} color="#a78bfa" animate />
              <Mini label="top similarity" value={stats.top} digits={3} color="#34d399" animate />
              <Mini label="avg similarity" value={stats.avg} digits={3} color="#22d3ee" animate />
              <Mini label="hybrid hits" value={hits.length} color="#fbbf24" animate />
            </div>

            {Composition({ title: 'Index composition · results per engine' })}

            <div>
              <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Layers size={11} /> Dense ⊕ full-text breakdown</div>
              <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-white/5" role="img"
                aria-label={`${stats.kinds.both} in both retrievers, ${stats.kinds.dense} dense only, ${stats.kinds.keyword} keyword only`}>
                {([['both', '#34d399'], ['dense', '#a78bfa'], ['keyword', '#fbbf24']] as const).map(([k, col]) => (
                  <motion.div key={k} className="h-full" style={{ background: col }} initial={{ width: 0 }}
                    animate={{ width: `${hits.length ? (stats.kinds[k] / hits.length) * 100 : 0}%` }} transition={{ duration: 0.7, ease: 'easeOut' }} />
                ))}
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-400">
                <Legend color="#34d399" label="both" n={stats.kinds.both} />
                <Legend color="#a78bfa" label="dense only" n={stats.kinds.dense} />
                <Legend color="#fbbf24" label="full-text only" n={stats.kinds.keyword} />
              </div>
            </div>

            {stats.hasSim && stats.matrix.length > 0 && (
              <div>
                <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Flame size={11} /> Hit density · engine × cosine similarity</div>
                <div className="overflow-x-auto">
                  <table className="w-full border-separate text-[10px]" style={{ borderSpacing: 2 }} aria-label="RAG hit density matrix">
                    <thead>
                      <tr>
                        <th className="w-24" />
                        {BINS.map((b) => <th key={b.label} className="px-1 text-center font-mono font-normal text-slate-500">{b.label}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {stats.matrix.map((m, r) => (
                        <tr key={m.engine}>
                          <td className="max-w-[96px] truncate pr-1 font-mono" style={{ color: engineColor(m.engine) }} title={m.engine}>{m.engine}</td>
                          {m.row.map((n, c) => (
                            <td key={c} className="p-0">
                              <motion.div
                                initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: (r * BINS.length + c) * 0.015 }}
                                className="grid h-5 place-items-center rounded font-mono text-[10px]"
                                title={`${m.engine} · similarity ${BINS[c].label} · ${n} hit${n === 1 ? '' : 's'}`}
                                style={{ background: n ? `${engineColor(m.engine)}${Math.round(40 + (n / stats.maxCell) * 180).toString(16).padStart(2, '0')}` : 'rgb(var(--white) / 0.04)' }}
                              >
                                {n || ''}
                              </motion.div>
                            </td>
                          ))}
                        </tr>
                      ))}
                      <tr>
                        <td className="pr-1 text-right font-mono text-slate-500">all</td>
                        {stats.hist.map((n, c) => (
                          <td key={c} className="p-0">
                            <div className="relative h-5 overflow-hidden rounded bg-white/[0.04]" title={`${n} hit(s) at similarity ${BINS[c].label}`}>
                              <motion.div className="absolute inset-x-0 bottom-0 bg-violet-400/60" initial={{ height: 0 }} animate={{ height: `${(n / stats.maxHist) * 100}%` }} transition={{ duration: 0.6 }} />
                              <span className="relative grid h-full place-items-center font-mono text-slate-300">{n || ''}</span>
                            </div>
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div>
              <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500">
                <Flame size={11} /> Hybrid RAG hits (dense ⊕ full-text, RRF) · {s.rag.indexed ?? 0} indexed
              </div>
              <div className="space-y-1">
                {hits.slice(0, 8).map((h, i) => {
                  const w = (h.rrf || 0) / stats.maxRrf
                  return (
                    <div key={i} className="relative overflow-hidden rounded-md border border-white/5 px-2 py-1">
                      <motion.div className="absolute inset-y-0 left-0" initial={{ width: 0 }} animate={{ width: `${w * 100}%` }}
                        style={{ background: `linear-gradient(90deg, ${engineColor(h.engine)}40, transparent)` }} />
                      <div className="relative flex items-center gap-2 text-[10.5px]">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: engineColor(h.engine) }} />
                        <span className="min-w-0 flex-1 truncate text-slate-200">{h.title}</span>
                        {typeof h.similarity === 'number' && <span className="font-mono text-emerald-300" title="cosine similarity">≈{h.similarity.toFixed(2)}</span>}
                        <span className="font-mono text-slate-500">d{h.dense_rank ?? '–'} k{h.keyword_rank ?? '–'}</span>
                        <span className="w-12 text-right font-mono text-slate-300">{(h.rrf || 0).toFixed(3)}</span>
                      </div>
                    </div>
                  )
                })}
                {hits.length === 0 && <div className="rounded-lg border border-dashed border-white/10 p-2 text-[11px] text-slate-500">Index ready · {s.rag.indexed ?? 0} chunks stored. The hybrid query returned no ranked hit above the cut-off, so the Analyst relies on the cross-source verification instead.</div>}
              </div>
            </div>

            {hits.length > 0 && (
              <div>
                <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Sparkles size={11} /> Indexed chunk preview</div>
                <div className="flex flex-wrap gap-1">
                  {hits.slice(0, 14).map((h, i) => (
                    <motion.span key={`${h.candidate_id || h.title}-${i}`} initial={{ opacity: 0, y: 3 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.025 }}
                      className="chip max-w-[170px] gap-1" title={`${h.title} · ${h.engine}`}>
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: engineColor(h.engine) }} />
                      <span className="truncate">{h.title}</span>
                    </motion.span>
                  ))}
                  {(s.rag.indexed ?? 0) > hits.length && <span className="chip font-mono text-slate-400">+{(s.rag.indexed ?? 0) - Math.min(hits.length, 14)} more</span>}
                </div>
              </div>
            )}
          </>
        )}

        {/* a finished session that never produced RAG events (e.g. an error) */}
        {!idle && !searching && !s.rag && calls.length > 0 && (
          <div className="rounded-lg border border-dashed border-white/10 p-3 text-center text-[11px] text-slate-500">
            {active ? 'Waiting for the Researcher to index results…' : 'No vector retrieval ran for this session.'}
          </div>
        )}
      </div>
    </section>
  )
}

function IdleState() {
  const steps = [
    ['1', 'SerpApi fan-out', 'results are normalised into chunks'],
    ['2', 'Embed + index', 'chunks land in the pgvector store'],
    ['3', 'Hybrid retrieval', 'dense ⊕ Postgres full-text, fused by RRF'],
  ]
  return (
    <div className="space-y-3">
      <p className="text-[11px] leading-relaxed text-slate-400">Run a prompt and this card lights up with live RAG activity: how many chunks were indexed, how well they match, and which retriever found them.</p>
      <ol className="space-y-1.5">
        {steps.map(([n, t, d]) => (
          <li key={n} className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-violet-400/20 font-mono text-[10px] text-violet-300">{n}</span>
            <span className="font-semibold text-slate-200">{t}</span><span className="truncate text-slate-500">{d}</span>
          </li>
        ))}
      </ol>
      <div aria-hidden className="grid grid-cols-10 gap-1 opacity-70">
        {Array.from({ length: 20 }).map((_, i) => <div key={i} className="h-4 rounded bg-white/[0.04]" />)}
      </div>
      <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-500">
        <span className="chip">similarity matrix</span><span className="chip">dense vs full-text split</span><span className="chip">chunk previews</span>
      </div>
    </div>
  )
}

function Legend({ color, label, n }: { color: string; label: string; n: number }) {
  return <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: color }} />{label} <b className="font-mono text-slate-200">{n}</b></span>
}

function Mini({ label, value, color, digits = 0, animate = false }: { label: string; value: number | null | undefined; color: string; digits?: number; animate?: boolean }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] py-1">
      <div className="font-mono text-sm font-bold" style={{ color }}>
        {animate ? <AnimatedNumber value={value} digits={digits} duration={0.6} /> : value == null ? '—' : value.toFixed(digits)}
      </div>
      <div className="text-[8.5px] uppercase tracking-wider text-slate-500">{label}</div>
    </div>
  )
}

function Stat({ label, value, color, sub, loading }: { label: string; value: any; color: string; sub?: string; loading?: boolean }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] py-1.5">
      {loading ? <div className="skeleton mx-auto my-1 h-5 w-10" aria-label="loading" /> : <div className="text-lg font-bold" style={{ color }}>{value}</div>}
      <div className="text-[9.5px] uppercase tracking-wider text-slate-500">{label}{sub ? ` · ${sub}` : ''}</div>
    </div>
  )
}

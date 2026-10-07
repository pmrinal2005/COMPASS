'use client'

import { useEffect, useState } from 'react'
import { ExternalLink, Layers, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { SessionState } from '@/lib/types'
import { engineColor } from '@/lib/utils'

/** "Raw calls" tab — every SerpApi engine response + agent spans, read back from Langfuse Cloud (or local spans). */
export function RawCalls({ s }: { s: SessionState }) {
  const [trace, setTrace] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const responses = s.logs.filter((l) => l.kind === 'response' || l.kind === 'cached')

  const load = async () => {
    if (!s.sessionId || s.replay) return
    setLoading(true)
    try {
      setTrace(await api.trace(s.sessionId))
    } catch {
      setTrace(null)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    if (s.status === 'done') load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.status, s.sessionId])

  const spans: any[] = trace?.spans || []
  return (
    <section className="panel p-4" id="raw-calls">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="panel-title"><Layers size={13} /> Raw calls · trace viewer</h3>
        <span className="chip">{s.replay ? 'offline recording' : trace?.source === 'langfuse-cloud' ? 'Langfuse Cloud' : 'local spans'}</span>
        {trace?.trace_url && (
          <a href={trace.trace_url} target="_blank" rel="noreferrer" className="btn-ghost ml-auto">Open in Langfuse <ExternalLink size={11} /></a>
        )}
        {!s.replay && <button onClick={load} className="btn-ghost" disabled={loading}><RefreshCw size={11} className={loading ? 'animate-spin' : ''} /> Refresh</button>}
      </header>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="scroll-thin max-h-[420px] space-y-2 overflow-auto">
          {responses.length === 0 && <div className="text-xs text-slate-500">No SerpApi responses yet.</div>}
          {responses.map((l) => (
            <details key={l.seq} className="rounded-lg border border-white/5 bg-black/30">
              <summary className="cursor-pointer px-3 py-1.5 font-mono text-[11px]">
                <span style={{ color: engineColor(l.engine) }}>{l.engine}</span>{' '}
                <span className="text-slate-500">{l.kind === 'cached' ? 'cache hit' : `${l.status} · ${l.results} results · ${l.ms}ms`}</span>
              </summary>
              <pre className="scroll-thin max-h-72 overflow-auto px-3 pb-2 text-[10px] text-slate-300">{JSON.stringify(l.raw ?? { cached: true, params: l.params }, null, 2)}</pre>
            </details>
          ))}
        </div>
        <div className="scroll-thin max-h-[420px] overflow-auto rounded-lg border border-white/5 bg-black/30 p-2 font-mono text-[10.5px]">
          {s.replay && <div className="text-slate-500">Connect a backend (NEXT_PUBLIC_API_URL) to read spans from Langfuse Cloud.</div>}
          {!s.replay && spans.length === 0 && <div className="text-slate-500">{loading ? 'Loading spans…' : 'Spans appear when the session completes.'}</div>}
          {spans.map((sp, i) => (
            <div key={sp.id || i} className="flex gap-2 border-b border-white/[0.03] py-0.5">
              <span className={sp.kind === 'generation' ? 'text-violet-300' : 'text-cyan-300'}>{sp.kind === 'generation' ? 'GEN ' : 'SPAN'}</span>
              <span className="text-slate-200">{sp.name}</span>
              <span className="ml-auto truncate text-slate-500">{JSON.stringify(sp.output ?? '').slice(0, 70)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

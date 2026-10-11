'use client'

import { GitFork, Zap } from 'lucide-react'
import type { SessionState } from '@/lib/types'
import { cn, engineColor } from '@/lib/utils'

const ROUTED_BY: Record<string, string> = {
  strong_keyword: 'strong keyword',
  weak_keyword: 'weak keyword',
  llm_router: 'LLM router',
  llm_validated: 'LLM validated',
  fallback: 'general fallback',
}

/** Orchestrator `orchestrator.routing` event: intent category, why this Playbook won, recency/entity/market signals,
 *  the planned engine fan-out (FRESH calls bypass the dedupe cache), and any recency weight override. */
export function RoutingPanel({ s }: { s: SessionState }) {
  const r = s.routing
  const a = r?.analysis
  return (
    <section className="panel p-4" id={`routing-${s.lens}`}>
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="panel-title"><GitFork size={13} /> Intent → Playbook routing</h3>
        {r?.routed_by && (
          <span className="chip font-mono" title={r.reason || ''}>{ROUTED_BY[r.routed_by] || r.routed_by}</span>
        )}
      </header>
      {!r ? (
        <div className="py-2 text-xs text-slate-500">The Orchestrator routes the prompt to one Playbook (strong keyword → weak keyword → Groq LLM → general fallback).</div>
      ) : (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
            <span className="chip border-cyan-400/40 text-cyan-200">{r.intent_category}</span>
            <span className="text-slate-500">→</span>
            <span className="font-semibold text-violet-100" title={r.playbook_id}>{r.playbook}</span>
            {r.confidence != null && <span className="chip font-mono">conf {Number(r.confidence).toFixed(2)}</span>}
            {r.strong_hits != null && r.strong_hits > 0 && <span className="chip font-mono" title="strong keyword hits">{r.strong_hits} strong</span>}
            {r.calls != null && r.max_calls != null && <span className="ml-auto font-mono text-[10px] text-slate-500">{r.calls}/{r.max_calls} calls</span>}
          </div>
          {a && (
            <div className="flex flex-wrap items-center gap-1.5 text-[10.5px]">
              {a.recency && (
                <span className={cn('chip font-mono', a.fresh_strong ? 'border-emerald-400/50 text-emerald-200' : 'text-slate-300')} title="recency signal in the prompt">
                  <Zap size={10} className={a.fresh_strong ? 'text-emerald-300' : 'text-slate-400'} /> {a.recency}{a.fresh_strong ? ' · live' : ''}
                </span>
              )}
              {a.entity && <span className="chip" title="extracted entity">◉ {a.entity}</span>}
              {a.market && <span className="chip" title="market / locale">◈ {a.market}</span>}
              {a.media_kind && <span className="chip" title="media kind">▶ {a.media_kind}</span>}
              {a.travel_origin && <span className="chip" title="trip origin">✈ {a.travel_origin}</span>}
              {a.app_query && <span className="chip" title="app query">▣ {a.app_query}</span>}
            </div>
          )}
          {(r.engines?.length || r.skipped_optional?.length) ? (
            <div className="flex flex-wrap items-center gap-1" aria-label="planned engines">
              {(r.engines || []).map((e) => {
                const fresh = r.fresh?.includes(e)
                return (
                  <span key={e} className={cn('chip font-mono', fresh && 'border-emerald-400/50 text-emerald-200')}
                    style={fresh ? undefined : { color: engineColor(e) }} title={fresh ? `${e} · FRESH: bypasses the dedupe cache` : e}>
                    {fresh && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}{e}
                  </span>
                )
              })}
              {(r.skipped_optional || []).map((e) => (
                <span key={e} className="chip font-mono opacity-40 line-through" title={`${e} · optional engine skipped (trigger off)`}>{e}</span>
              ))}
            </div>
          ) : null}
          {r.weight_override && (
            <div className="text-[10.5px] text-slate-400" title={r.weight_override.reason}>
              ⚖ weight override: <span className="font-mono text-slate-200">{r.weight_override.dimension}</span>{' '}
              <span className="font-mono">{Number(r.weight_override.from).toFixed(2)} → {Number(r.weight_override.to).toFixed(2)}</span>{' '}
              <span className="text-slate-500">({r.weight_override.reason})</span>
            </div>
          )}
          {r.llm_router && typeof r.llm_router === 'object' && (r.llm_router.used || r.llm_router.verdict) && (
            <div className="text-[10.5px] text-slate-500" title={JSON.stringify(r.llm_router)}>
              🤖 LLM router: {r.llm_router.agree === false ? 'overrode the keyword winner' : 'agreed with keyword ranking'}
              {r.llm_router.latency_ms != null ? ` · ${r.llm_router.latency_ms}ms` : ''}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

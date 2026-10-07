'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Search, BarChart3, Bot, Network } from 'lucide-react'
import type { AgentName, SessionState } from '@/lib/types'
import { AGENT_META, cn, engineColor } from '@/lib/utils'

const ICONS: Record<AgentName, any> = { orchestrator: Brain, researcher: Search, analyst: BarChart3, actor: Bot }
const ORDER: AgentName[] = ['orchestrator', 'researcher', 'analyst', 'actor']

export function AgentRail({ s }: { s: SessionState }) {
  return (
    <div className="grid grid-cols-4 gap-2" id="agent-rail">
      {ORDER.map((a) => {
        const Icon = ICONS[a]
        const st = s.agents[a]
        const meta = AGENT_META[a]
        return (
          <div
            key={a}
            className={cn(
              'relative overflow-hidden rounded-xl border px-3 py-2 transition',
              st === 'active' ? 'border-white/20 bg-white/[0.06]' : 'border-white/[0.06] bg-white/[0.02]',
            )}
          >
            {st === 'active' && (
              <motion.div
                layoutId={`glow-${s.lens}`}
                className="absolute inset-0 -z-0 opacity-30"
                style={{ background: `radial-gradient(120% 120% at 0% 0%, ${meta.color}55, transparent 60%)` }}
              />
            )}
            <div className="relative flex items-center gap-2">
              <span className="relative grid h-7 w-7 place-items-center rounded-lg" style={{ background: `${meta.color}22`, color: meta.color }}>
                <Icon size={15} />
                {st === 'active' && <span className="absolute inset-0 animate-pulse-ring rounded-lg" style={{ boxShadow: `0 0 0 2px ${meta.color}` }} />}
              </span>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-100">{meta.label}</div>
                <div className="truncate text-[10px] text-slate-500">{s.agentLabel[a] || meta.role}</div>
              </div>
              <span
                className={cn('ml-auto h-1.5 w-1.5 rounded-full', st === 'active' ? 'animate-pulse' : '')}
                style={{ background: st === 'idle' ? '#334155' : st === 'active' ? meta.color : '#10b981' }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

const STATUS_COLOR: Record<string, string> = {
  pending: '#475569',
  inflight: '#22d3ee',
  done: '#34d399',
  cached: '#fbbf24',
  error: '#f43f5e',
}

/** Animated Decision-Graph / thought-tree: Orchestrator → typed nodes → SerpApi sources → Analyst → Actor. */
export function ThoughtTree({ s }: { s: SessionState }) {
  const g = s.graph
  const calls = s.callOrder.map((id) => s.calls[id]).filter(Boolean)
  const W = 560
  const colX = { root: 60, src: 280, an: 470 }
  const rowH = 30
  const H = Math.max(230, calls.length * rowH + 60)
  const srcY = (i: number) => 40 + i * rowH
  const rootY = H / 2
  const nodes = g?.nodes || []
  const ents = nodes.filter((n) => n.kind === 'entity').slice(0, 6)
  const dims = nodes.filter((n) => n.kind === 'dimension')
  const cons = nodes.filter((n) => n.kind === 'constraint')

  return (
    <section className="panel flex h-full flex-col p-4" id="thought-tree">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="panel-title"><Network size={13} /> Decision graph · thought-tree</h3>
        {s.intent && <span className="chip" style={{ color: '#c4b5fd' }}>{s.intent.playbook}</span>}
      </header>

      {!g ? (
        <div className="grid flex-1 place-items-center text-xs text-slate-500">
          {s.status === 'connecting' || s.status === 'running' ? 'Orchestrator is classifying intent…' : 'Run a prompt to grow the decision graph.'}
        </div>
      ) : (
        <>
          <div className="mb-2 flex flex-wrap gap-1">
            {ents.map((n) => (
              <motion.span key={n.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="chip border-violet-400/20 text-violet-200">
                {n.label}
              </motion.span>
            ))}
            {cons.map((n) => (
              <span key={n.id} className="chip border-rose-400/20 text-rose-200">⛓ {n.label}</span>
            ))}
          </div>
          <div className="scroll-thin relative flex-1 overflow-auto">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minHeight: 220 }}>
              <defs>
                <linearGradient id={`edge-${s.lens}`} x1="0" x2="1">
                  <stop offset="0" stopColor="#a78bfa" stopOpacity="0.7" />
                  <stop offset="1" stopColor="#22d3ee" stopOpacity="0.7" />
                </linearGradient>
              </defs>
              {/* edges root -> sources -> analyst */}
              {calls.map((c, i) => {
                const y = srcY(i)
                const live = c.status === 'inflight'
                const col = STATUS_COLOR[c.status]
                return (
                  <g key={c.id}>
                    <motion.path
                      d={`M${colX.root + 40},${rootY} C${colX.root + 130},${rootY} ${colX.src - 110},${y} ${colX.src - 6},${y}`}
                      fill="none"
                      stroke={c.round > 0 ? '#f472b6' : `url(#edge-${s.lens})`}
                      strokeWidth={live ? 1.8 : 1.1}
                      strokeDasharray={live ? '4 4' : undefined}
                      className={live ? 'animate-dash' : ''}
                      initial={{ pathLength: 0, opacity: 0 }}
                      animate={{ pathLength: 1, opacity: c.status === 'pending' ? 0.35 : 0.85 }}
                      transition={{ duration: 0.6, delay: i * 0.04 }}
                    />
                    {(c.status === 'done' || c.status === 'cached') && (
                      <motion.path
                        d={`M${colX.src + 150},${y} C${colX.an - 60},${y} ${colX.an - 80},${rootY} ${colX.an - 30},${rootY}`}
                        fill="none"
                        stroke={col}
                        strokeOpacity={0.55}
                        strokeWidth={1}
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: 0.5 }}
                      />
                    )}
                    <motion.g initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
                      <rect x={colX.src - 6} y={y - 11} width={156} height={22} rx={6} fill="#0d1020" stroke={col} strokeOpacity={0.7} />
                      <circle cx={colX.src + 5} cy={y} r={3.5} fill={engineColor(c.engine)} />
                      <text x={colX.src + 14} y={y + 3.5} fontSize={9.5} fill="#e2e8f0" fontFamily="var(--font-mono)">
                        {c.engine.length > 18 ? c.engine.slice(0, 17) + '…' : c.engine}
                      </text>
                      <text x={colX.src + 146} y={y + 3.5} fontSize={8} textAnchor="end" fill={col} fontFamily="var(--font-mono)">
                        {c.status === 'cached' ? 'CACHE' : c.status === 'done' ? `${c.ms ?? ''}ms` : c.status === 'inflight' ? '…' : c.status === 'error' ? 'ERR' : ''}
                      </text>
                    </motion.g>
                  </g>
                )
              })}
              {/* root orchestrator */}
              <g>
                <circle cx={colX.root} cy={rootY} r={34} fill="#a78bfa22" stroke="#a78bfa" />
                <text x={colX.root} y={rootY - 2} fontSize={10} textAnchor="middle" fill="#ede9fe" fontWeight={600}>Orchestrator</text>
                <text x={colX.root} y={rootY + 11} fontSize={8} textAnchor="middle" fill="#a78bfa">{g.playbook_id}</text>
              </g>
              {/* analyst sink */}
              <g>
                <circle cx={colX.an} cy={rootY} r={30} fill="#fbbf2418" stroke={s.matrix ? '#fbbf24' : '#475569'} />
                <text x={colX.an} y={rootY - 2} fontSize={10} textAnchor="middle" fill="#fef3c7" fontWeight={600}>Analyst</text>
                <text x={colX.an} y={rootY + 11} fontSize={8} textAnchor="middle" fill="#fbbf24">
                  {s.confidence !== undefined ? `conf ${Math.round(s.confidence * 100)}%` : `${dims.length} dims`}
                </text>
              </g>
              {s.replans.length > 0 && (
                <path
                  d={`M${colX.an},${rootY - 30} C${colX.an - 40},${8} ${colX.root + 40},${8} ${colX.root},${rootY - 34}`}
                  fill="none" stroke="#f472b6" strokeDasharray="5 4" className="animate-dash" strokeWidth={1.3}
                />
              )}
            </svg>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {dims.map((d) => (
              <span key={d.id} className="chip border-amber-400/20 text-amber-200">
                {d.label} · {Math.round((d.meta?.weight || 0) * 100)}%
              </span>
            ))}
          </div>
          <AnimatePresence>
            {s.replans.map((r) => (
              <motion.div key={r.iteration} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                className="mt-2 rounded-lg border border-pink-400/30 bg-pink-500/10 px-3 py-1.5 text-[11px] text-pink-100">
                ↺ Re-plan {r.iteration}/{r.max ?? 2}: {r.reasons?.[0] || 'low confidence'} → {r.new_calls.map((c) => c.engine).join(', ')}
              </motion.div>
            ))}
          </AnimatePresence>
        </>
      )}
    </section>
  )
}

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Search, BarChart3, Bot, Network, Maximize2, X } from 'lucide-react'
import type { AgentName, SessionState } from '@/lib/types'
import { AGENT_META, cn, engineColor } from '@/lib/utils'
import { PanZoom } from './PanZoom'

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
const ROW_H = 30

/** Pure SVG renderer of the decision graph. `detailed` (used by the full-screen modal) additionally draws the entity / constraint inputs,
 *  the weighted dimension nodes and the Actor node, so a large execution tree is worth panning around. */
function TreeSvg({ s, detailed = false, svgClass = 'w-full', fixed = false }: { s: SessionState; detailed?: boolean; svgClass?: string; fixed?: boolean }) {
  const g = s.graph!
  const calls = s.callOrder.map((id) => s.calls[id]).filter(Boolean)
  const nodes = g.nodes || []
  const ents = nodes.filter((n) => n.kind === 'entity').slice(0, detailed ? 8 : 6)
  const dims = nodes.filter((n) => n.kind === 'dimension')
  const cons = nodes.filter((n) => n.kind === 'constraint').slice(0, detailed ? 6 : 99)
  const inputs = [...ents.map((n) => ({ n, c: '#a78bfa' })), ...cons.map((n) => ({ n, c: '#fb7185' }))]

  const colX = detailed ? { ent: 16, root: 262, src: 430, an: 712, dim: 800 } : { ent: 0, root: 60, src: 280, an: 470, dim: 0 }
  const W = detailed ? 990 : 560
  const rows = Math.max(calls.length, detailed ? inputs.length : 0, detailed ? dims.length : 0, 1)
  const H = detailed ? Math.max(300, rows * ROW_H + 90) : Math.max(230, calls.length * ROW_H + 60)
  const rootY = H / 2
  const yAt = (i: number, n: number) => rootY + (i - (n - 1) / 2) * ROW_H
  const nActions = s.actionOrder.length

  return (
    <svg viewBox={`0 0 ${W} ${H}`} {...(fixed ? { width: W, height: H } : {})} className={svgClass} style={fixed ? undefined : { minHeight: 220 }} role="img" aria-label="Decision graph">
      <defs>
        <linearGradient id={`edge-${s.lens}${detailed ? '-d' : ''}`} x1="0" x2="1">
          <stop offset="0" stopColor="#a78bfa" stopOpacity="0.7" />
          <stop offset="1" stopColor="#22d3ee" stopOpacity="0.7" />
        </linearGradient>
      </defs>

      {/* inputs -> orchestrator (detailed only) */}
      {detailed && inputs.map(({ n, c }, i) => {
        const y = yAt(i, inputs.length)
        return (
          <g key={n.id}>
            <motion.path d={`M${colX.ent + 150},${y} C${colX.ent + 200},${y} ${colX.root - 80},${rootY} ${colX.root - 34},${rootY}`} fill="none" stroke={c} strokeOpacity={0.5} strokeWidth={1}
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: i * 0.03 }} />
            <motion.g initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
              <rect x={colX.ent} y={y - 11} width={150} height={22} rx={6} className="fill-node" stroke={c} strokeOpacity={0.6} />
              <text x={colX.ent + 8} y={y + 3.5} fontSize={9.5} className="fill-slate-200" fontFamily="var(--font-mono)">
                {(n.kind === 'constraint' ? '⛓ ' : '') + (n.label.length > 22 ? n.label.slice(0, 21) + '…' : n.label)}
              </text>
            </motion.g>
          </g>
        )
      })}

      {/* edges root -> sources -> analyst */}
      {calls.map((c, i) => {
        const y = yAt(i, calls.length)
        const live = c.status === 'inflight'
        const col = STATUS_COLOR[c.status]
        return (
          <g key={c.id}>
            <motion.path
              d={`M${colX.root + 40},${rootY} C${colX.root + 130},${rootY} ${colX.src - 110},${y} ${colX.src - 6},${y}`}
              fill="none"
              stroke={c.round > 0 ? '#f472b6' : `url(#edge-${s.lens}${detailed ? '-d' : ''})`}
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
                fill="none" stroke={col} strokeOpacity={0.55} strokeWidth={1}
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5 }}
              />
            )}
            <motion.g initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
              <rect x={colX.src - 6} y={y - 11} width={156} height={22} rx={6} className="fill-node" stroke={col} strokeOpacity={0.7} />
              <circle cx={colX.src + 5} cy={y} r={3.5} fill={engineColor(c.engine)} />
              <text x={colX.src + 14} y={y + 3.5} fontSize={9.5} className="fill-slate-200" fontFamily="var(--font-mono)">
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
        <text x={colX.root} y={rootY - 2} fontSize={10} textAnchor="middle" className="fill-violet-100" fontWeight={600}>Orchestrator</text>
        <text x={colX.root} y={rootY + 11} fontSize={8} textAnchor="middle" fill="#a78bfa">{g.playbook_id}</text>
      </g>
      {/* analyst sink */}
      <g>
        <circle cx={colX.an} cy={rootY} r={30} fill="#fbbf2418" stroke={s.matrix ? '#fbbf24' : '#475569'} />
        <text x={colX.an} y={rootY - 2} fontSize={10} textAnchor="middle" className="fill-amber-50" fontWeight={600}>Analyst</text>
        <text x={colX.an} y={rootY + 11} fontSize={8} textAnchor="middle" fill="#fbbf24">
          {s.confidence !== undefined ? `conf ${Math.round(s.confidence * 100)}%` : `${dims.length} dims`}
        </text>
      </g>

      {/* dimensions + actor (detailed only) */}
      {detailed && dims.map((d, i) => {
        const y = yAt(i, dims.length)
        return (
          <g key={d.id}>
            <motion.path d={`M${colX.an + 30},${rootY} C${colX.an + 55},${rootY} ${colX.dim - 30},${y} ${colX.dim - 4},${y}`} fill="none" stroke="#fbbf24" strokeOpacity={0.45}
              initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: i * 0.04 }} />
            <rect x={colX.dim - 4} y={y - 11} width={186} height={22} rx={6} className="fill-node" stroke="#fbbf24" strokeOpacity={0.5} />
            <text x={colX.dim + 4} y={y + 3.5} fontSize={9.5} className="fill-amber-200" fontFamily="var(--font-mono)">
              {d.label.length > 20 ? d.label.slice(0, 19) + '…' : d.label}
            </text>
            <text x={colX.dim + 176} y={y + 3.5} fontSize={8.5} textAnchor="end" fill="#fbbf24" fontFamily="var(--font-mono)">{Math.round((d.meta?.weight || 0) * 100)}%</text>
          </g>
        )
      })}
      {detailed && (
        <g>
          <motion.path d={`M${colX.an},${rootY + 30} L${colX.an},${rootY + 62}`} fill="none" stroke="#34d399" strokeWidth={1.2} strokeOpacity={nActions ? 0.9 : 0.35}
            strokeDasharray={s.agents.actor === 'active' ? '4 4' : undefined} className={s.agents.actor === 'active' ? 'animate-dash' : ''} />
          <circle cx={colX.an} cy={rootY + 88} r={26} fill="#34d39918" stroke={nActions ? '#34d399' : '#475569'} />
          <text x={colX.an} y={rootY + 86} fontSize={10} textAnchor="middle" className="fill-emerald-200" fontWeight={600}>Actor</text>
          <text x={colX.an} y={rootY + 98} fontSize={8} textAnchor="middle" fill="#34d399">{nActions} action{nActions === 1 ? '' : 's'}</text>
        </g>
      )}

      {s.replans.length > 0 && (
        <path
          d={`M${colX.an},${rootY - 30} C${colX.an - 40},${8} ${colX.root + 40},${8} ${colX.root},${rootY - 34}`}
          fill="none" stroke="#f472b6" strokeDasharray="5 4" className="animate-dash" strokeWidth={1.3}
        />
      )}
    </svg>
  )
}

/** Full-screen, live-updating decision graph with Google-Maps-style pan & zoom. Rendered in a portal (the panel's backdrop-filter would
 *  otherwise turn `position: fixed` into "fixed to the card"). */
function GraphModal({ s, onClose }: { s: SessionState; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose          // the live graph re-renders this modal constantly: never re-run the focus/scroll-lock effect for it
  const g = s.graph
  const live = s.status === 'running' || s.status === 'connecting' || s.status === 'awaiting_budget'
  const calls = s.callOrder.length
  const done = s.callOrder.filter((id) => ['done', 'cached', 'error'].includes(s.calls[id]?.status)).length

  useEffect(() => {
    const prevFocus = document.activeElement as HTMLElement | null
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onCloseRef.current() } }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      prevFocus?.focus?.()
    }
  }, [])

  // natural pixel size of the detailed canvas (mirrors TreeSvg's maths) so PanZoom can fit it
  const nodes = g?.nodes || []
  const nIn = Math.min(nodes.filter((n) => n.kind === 'entity').length, 8) + Math.min(nodes.filter((n) => n.kind === 'constraint').length, 6)
  const rows = Math.max(calls, nIn, nodes.filter((n) => n.kind === 'dimension').length, 1)
  const W = 990
  const H = Math.max(300, rows * ROW_H + 90)

  return createPortal(
    <motion.div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm sm:p-6"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCloseRef.current() }}
    >
      <motion.div
        role="dialog" aria-modal="true" aria-labelledby="graph-modal-title" id="decision-graph-modal"
        className="panel flex h-full max-h-[920px] w-full max-w-[1500px] flex-col overflow-hidden p-0 !bg-surface"
        initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.97, opacity: 0 }}
      >
        <header className="flex flex-wrap items-center gap-2 border-b border-white/10 px-4 py-3">
          <h3 id="graph-modal-title" className="panel-title"><Network size={14} /> Decision graph · thought-tree</h3>
          {s.intent && <span className="chip" style={{ color: '#c4b5fd' }}>{s.intent.playbook}</span>}
          {live ? (
            <span className="chip border-emerald-400/30 text-emerald-200"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> live · {done}/{calls} calls</span>
          ) : (
            <span className="chip">{calls} calls · {s.status}</span>
          )}
          <div className="ml-2 hidden items-center gap-2 text-[10px] text-slate-400 md:flex">
            {Object.entries(STATUS_COLOR).map(([k, c]) => (
              <span key={k} className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: c }} />{k}</span>
            ))}
          </div>
          <button ref={closeRef} type="button" onClick={() => onCloseRef.current()} className="btn-ghost ml-auto" aria-label="Close full-screen graph" id="decision-graph-close"><X size={14} /> Close</button>
        </header>
        <div className="relative min-h-0 flex-1 bg-canvas/60 grid-bg">
          {g ? (
            <PanZoom width={W} height={H} label="Decision graph" className="absolute inset-0">
              <TreeSvg s={s} detailed fixed svgClass="block" />
            </PanZoom>
          ) : (
            <div className="grid h-full place-items-center text-sm text-slate-500">
              {live ? 'Orchestrator is classifying intent… the graph will appear here live.' : 'Run a prompt to grow the decision graph.'}
            </div>
          )}
        </div>
        {s.replans.length > 0 && (
          <footer className="flex flex-wrap gap-2 border-t border-white/10 px-4 py-2">
            {s.replans.map((r) => (
              <span key={r.iteration} className="chip border-pink-400/30 text-pink-200">↺ Re-plan {r.iteration}/{r.max ?? 2}: {r.reasons?.[0] || 'low confidence'} → {r.new_calls.map((c) => c.engine).join(', ')}</span>
            ))}
          </footer>
        )}
      </motion.div>
    </motion.div>,
    document.body,
  )
}

/** Animated Decision-Graph / thought-tree: Orchestrator → typed nodes → SerpApi sources → Analyst → Actor. */
export function ThoughtTree({ s }: { s: SessionState }) {
  const g = s.graph
  const nodes = g?.nodes || []
  const ents = nodes.filter((n) => n.kind === 'entity').slice(0, 6)
  const dims = nodes.filter((n) => n.kind === 'dimension')
  const cons = nodes.filter((n) => n.kind === 'constraint')
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  return (
    <section className="panel flex h-full flex-col p-4" id="thought-tree">
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="panel-title"><Network size={13} /> Decision graph · thought-tree</h3>
        <div className="flex items-center gap-1.5">
          {s.intent && <span className="chip" style={{ color: '#c4b5fd' }}>{s.intent.playbook}</span>}
          <button type="button" id={`thought-tree-expand-${s.lens}`} className="btn-ghost !p-1.5" onClick={() => setOpen(true)}
            aria-label="Expand decision graph to full screen" aria-haspopup="dialog" title="Expand · pan & zoom the live graph">
            <Maximize2 size={13} />
          </button>
        </div>
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
            <TreeSvg s={s} />
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
      {mounted && <AnimatePresence>{open && <GraphModal key="graph-modal" s={s} onClose={close} />}</AnimatePresence>}
    </section>
  )
}

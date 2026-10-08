import { useMemo } from 'react'
import type { SessionState } from './types'

/** The Plan → Search → Verify → Compare → Act pipeline, derived purely from the SSE event stream. */
export const PIPELINE = [
  { key: 'plan', label: 'Plan', agent: 'orchestrator', hint: 'intent → Decision Graph', stages: ['plan', 'awaiting_budget', 'replan'] },
  { key: 'search', label: 'Search', agent: 'researcher', hint: 'async SerpApi fan-out', stages: ['research', 'repoll'] },
  { key: 'verify', label: 'Verify', agent: 'researcher', hint: 'hybrid RAG · ≥2-source facts', stages: ['verify'] },
  { key: 'compare', label: 'Compare', agent: 'analyst', hint: 'matrix · anomalies · confidence', stages: ['analyze'] },
  { key: 'act', label: 'Act', agent: 'actor', hint: 'HITL proposals · receipts', stages: ['act'] },
] as const

export type StepKey = (typeof PIPELINE)[number]['key']
export type StepState = 'todo' | 'active' | 'done'
export interface StepView {
  key: StepKey; label: string; agent: string; hint: string; state: StepState
  ms: number | null          // wall time spent in this step (summed over loops)
  visits: number             // >1 => the bounded re-plan loop went through it again
}
export interface PipelineView { steps: StepView[]; loops: number; maxLoops: number; progress: number; waiting: boolean; finished: boolean }

const stepOf = (stage: string): number => PIPELINE.findIndex((p) => (p.stages as readonly string[]).includes(stage))

export function derivePipeline(s: SessionState): PipelineView {
  const finished = s.status === 'done'
  const cur = finished ? PIPELINE.length : stepOf(s.stage)
  const ms: number[] = PIPELINE.map(() => 0)
  const visits: number[] = PIPELINE.map(() => 0)
  // walk stage events: time in a step = gap until the next stage event (the last open step is measured to the newest event)
  const stages = s.events.filter((e) => e.type === 'stage')
  const lastTs = s.events.length ? s.events[s.events.length - 1].ts : 0
  stages.forEach((e, i) => {
    const k = stepOf(e.data?.stage)
    if (k < 0) return
    const prev = i > 0 ? stepOf(stages[i - 1].data?.stage) : -1
    if (k !== prev) visits[k] += 1
    const end = i + 1 < stages.length ? stages[i + 1].ts : lastTs
    ms[k] += Math.max(0, (end - e.ts) * 1000)
  })
  const idle = s.status === 'idle' || s.status === 'connecting'
  const steps: StepView[] = PIPELINE.map((p, i) => ({
    key: p.key, label: p.label, agent: p.agent, hint: p.hint, ms: visits[i] ? Math.round(ms[i]) : null, visits: visits[i],
    state: idle ? 'todo' : i < cur ? 'done' : i === cur ? 'active' : 'todo',
  }))
  const loops = s.replans.length
  const progress = idle ? 0 : finished ? 1 : Math.min(1, (cur + 0.5) / PIPELINE.length)
  return { steps, loops, maxLoops: s.replans[0]?.max ?? 2, progress, waiting: s.status === 'awaiting_budget', finished }
}

export function usePipeline(s: SessionState): PipelineView {
  // events array identity changes on every event, which is exactly when the view must be recomputed
  return useMemo(() => derivePipeline(s), [s.events, s.stage, s.status, s.replans]) // eslint-disable-line react-hooks/exhaustive-deps
}

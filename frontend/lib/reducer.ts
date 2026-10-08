import type { AgentName, CompassEvent, Lens, SessionState } from './types'

export const AGENTS: AgentName[] = ['orchestrator', 'researcher', 'analyst', 'actor']

export function initialState(prompt = '', lens: Lens = 'go'): SessionState {
  return {
    sessionId: null,
    prompt,
    lens,
    status: 'idle',
    stage: 'idle',
    replay: false,
    agents: { orchestrator: 'idle', researcher: 'idle', analyst: 'idle', actor: 'idle' },
    agentLabel: {},
    calls: {},
    callOrder: [],
    logs: [],
    prevOrder: [],
    reasons: [],
    anomalies: [],
    replans: [],
    actions: {},
    actionOrder: [],
    watches: [],
    watchTicks: [],
    events: [],
    round: 0,
  }
}

const STAGE_AGENT: Record<string, AgentName> = {
  plan: 'orchestrator',
  awaiting_budget: 'orchestrator',
  replan: 'orchestrator',
  research: 'researcher',
  repoll: 'researcher',
  verify: 'researcher',
  analyze: 'analyst',
  act: 'actor',
}

function activate(s: SessionState, agent: AgentName): SessionState['agents'] {
  const next = { ...s.agents }
  const idx = AGENTS.indexOf(agent)
  AGENTS.forEach((a, i) => {
    if (a === agent) next[a] = 'active'
    else if (i < idx && next[a] !== 'idle') next[a] = 'done'
    else if (next[a] === 'active') next[a] = 'done'
  })
  return next
}

export function reduce(s: SessionState, e: CompassEvent): SessionState {
  const d = e.data || {}
  const events = s.events.length > 600 ? [...s.events.slice(-500), e] : [...s.events, e]
  let n: SessionState = { ...s, events }

  switch (e.type) {
    case 'session.start':
      return { ...n, status: 'running', credits: d.credits, prompt: d.prompt ?? s.prompt, lens: d.lens ?? s.lens }

    case 'stage': {
      const agent = STAGE_AGENT[d.stage]
      n = { ...n, stage: d.stage }
      if (d.stage === 'awaiting_budget') n.status = 'awaiting_budget'
      else if (d.stage === 'done') {
        n.status = 'done'
        n.agents = { orchestrator: 'done', researcher: 'done', analyst: 'done', actor: 'done' }
        n.caveat = d.caveat
      } else if (n.status !== 'error') n.status = 'running'
      if (d.stage === 'repoll') {
        n.disruption = d.disruption
        n.prevOrder = (s.matrix?.rows || []).map((r) => r.id)
        n.prevInsights = s.insights ?? null
        n.baselined = true            // keep THIS baseline through the re-plan that follows the disruption
        n.round = s.round + 1
      }
      if (d.stage === 'research' && typeof d.round === 'number' && d.round > 0) n.round = s.round + 1
      if (agent) n.agents = activate(n, agent)
      return n
    }

    case 'agent.start':
      if (AGENTS.includes(d.agent)) {
        return { ...n, agents: activate(n, d.agent), agentLabel: { ...s.agentLabel, [d.agent]: d.label } }
      }
      return n

    case 'orchestrator.intent':
      return { ...n, intent: d }

    case 'orchestrator.graph': {
      const g = d.graph
      const calls = { ...s.calls }
      const order = [...s.callOrder]
      for (const c of g.calls) {
        if (!calls[c.id]) order.push(c.id)
        calls[c.id] = { id: c.id, engine: c.engine, params: c.params, purpose: c.purpose, status: 'pending', round: s.round }
      }
      return { ...n, graph: g, calls, callOrder: order }
    }

    case 'orchestrator.replan': {
      const calls = { ...s.calls }
      const order = [...s.callOrder]
      for (const c of d.calls || []) {
        if (!calls[c.id]) order.push(c.id)
        calls[c.id] = { id: c.id, engine: c.engine, params: c.params, purpose: c.purpose, status: 'pending', round: d.iteration }
      }
      return {
        ...n,
        calls,
        callOrder: order,
        replans: [...s.replans, { iteration: d.iteration, confidence: d.confidence, reasons: d.reasons, new_calls: d.new_calls, max: d.max }],
        ...(s.baselined ? {} : { prevOrder: (s.matrix?.rows || []).map((r) => r.id), prevInsights: s.insights ?? null }),
      }
    }

    case 'serp.request': {
      const prev = s.calls[d.call_id]
      const calls = {
        ...s.calls,
        [d.call_id]: { ...(prev || { id: d.call_id, engine: d.engine, params: d.params, purpose: d.purpose, round: s.round }), status: 'inflight' as const },
      }
      const order = s.callOrder.includes(d.call_id) ? s.callOrder : [...s.callOrder, d.call_id]
      return {
        ...n,
        calls,
        callOrder: order,
        logs: [...s.logs, { seq: e.seq, ts: e.ts, kind: 'request' as const, callId: d.call_id, engine: d.engine, params: d.params, purpose: d.purpose }].slice(-200),
      }
    }

    case 'serp.cached': {
      const prev = s.calls[d.call_id]
      const calls = {
        ...s.calls,
        [d.call_id]: { ...(prev || { id: d.call_id, engine: d.engine, params: d.params, purpose: d.purpose, round: s.round }), status: 'cached' as const, ms: 0 },
      }
      const order = s.callOrder.includes(d.call_id) ? s.callOrder : [...s.callOrder, d.call_id]
      return {
        ...n,
        calls,
        callOrder: order,
        credits: d.credits ?? s.credits,
        logs: [...s.logs, { seq: e.seq, ts: e.ts, kind: 'cached' as const, callId: d.call_id, engine: d.engine, params: d.params, purpose: d.purpose }].slice(-200),
      }
    }

    case 'serp.response': {
      const prev = s.calls[d.call_id]
      return {
        ...n,
        calls: prev ? { ...s.calls, [d.call_id]: { ...prev, status: d.cached ? 'cached' : 'done', ms: d.ms, results: d.results } } : s.calls,
        credits: d.credits ?? s.credits,
        logs: [
          ...s.logs,
          {
            seq: e.seq, ts: e.ts, kind: 'response' as const, callId: d.call_id, engine: d.engine, ms: d.ms, results: d.results,
            status: d.status, mode: d.mode, searchId: d.search_id, raw: d.raw,
          },
        ].slice(-200),
      }
    }

    case 'serp.error': {
      const prev = s.calls[d.call_id]
      return {
        ...n,
        calls: prev ? { ...s.calls, [d.call_id]: { ...prev, status: 'error', error: d.error } } : s.calls,
        logs: [...s.logs, { seq: e.seq, ts: e.ts, kind: 'error' as const, callId: d.call_id, engine: d.engine, error: d.error }].slice(-200),
      }
    }

    case 'rag.retrieval':
      return { ...n, rag: d }
    case 'rag.verification':
      return { ...n, verification: d }
    case 'analyst.anomaly':
      return { ...n, anomalies: d.anomalies || [] }
    case 'analyst.matrix':
      return {
        ...n,
        matrix: d.matrix,
        insights: d.insights ?? null,
        confidence: d.confidence,
        reasons: d.reasons || [],
        rationale: d.rationale,
        threshold: d.threshold,
        context: d.context,
      }

    case 'actor.proposal': {
      const a = d.action
      return {
        ...n,
        actions: { ...s.actions, [a.id]: a },
        actionOrder: s.actionOrder.includes(a.id) ? s.actionOrder : [a.id, ...s.actionOrder],
      }
    }
    case 'actor.superseded': {
      const a = s.actions[d.action_id]
      return a ? { ...n, actions: { ...s.actions, [a.id]: { ...a, status: 'rejected', receipt: { superseded: true } } } } : n
    }
    case 'actor.approved': {
      const a = s.actions[d.action_id]
      return a ? { ...n, actions: { ...s.actions, [a.id]: { ...a, status: 'approved' } } } : n
    }
    case 'actor.rejected': {
      const a = s.actions[d.action_id]
      return a ? { ...n, actions: { ...s.actions, [a.id]: { ...a, status: 'rejected' } } } : n
    }
    case 'actor.modified':
      return { ...n, actions: { ...s.actions, [d.action.id]: d.action } }
    case 'actor.receipt': {
      const a = s.actions[d.action_id]
      return a ? { ...n, actions: { ...s.actions, [a.id]: { ...a, status: 'executed', receipt: d.receipt } } } : n
    }

    case 'budget.confirm':
      return { ...n, budgetPrompt: d, status: 'awaiting_budget' }
    case 'budget.confirmed':
      return { ...n, budgetPrompt: null, status: 'running' }

    case 'watch.created':
      return { ...n, watches: [...s.watches.filter((w) => w.id !== d.watch.id), d.watch] }
    case 'watch.tick':
      return { ...n, watchTicks: [...s.watchTicks, d].slice(-30) }
    case 'watch.repoll':
      return { ...n, disruption: d.disruption ?? s.disruption }

    case 'session.rehydrated':
      return { ...n, rehydrated: true }

    case 'session.complete':
      return { ...n, credits: d.credits ?? s.credits, caveat: d.caveat, status: 'done', baselined: false }
    case 'session.error':
      return { ...n, status: 'error', error: d.error }
    default:
      return n
  }
}

'use client'

import { useCallback, useEffect, useReducer, useRef } from 'react'
import { api, API_URL, hasBackend, type DisruptKind } from './api'
import { initialState, reduce } from './reducer'
import type { ActionProposal, CompassEvent, Lens, SessionState } from './types'
import recordings from './demo/recordings.json'

/* ------------------------------------------------------------------ replay data */
interface RecEvent extends CompassEvent {
  t: number
}
interface Recording {
  prompt: string
  lens: Lens
  events: RecEvent[]
  receipts: Record<string, any>
  disruption?: { kind?: string; events: RecEvent[]; receipts: Record<string, any> }
}
const REC = recordings as unknown as Record<string, Recording>

/** Pick the pre-recorded scenario closest to a free-form prompt (offline Demo Mode). */
export function pickScenario(prompt: string, lens: Lens): string {
  const p = prompt.toLowerCase()
  const rules: [string, RegExp][] = [
    ['seo', /\bseo\b|serp|rank(ing)?|visibility|keyword|backlink|search engines?|ai mode|ai overview|cited|share of voice|\b[a-z0-9-]+\.(com|io|ai|org|net)\b/],
    ['tacos', /restaurant|taco|ramen|pizza|sushi|brunch|dinner|lunch|coffee|cafe|bbq|burger|yelp|tripadvisor|eat\b|food|near me|nearby|table/],
    ['tokyo', /trip|flight|hotel|travel|vacation|itinerary|getaway|weekend|fly/],
    ['earbuds', /supplier|bulk|wholesale|moq|rfq|vendor|procure|sourc|oem|manufactur/],
    ['prior_art', /patent|prior art|research|paper|scholar|landscape|literature|novelty/],
    ['jobs', /job|hiring|career|role|position|developer|engineer|recruit|salary/],
    ['headphones', /deal|buy|cheapest|price|product|discount|headphone|laptop|monitor|shop/],
  ]
  for (const [k, re] of rules) if (re.test(p) && REC[k]) return k
  return lens === 'pro' ? 'earbuds' : 'tokyo'
}

/** Which injected failure fits the active scenario (offline replay + live backend map it the same way). */
export const DISRUPTION_FOR: Record<string, { kind: DisruptKind; label: string }> = {
  tokyo: { kind: 'price_spike', label: 'Price spike +45%' },
  headphones: { kind: 'price_spike', label: 'Price spike +45%' },
  tacos: { kind: 'rating_drop', label: 'Rating drop −45%' },
  seo: { kind: 'rank_drop', label: 'Rank drop −8 positions' },
}

export const SCENARIOS = Object.entries(REC).map(([key, r]) => ({ key, prompt: r.prompt, lens: r.lens }))

/* ------------------------------------------------------------------ reducer wrapper */
type Act =
  | { kind: 'reset'; prompt: string; lens: Lens; replay: boolean }
  | { kind: 'event'; e: CompassEvent }
  | { kind: 'patch'; patch: Partial<SessionState> }
  | { kind: 'action'; a: ActionProposal }

function root(s: SessionState, a: Act): SessionState {
  switch (a.kind) {
    case 'reset':
      return { ...initialState(a.prompt, a.lens), status: 'connecting', replay: a.replay }
    case 'event':
      return reduce(s, a.e)
    case 'patch':
      return { ...s, ...a.patch }
    case 'action':
      return { ...s, actions: { ...s.actions, [a.a.id]: a.a } }
  }
}

export type BackendMode = 'checking' | 'live' | 'offline'

export function useSession(lens: Lens, backend: BackendMode) {
  const [state, dispatch] = useReducer(root, initialState('', lens))
  const esRef = useRef<EventSource | null>(null)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  const scenario = useRef<string | null>(null)
  const seqOffset = useRef(0)
  const stateRef = useRef(state)
  stateRef.current = state

  const stop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])

  useEffect(() => stop, [stop])

  /** Schedule recorded events with their original relative timing (slightly stretched so the animation reads). */
  const play = useCallback((events: RecEvent[], onDone?: () => void) => {
    const base = seqOffset.current
    let last = 0
    events.forEach((e, i) => {
      const at = Math.round(e.t * 1600 + i * 70)
      last = Math.max(last, at)
      timers.current.push(setTimeout(() => dispatch({ kind: 'event', e: { ...e, seq: base + e.seq } }), at))
    })
    seqOffset.current = base + events.length + 1
    if (onDone) timers.current.push(setTimeout(onDone, last + 50))
  }, [])

  const startReplay = useCallback(
    (prompt: string) => {
      const key = pickScenario(prompt, lens)
      scenario.current = key
      seqOffset.current = 0
      dispatch({ kind: 'reset', prompt: REC[key].prompt, lens, replay: true })
      dispatch({ kind: 'patch', patch: { sessionId: `demo_${key}` } })
      play(REC[key].events)
    },
    [lens, play],
  )

  const start = useCallback(
    async (prompt: string, priorities?: Record<string, number>) => {
      stop()
      // Only a missing backend URL (NEXT_PUBLIC_API_URL=offline) forces the recordings. If the health badge is still "waking"/"offline"
      // (Render cold start) we STILL try the live API - createSession waits up to 75 s - and only then fall back to the recording.
      if (!hasBackend()) return startReplay(prompt)
      dispatch({ kind: 'reset', prompt, lens, replay: false })
      try {
        const { session_id } = await api.createSession(prompt, lens, priorities)  // 75 s timeout (cold start)
        dispatch({ kind: 'patch', patch: { sessionId: session_id } })
        const es = new EventSource(api.streamUrl(session_id))
        esRef.current = es
        es.onmessage = (m) => {
          try {
            dispatch({ kind: 'event', e: JSON.parse(m.data) })
          } catch {}
        }
        es.onerror = () => {
          // EventSource auto-reconnects; the server replays history after the last id.
        }
      } catch (err: any) {
        // backend unreachable (e.g. Render cold start) -> fall back to the pre-cached Demo Mode recording
        startReplay(prompt)
        dispatch({ kind: 'patch', patch: { error: `Backend unreachable (${err?.message || err}); showing offline recording.` } })
      }
    },
    [lens, startReplay, stop],
  )

  const disrupt = useCallback(
    async (kind: DisruptKind = 'price_spike') => {
      const s = stateRef.current
      if (!s.sessionId) return
      if (s.replay) {
        const rec = scenario.current ? REC[scenario.current] : null
        if (!rec?.disruption) {
          dispatch({ kind: 'patch', patch: { error: 'This offline scenario has no recorded disruption — try the Tokyo trip, headphones deal, tacos or SEO scenario.' } })
          return
        }
        play(rec.disruption.events)
        return
      }
      try {
        await api.disrupt(s.sessionId, kind)
      } catch (e: any) {
        dispatch({ kind: 'patch', patch: { error: String(e?.message || e) } })
      }
    },
    [play],
  )

  const repoll = useCallback(async () => {
    const s = stateRef.current
    if (!s.sessionId || s.replay) return
    await api.repoll(s.sessionId).catch(() => {})
  }, [])

  const confirmBudget = useCallback(async (choice: 'all' | 'essential') => {
    const s = stateRef.current
    if (!s.sessionId || s.replay) return
    await api.confirm(s.sessionId, choice).catch(() => {})
  }, [])

  const recordedReceipt = (id: string) => {
    const rec = scenario.current ? REC[scenario.current] : null
    return rec?.receipts?.[id] ?? rec?.disruption?.receipts?.[id]
  }

  const approve = useCallback(async (a: ActionProposal) => {
    if (stateRef.current.replay) {
      dispatch({ kind: 'action', a: { ...a, status: 'approved' } })
      setTimeout(() => {
        const receipt = recordedReceipt(a.id) || {
          action_id: a.id, type: a.type, title: a.title, confirmation: `CMP-${a.id.slice(-6).toUpperCase()}`, offline: true,
        }
        dispatch({ kind: 'action', a: { ...a, status: 'executed', receipt } })
      }, 900)
      return
    }
    dispatch({ kind: 'action', a: { ...a, status: 'approved' } })
    try {
      const r = await api.approve(a.id)
      dispatch({ kind: 'action', a: { ...r.action, receipt: r.receipt } })
    } catch (e: any) {
      dispatch({ kind: 'action', a: { ...a, status: 'failed', receipt: { error: String(e?.message || e) } } })
    }
  }, [])

  const reject = useCallback(async (a: ActionProposal) => {
    dispatch({ kind: 'action', a: { ...a, status: 'rejected' } })
    if (!stateRef.current.replay) await api.reject(a.id).catch(() => {})
  }, [])

  const modify = useCallback(async (a: ActionProposal, note: string, payload: Record<string, any> = {}) => {
    const next: ActionProposal = { ...a, status: 'modified', payload: { ...a.payload, ...payload }, description: `${a.description}  ✎ ${note}` }
    dispatch({ kind: 'action', a: next })
    if (!stateRef.current.replay) await api.modify(a.id, payload, note).catch(() => {})
  }, [])

  const scenarioKey = () => scenario.current

  const icsUrl = (a: ActionProposal) => (!state.replay && API_URL ? `${API_URL}/api/actions/${a.id}/ics` : null)

  return { state, start, disrupt, repoll, confirmBudget, approve, reject, modify, icsUrl, stop, scenarioKey }
}

'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { SessionState, WatchRecord, WatchTick } from './types'

/** Deterministic pseudo-random in [0,1) so the offline simulation is stable per (watch, poll #). */
function rnd(seed: string): number {
  let h = 2166136261
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619)
  h ^= h >>> 13; h = Math.imul(h, 1274126177); h ^= h >>> 16
  return (h >>> 0) / 4294967296
}

/** Offline-only poll: a small drift around the baseline, occasionally past the threshold. Clearly labelled "simulated" in the UI. */
export function simulateTick(w: WatchRecord, n: number): { rec: WatchRecord; tick: WatchTick } {
  const base = w.baseline_price ?? w.last_price ?? 100
  const metric = w.metric ?? 'price'
  const r = rnd(`${w.id}:${n}`)
  const spike = n > 0 && n % 3 === 0                       // every 3rd poll breaches the threshold
  let price: number
  if (metric === 'position') price = Math.max(1, Math.round(base + (spike ? 4 : (r - 0.5) * 2)))
  else if (metric === 'rating') price = +Math.min(5, Math.max(1, base * (spike ? 0.88 : 1 + (r - 0.5) * 0.03))).toFixed(2)
  else price = Math.round(base * (spike ? 1.14 : 1 + (r - 0.5) * 0.05))
  const change = base ? ((price - base) / base) * 100 : 0
  const bad = metric === 'rating' ? change <= -w.threshold_pct : metric === 'position' ? change >= w.threshold_pct || price - base >= 3 : Math.abs(change) >= w.threshold_pct
  const now = Date.now() / 1000
  const rec: WatchRecord = { ...w, last_price: price, last_checked: now, alerts: (w.alerts || 0) + (bad ? 1 : 0), history: [...(w.history || []), { ts: now, price }].slice(-30) }
  return { rec, tick: { id: w.id, label: w.label, metric, price, baseline: base, change_pct: +change.toFixed(2), triggered: bad, matched: w.target_title || w.target_domain || null } }
}

/** Watches for the panel: server-side list (live) ∪ watches announced on the event stream ∪ watch actions already executed. */
export function useWatches(s: SessionState, live: boolean) {
  const [server, setServer] = useState<WatchRecord[]>([])
  const [local, setLocal] = useState<Record<string, WatchRecord>>({})
  const [ticks, setTicks] = useState<WatchTick[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const polls = useRef<Record<string, number>>({})

  const refresh = useCallback(async () => {
    if (!live) return
    try { setServer(await api.watches()); setError(null) } catch (e: any) { setError(String(e?.message || e)) }
  }, [live])

  const executed = Object.values(s.actions).filter((a) => a.type === 'watch' && a.status === 'executed' && (a.receipt as any)?.watch).length
  useEffect(() => { refresh() }, [refresh, s.watches.length, executed])

  const merged = useMemo(() => {
    const m = new Map<string, WatchRecord>()
    // precedence (low -> high): executed-action receipt < event-stream announcement < server record < local simulation.
    Object.values(s.actions).forEach((a) => {
      const w = (a.receipt as any)?.watch
      if (a.type === 'watch' && a.status === 'executed' && w?.id) m.set(w.id, w)
    })
    s.watches.forEach((w) => m.set(w.id, { ...m.get(w.id), ...w }))
    if (live) server.forEach((w) => m.set(w.id, { ...m.get(w.id), ...w }))   // the server copy is the freshest: it carries last_checked/history
    Object.values(local).forEach((w) => m.set(w.id, w))
    return [...m.values()].sort((a, b) => (b.last_checked || 0) - (a.last_checked || 0))
  }, [live, server, s.watches, s.actions, local])

  const check = useCallback(async (w: WatchRecord) => {
    setBusy(w.id); setError(null)
    try {
      if (live) {
        const t = await api.tickWatch(w.id)
        setTicks((x) => [...x, t].slice(-20))
        await refresh()
      } else {
        const n = (polls.current[w.id] = (polls.current[w.id] || 0) + 1)
        const { rec, tick } = simulateTick(local[w.id] || w, n)
        await new Promise((r) => setTimeout(r, 650))
        setLocal((l) => ({ ...l, [w.id]: rec }))
        setTicks((x) => [...x, tick].slice(-20))
      }
    } catch (e: any) { setError(String(e?.message || e)) } finally { setBusy(null) }
  }, [live, local, refresh])

  const allTicks = useMemo(() => [...s.watchTicks, ...ticks].slice(-20), [s.watchTicks, ticks])
  return { watches: merged, ticks: allTicks, busy, error, check, refresh, simulated: !live }
}

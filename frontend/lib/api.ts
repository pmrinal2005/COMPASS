import type { Account, ActionProposal, Lens, Playbook } from './types'

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '')

export async function fetchJSON<T = any>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), init?.timeoutMs ?? 15000)
  try {
    const r = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    })
    if (!r.ok) {
      let msg = `${r.status}`
      try {
        msg = (await r.json()).detail || msg
      } catch {}
      throw new Error(msg)
    }
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

export interface Health {
  ok: boolean
  demo_mode: boolean
  integrations: Record<string, any>
  llm: string
  embedder: string
  store: string
  cache: { backend: string; hits: number; misses: number; hit_rate: number }
  live_serpapi_calls: number
}

export type DisruptKind = 'price_spike' | 'unavailable' | 'rating_drop' | 'rank_drop'

export const api = {
  account: (force = false) => fetchJSON<Account>(`/api/account${force ? '?force=true' : ''}`, { timeoutMs: 15000 }),
  playbooks: () => fetchJSON<Playbook[]>('/api/playbooks', { timeoutMs: 15000 }),
  locations: (q: string, limit = 5) => fetchJSON<any[]>(`/api/locations?q=${encodeURIComponent(q)}&limit=${limit}`),
  watches: () => fetchJSON<any[]>('/api/watches'),
  tickWatch: (wid: string) => fetchJSON(`/api/watches/${wid}/check`, { method: 'POST', timeoutMs: 60000 }),
  health: (timeoutMs = 8000) => fetchJSON<Health>('/api/health', { timeoutMs }),
  createSession: (prompt: string, lens: Lens, priorities?: Record<string, number>) =>
    fetchJSON<{ session_id: string }>('/api/sessions', { method: 'POST', body: JSON.stringify({ prompt, lens, priorities }) }),
  confirm: (sid: string, choice: 'all' | 'essential') => fetchJSON(`/api/sessions/${sid}/confirm?choice=${choice}`, { method: 'POST' }),
  disrupt: (sid: string, kind: DisruptKind, pct = 45) =>
    fetchJSON(`/api/sessions/${sid}/disrupt?kind=${kind}&pct=${pct}`, { method: 'POST' }),
  repoll: (sid: string) => fetchJSON(`/api/sessions/${sid}/repoll`, { method: 'POST' }),
  approve: (aid: string) =>
    fetchJSON<{ action: ActionProposal; receipt: any }>(`/api/actions/${aid}/approve`, { method: 'POST', timeoutMs: 60000 }),
  reject: (aid: string) => fetchJSON(`/api/actions/${aid}/reject`, { method: 'POST' }),
  modify: (aid: string, payload: Record<string, any>, note?: string) =>
    fetchJSON(`/api/actions/${aid}/modify`, { method: 'POST', body: JSON.stringify({ payload, note }) }),
  trace: (sid: string) => fetchJSON(`/api/sessions/${sid}/trace`),
  checkWatch: (wid: string) => fetchJSON(`/api/watches/${wid}/check`, { method: 'POST' }),
  streamUrl: (sid: string) => `${API_URL}/api/sessions/${sid}/stream`,
}

export const hasBackend = () => Boolean(API_URL)

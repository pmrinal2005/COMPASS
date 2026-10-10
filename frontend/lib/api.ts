import type { Account, ActionProposal, Lens, Playbook, WatchRecord, WatchTick } from './types'

/**
 * Backend resolution (NEXT_PUBLIC_* values are inlined at BUILD time -> after changing it in Vercel you must REDEPLOY):
 *   - unset / empty            -> the deployed Render backend below (so a forgotten env var no longer silently ships the demo)
 *   - "offline" | "demo"       -> force the pre-recorded offline Demo Mode
 *   - "my-api.onrender.com"    -> https:// is added automatically; trailing slashes / whitespace / a pasted "/api" suffix are stripped
 */
export const DEFAULT_API_URL = 'https://compass-api-w9dp.onrender.com'

export function resolveApiUrl(raw: string | undefined | null): string {
  const v = (raw ?? '').trim()
  if (!v) return DEFAULT_API_URL
  if (/^(offline|demo|none|off|false)$/i.test(v)) return ''
  const withProto = /^https?:\/\//i.test(v) ? v : `${/^(localhost|127\.|0\.0\.0\.0)/.test(v) ? 'http' : 'https'}://${v}`
  return withProto.replace(/\/+$/, '').replace(/\/api$/i, '')
}

export const API_URL = resolveApiUrl(process.env.NEXT_PUBLIC_API_URL)

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
  watches: () => fetchJSON<WatchRecord[]>('/api/watches'),
  tickWatch: (wid: string) => fetchJSON<WatchTick>(`/api/watches/${wid}/check`, { method: 'POST', timeoutMs: 60000 }),
  health: (timeoutMs = 8000) => fetchJSON<Health>('/api/health', { timeoutMs }),
  createSession: (prompt: string, lens: Lens, priorities?: Record<string, number>) =>
    fetchJSON<{ session_id: string }>('/api/sessions', { method: 'POST', timeoutMs: 75000, body: JSON.stringify({ prompt, lens, priorities }) }),
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
  streamUrl: (sid: string) => `${API_URL}/api/sessions/${sid}/stream`,
}

export const hasBackend = () => Boolean(API_URL)

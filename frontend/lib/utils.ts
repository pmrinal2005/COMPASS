import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...v: ClassValue[]) => twMerge(clsx(v))

export const money = (v?: number | null, digits = 0) =>
  v === null || v === undefined ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`

export const pct = (v?: number | null) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`)

/** Engine -> colour family (used across the log, heat-map and thought tree). */
const ENGINE_COLORS: [RegExp, string][] = [
  [/flight/, '#60a5fa'],
  [/hotel/, '#f472b6'],
  [/maps|local|yelp|tripadvisor/, '#34d399'],
  [/finance/, '#facc15'],
  [/shopping|amazon|walmart|ebay|home_depot/, '#fb923c'],
  [/jobs/, '#a78bfa'],
  [/news/, '#f87171'],
  [/trends/, '#2dd4bf'],
  [/scholar/, '#c084fc'],
  [/patents/, '#e879f9'],
  [/autocomplete/, '#94a3b8'],
  [/airbnb/, '#fb7185'],
  [/event/, '#f59e0b'],
  [/ai_mode|ai_overview/, '#c4b5fd'],
  [/bing|baidu|naver|yahoo|yandex|duckduckgo/, '#38bdf8'],
  [/^google$/, '#22d3ee'],
]
export function engineColor(engine: string): string {
  for (const [re, c] of ENGINE_COLORS) if (re.test(engine)) return c
  return '#94a3b8'
}

export const AGENT_META = {
  orchestrator: { label: 'Orchestrator', role: 'Plan · classify · re-plan', color: '#a78bfa' },
  researcher: { label: 'Researcher', role: 'SerpApi fan-out · hybrid RAG', color: '#22d3ee' },
  analyst: { label: 'Analyst', role: 'Decision matrix · anomalies', color: '#fbbf24' },
  actor: { label: 'Actor', role: 'HITL actions · receipts', color: '#34d399' },
} as const

/** Platform -> colour for the cross-platform venue consensus bars. */
export const PLATFORM_COLORS: Record<string, string> = { 'Google Maps': '#34d399', Yelp: '#f43f5e', Tripadvisor: '#fbbf24' }
export const platformColor = (p: string) => PLATFORM_COLORS[p] || '#94a3b8'

/** Rank-position heat colour (SEO grid): top-3 green, page-1 cyan, page-2 amber, deeper rose, not found slate. */
export function positionHeat(pos: number | null | undefined): string {
  if (pos === null || pos === undefined) return '#334155'
  if (pos <= 3) return '#10b981'
  if (pos <= 10) return '#22d3ee'
  if (pos <= 20) return '#f59e0b'
  return '#f43f5e'
}

export const ago = (ts?: number | null) => {
  if (!ts) return 'never'
  const d = Math.max(0, Date.now() / 1000 - ts)
  return d < 60 ? `${Math.round(d)}s ago` : d < 3600 ? `${Math.round(d / 60)}m ago` : `${Math.round(d / 3600)}h ago`
}

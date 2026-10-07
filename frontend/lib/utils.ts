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

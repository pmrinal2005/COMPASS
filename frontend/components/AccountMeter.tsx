'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Gauge, RefreshCw, WifiOff } from 'lucide-react'
import { api } from '@/lib/api'
import type { Account } from '@/lib/types'
import { cn } from '@/lib/utils'
import { AnimatedNumber } from './AnimatedNumber'

function Ring({ frac, color, size = 34 }: { frac: number; color: string; size?: number }) {
  const r = size / 2 - 3, c = 2 * Math.PI * r
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
      <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeDasharray={c}
        initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - Math.min(1, Math.max(0, frac))) }} transition={{ type: 'spring', stiffness: 80, damping: 18 }} />
    </svg>
  )
}

/** Header badge: real SerpApi account credits via the free Account API (GET /api/account → serpapi.com/account.json). */
export function AccountMeter({ live, refreshKey = 0 }: { live: boolean; refreshKey?: number }) {
  const [acc, setAcc] = useState<Account | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const load = useCallback(async (force = false) => {
    if (!live) return
    setBusy(true)
    try { setAcc(await api.account(force)); setErr(null) } catch (e: any) { setErr(String(e?.message || e)) } finally { setBusy(false) }
  }, [live])
  useEffect(() => { load() }, [load, refreshKey])

  if (!live) return <span className="chip" title="Connect a backend to read your SerpApi plan"><WifiOff size={11} /> credits: offline</span>
  if (err && !acc) return <button className="chip text-rose-200" onClick={() => load(true)} title={err}><Gauge size={11} /> account unavailable</button>
  if (!acc) return <span className="chip"><Gauge size={11} className="animate-pulse" /> credits…</span>
  if (acc.demo) return <span className="chip text-amber-200" title="No SERPAPI_KEY on the backend: Demo Mode serves shape-faithful payloads for 0 credits."><Gauge size={11} /> demo · 0 credits</span>

  const total = acc.searches_per_month || 0
  const left = acc.total_searches_left ?? acc.plan_searches_left ?? 0
  const frac = total ? left / total : 0
  const color = frac > 0.4 ? '#34d399' : frac > 0.15 ? '#fbbf24' : '#f43f5e'
  const hr = acc.account_rate_limit_per_hour ? (acc.this_hour_searches ?? 0) / acc.account_rate_limit_per_hour : 0
  return (
    <button onClick={() => load(true)} className={cn('group flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-2 py-1 text-left transition hover:bg-white/[0.07]')}
      title={`${acc.plan_name} · ${acc.account_status} · ${acc.this_month_usage} used this month · ${acc.this_hour_searches}/${acc.account_rate_limit_per_hour} this hour${acc.plan_renewal_date ? ` · renews ${acc.plan_renewal_date}` : ''}\nClick to refresh (free, not counted)`}
      aria-label="SerpApi account credits">
      <span className="relative grid place-items-center"><Ring frac={frac} color={color} /><span className="absolute"><RefreshCw size={9} className={cn('text-slate-400', busy && 'animate-spin')} /></span></span>
      <span className="leading-tight">
        <span className="block font-mono text-[11px] font-bold" style={{ color }}><AnimatedNumber value={left} /> <span className="font-normal text-slate-500">/ {total.toLocaleString()}</span></span>
        <span className="block text-[9px] uppercase tracking-wider text-slate-500">{acc.plan_name} · {Math.round(hr * 100)}% hr</span>
      </span>
    </button>
  )
}

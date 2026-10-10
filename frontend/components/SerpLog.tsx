'use client'

import { useEffect, useRef, useState } from 'react'
import { Terminal, ChevronRight } from 'lucide-react'
import type { LogEntry, SessionState } from '@/lib/types'
import { cn, engineColor } from '@/lib/utils'

const KIND: Record<LogEntry['kind'], { tag: string; cls: string }> = {
  request: { tag: 'GET', cls: 'text-cyan-300' },
  response: { tag: '200', cls: 'text-emerald-300' },
  cached: { tag: 'HIT', cls: 'text-amber-300' },
  error: { tag: 'ERR', cls: 'text-rose-300' },
}

function qs(params?: Record<string, any>) {
  if (!params) return ''
  return Object.entries(params)
    .filter(([k]) => k !== 'api_key')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
}

/** Live-scrolling raw SerpApi log, colour-coded by engine. */
export function SerpLog({ s }: { s: SessionState }) {
  const ref = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState<number | null>(null)
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' })
  }, [s.logs.length])

  return (
    <section className="panel flex h-full flex-col p-4" id="serp-log">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="panel-title"><Terminal size={13} /> Live SerpApi log</h3>
        <span className="chip font-mono">async=true · {s.logs.filter((l) => l.kind === 'response').length} resp</span>
      </header>
      <div ref={ref} className="scroll-thin flex-1 space-y-0.5 overflow-auto rounded-lg bg-black/40 p-2 font-mono text-[10.5px] leading-relaxed">
        {s.logs.length === 0 && <div className="text-slate-600">$ waiting for the Researcher fan-out…</div>}
        {s.logs.map((l) => {
          const k = KIND[l.kind]
          const isOpen = open === l.seq
          return (
            <div key={l.seq}>
              <button
                className={cn('flex w-full items-start gap-1.5 text-left hover:bg-white/[0.03]', l.raw ? 'cursor-pointer' : 'cursor-default')}
                onClick={() => l.raw && setOpen(isOpen ? null : l.seq)}
              >
                <span className={cn('w-7 shrink-0', k.cls)}>{k.tag}</span>
                <span className="shrink-0 font-semibold" style={{ color: engineColor(l.engine) }}>{l.engine}</span>
                <span className="min-w-0 flex-1 truncate text-slate-400">
                  {l.kind === 'request' && <>/search.json?engine={l.engine}&{qs(l.params)}</>}
                  {l.kind === 'cached' && <>dedupe hit · no credit spent · {l.purpose}</>}
                  {l.kind === 'response' && (
                    <>
                      {l.status} · {l.results} results · {l.ms}ms · {l.mode}
                      {l.searchId ? ` · id ${l.searchId.slice(0, 10)}` : ''}
                    </>
                  )}
                  {l.kind === 'error' && <span className="text-rose-300">{l.error}</span>}
                </span>
                {l.raw && <ChevronRight size={11} className={cn('mt-0.5 shrink-0 text-slate-500 transition', isOpen && 'rotate-90')} />}
              </button>
              {isOpen && (
                <pre className="scroll-thin my-1 max-h-56 overflow-auto rounded border border-white/5 bg-canvas p-2 text-[10px] text-slate-300">
                  {JSON.stringify(l.raw, null, 2)}
                </pre>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

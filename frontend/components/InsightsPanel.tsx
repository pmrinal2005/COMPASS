'use client'

import { motion } from 'framer-motion'
import { Calendar, ExternalLink, Home, Lightbulb, ShieldCheck, Ticket } from 'lucide-react'
import type { Insights, SessionState } from '@/lib/types'
import { money } from '@/lib/utils'
import { VenueConsensus } from './VenueConsensus'
import { SeoGrid } from './SeoGrid'

const TITLE: Record<string, string> = { venues: 'Venue consensus · Maps ⊕ Yelp ⊕ Tripadvisor', seo: 'SEO & AI visibility · 7 engines', trip: 'Stays & events · Airbnb ⊕ Events' }

function TripExtras({ ins }: { ins: Extract<Insights, { kind: 'trip' }> }) {
  return (
    <div className="grid h-full gap-3 overflow-auto md:grid-cols-2" id="trip-extras">
      <div>
        <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Home size={11} /> Alternative stays (Airbnb)</div>
        <ul className="stagger space-y-1.5">
          {ins.stays.slice(0, 5).map((s) => (
            <li key={s.title} className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-slate-200">{s.title}</span>
                <span className="font-mono text-slate-100">{money(s.price)}</span>
                {s.url && <a href={s.url} target="_blank" rel="noreferrer" aria-label="open listing" className="text-slate-500 hover:text-slate-200"><ExternalLink size={10} /></a>}
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-500">
                {s.rating ? <span>★ {s.rating}{s.reviews ? ` (${s.reviews})` : ''}</span> : null}
                {s.qualifier && <span>{s.qualifier}</span>}
                {s.verified && <span className="ml-auto inline-flex items-center gap-0.5 text-emerald-300"><ShieldCheck size={10} /> verified</span>}
              </div>
            </li>
          ))}
          {ins.stays.length === 0 && <li className="text-[11px] text-slate-600">No stays returned.</li>}
        </ul>
      </div>
      <div>
        <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500"><Calendar size={11} /> Things happening during the trip</div>
        <ul className="stagger space-y-1.5">
          {ins.events.slice(0, 5).map((e) => (
            <li key={e.title + (e.when || '')} className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
              <div className="flex items-center gap-2">
                <Ticket size={11} className="shrink-0 text-amber-300" />
                <span className="min-w-0 flex-1 truncate text-slate-200">{e.title}</span>
                {e.url && <a href={e.url} target="_blank" rel="noreferrer" aria-label="open event" className="text-slate-500 hover:text-slate-200"><ExternalLink size={10} /></a>}
              </div>
              <div className="text-[10px] text-slate-500">{[e.when, e.venue].filter(Boolean).join(' · ')}</div>
            </li>
          ))}
          {ins.events.length === 0 && <li className="text-[11px] text-slate-600">No events returned.</li>}
        </ul>
      </div>
    </div>
  )
}

/** Playbook-specific insight panel (the Analyst's `insights` payload): venue consensus, SEO grid, or stays+events. */
export function InsightsPanel({ s }: { s: SessionState }) {
  const ins = s.insights
  return (
    <section className="panel flex h-full flex-col p-4" id={`insights-${s.lens}`}>
      <header className="mb-2 flex items-center justify-between gap-2">
        <h3 className="panel-title"><Lightbulb size={13} /> {ins ? TITLE[ins.kind] : 'Playbook insights'}</h3>
        {ins && <span className="chip">{ins.kind}</span>}
      </header>
      {!ins ? (
        <div className="grid flex-1 place-items-center px-4 text-center text-xs text-slate-500">
          Cross-platform venue consensus, the multi-engine SEO grid and trip extras (Airbnb stays + events) appear here for the Local, SEO and Trip Playbooks.
        </div>
      ) : (
        <motion.div key={ins.kind} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="min-h-0 flex-1">
          {ins.kind === 'venues' && <VenueConsensus ins={ins} prev={s.prevInsights} />}
          {ins.kind === 'seo' && <SeoGrid ins={ins} prev={s.prevInsights} />}
          {ins.kind === 'trip' && <TripExtras ins={ins} />}
        </motion.div>
      )}
    </section>
  )
}

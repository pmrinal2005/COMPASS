'use client'

import { motion } from 'framer-motion'
import { Calendar, ExternalLink, Home, Lightbulb, ShieldCheck, Ticket, BadgeCheck, TrendingUp, TrendingDown } from 'lucide-react'
import type { Insights, SessionState } from '@/lib/types'
import { cn, money } from '@/lib/utils'
import { VenueConsensus } from './VenueConsensus'
import { SeoGrid } from './SeoGrid'

const TITLE: Record<string, string> = {
  venues: 'Venue consensus · Maps ⊕ Yelp ⊕ Tripadvisor', seo: 'SEO & AI visibility · 7 engines', trip: 'Stays & events · Airbnb ⊕ Events',
  feed: 'Ranked feed · fresh-first blend',
}

function FeedExtras({ ins }: { ins: Extract<Insights, { kind: 'feed' }> }) {
  return (
    <div className="grid h-full gap-3 overflow-auto md:grid-cols-2" id="feed-extras">
      <div>
        <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-500">
          {ins.title}
        </div>
        <ul className="stagger space-y-1.5">
          {ins.items.slice(0, 8).map((it, i) => (
            <li key={`${it.title}-${i}`} className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
              <div className="flex items-center gap-2">
                <span className="w-4 shrink-0 font-mono text-slate-500">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate text-slate-200" title={it.title}>{it.title}</span>
                {it.verified && <BadgeCheck size={11} className="shrink-0 text-cyan-300" />}
                {it.url && <a href={it.url} target="_blank" rel="noreferrer" aria-label="open result" className="shrink-0 text-slate-500 hover:text-slate-200"><ExternalLink size={10} /></a>}
              </div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 pl-6 text-[10px] text-slate-500">
                {it.source && <span>{it.source}</span>}
                {it.channel && <span>{it.channel}</span>}
                {it.date && <span>{it.date}</span>}
                {it.views != null && <span>{it.views} views</span>}
                {it.length && <span>{it.length}</span>}
                {it.price != null && <span className="font-mono text-slate-300">{money(it.price)}</span>}
                {it.rating != null && <span>★ {it.rating}</span>}
                {it.score != null && <span className="ml-auto font-mono">{Number(it.score).toFixed(3)}</span>}
              </div>
            </li>
          ))}
          {ins.items.length === 0 && <li className="text-[11px] text-slate-600">No feed items returned.</li>}
        </ul>
      </div>
      <div className="space-y-3">
        {ins.channel && (
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Channel</div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px] text-slate-200">
              {ins.channel.title} {ins.channel.handle && <span className="text-slate-500">{ins.channel.handle}</span>}
              <div className="text-[10px] text-slate-500">
                {[ins.channel.subscribers != null ? `${ins.channel.subscribers} subscribers` : null,
                  ins.channel.video_count != null ? `${ins.channel.video_count} videos` : null].filter(Boolean).join(' · ')}
              </div>
            </div>
          </div>
        )}
        {ins.movers && ins.movers.length > 0 && (
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Market movers</div>
            <ul className="space-y-1">
              {ins.movers.slice(0, 6).map((m, i) => (
                <li key={`${m.stock || m.name}-${i}`} className="flex items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-1 text-[11px]">
                  {m.change_pct != null && m.change_pct < 0 ? <TrendingDown size={11} className="text-rose-300" /> : <TrendingUp size={11} className="text-emerald-300" />}
                  <span className="min-w-0 flex-1 truncate text-slate-200" title={m.name}>{m.stock || m.name}</span>
                  {m.price != null && <span className="font-mono text-slate-300">{m.price}</span>}
                  {m.change_pct != null && (
                    <span className={cn('font-mono', m.change_pct < 0 ? 'text-rose-300' : 'text-emerald-300')}>
                      {m.change_pct > 0 ? '+' : ''}{Number(m.change_pct).toFixed(2)}%
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(ins.fx?.rate != null || ins.momentum != null || ins.deals_origin) && (
          <div className="flex flex-wrap gap-1.5">
            {ins.fx?.rate != null && <span className="chip font-mono" title={ins.fx.pair || 'fx'}>{ins.fx.pair}: {ins.fx.rate}</span>}
            {ins.momentum != null && (
              <span className="chip font-mono" title={Array.isArray(ins.momentum) ? `interest over time (${ins.momentum.length} points)` : 'trend momentum score'}>
                momentum {Array.isArray(ins.momentum) ? ins.momentum.slice(-1)[0] : Number(ins.momentum).toFixed(2)}
              </span>
            )}
            {ins.deals_origin && <span className="chip" title="deals origin airport">{ins.deals_origin}</span>}
          </div>
        )}
      </div>
    </div>
  )
}

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

/** Playbook-specific insight panel (the Analyst's `insights` payload): venue consensus, SEO grid, stays+events, or a ranked feed. */
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
          Cross-platform venue consensus, the multi-engine SEO grid, trip extras and ranked feeds (news, media, finance, images, apps) appear here.
        </div>
      ) : (
        <motion.div key={ins.kind} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="min-h-0 flex-1">
          {ins.kind === 'venues' && <VenueConsensus ins={ins} prev={s.prevInsights} />}
          {ins.kind === 'seo' && <SeoGrid ins={ins} prev={s.prevInsights} />}
          {ins.kind === 'trip' && <TripExtras ins={ins} />}
          {ins.kind === 'feed' && <FeedExtras ins={ins} />}
        </motion.div>
      )}
    </section>
  )
}

'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowUpRight, Compass, Menu, X } from 'lucide-react'
import { BlurText } from './BlurText'
import { PitchDeck } from './PitchDeck'
import { peekResolvedSrc, warmAll, whenReady } from '@/lib/videoCache'

// Served from /public (same-origin) so the landing never depends on a third-party CDN for its two hero clips.
const HERO_VIDEO = '/landing_page.mp4'
const CAP_VIDEO = '/section3.mp4'

const NAV = [
  { to: '#capabilities', label: 'The Four Agents' },
  { to: '#pitch', label: 'Product Demo' },
  { to: '/dashboard', label: 'Dashboard' },
]

const METRICS = [
  { value: '25', label: 'SerpApi engines fanned out in parallel — Flights to Patents, one sentence' },
  { value: '2×', label: 'Sources must agree before COMPASS trusts a price, rating or deadline' },
  { value: '$0', label: 'To run. Free-tier cloud, zero Docker, happy on a 4 GB laptop' },
]

const AGENTS = [
  { title: 'Plan it in one breath', body: 'Your sentence becomes a Decision Graph: what to compare, what constraints matter, which live sources to ask. No forms. No filters. Just say it.', tags: ['Orchestrator', 'LangGraph', 'Playbooks'] },
  { title: 'Search everything. At once.', body: 'Flights, hotels, maps, shopping, jobs, scholar, patents — fired in parallel through SerpApi async mode, deduplicated so repeat calls never burn a credit.', tags: ['Researcher', 'SerpApi async', 'pgvector RAG'] },
  { title: 'Compare. Then act.', body: 'A transparent weighted matrix ranks every option, flags price anomalies, and turns the winner into an Approve / Modify / Reject card. You stay in control.', tags: ['Analyst', 'Actor', 'Human-in-the-loop'] },
]

export function LandingPage() {
  const [ready, setReady] = useState(false)
  const [heroSrc, setHeroSrc] = useState(() => peekResolvedSrc(HERO_VIDEO))
  const [capSrc, setCapSrc] = useState(() => peekResolvedSrc(CAP_VIDEO))
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let live = true
    warmAll([HERO_VIDEO, CAP_VIDEO])
    whenReady(HERO_VIDEO).then((src) => { if (live) { setHeroSrc(src); setReady(true) } })
    whenReady(CAP_VIDEO).then((src) => { if (live) setCapSrc(src) })
    const t = window.setTimeout(() => { if (live) setReady(true) }, 2200)
    return () => { live = false; window.clearTimeout(t) }
  }, [])

  return (
    <div className="lp-root" id="landing-root">
      {!ready && (
        <div className="landing-loader" role="status" aria-label="Loading COMPASS">
          <div className="landing-loader__core">
            <div className="landing-loader__rings">
              <div className="landing-loader__ring landing-loader__ring--outer" />
              <div className="landing-loader__ring landing-loader__ring--middle" />
              <div className="landing-loader__ring landing-loader__ring--inner" />
              <div className="landing-loader__planet" />
            </div>
            <div className="landing-loader__copy">
              <p className="landing-loader__eyebrow">COMPASS</p>
              <p className="landing-loader__title">Calibrating the agents…</p>
              <div className="landing-loader__bar"><span className="landing-loader__barFill" /></div>
            </div>
          </div>
        </div>
      )}

      <header className="pointer-events-none fixed left-0 right-0 top-0 z-50 px-3 pt-3 sm:px-6">
        <nav className="pointer-events-auto landing-nav-shell mx-auto flex max-w-6xl items-center justify-between rounded-full px-3 py-2 sm:px-4" aria-label="Primary">
          <a href="#home" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-violet-400 to-cyan-400 text-ink-950">
              <Compass className="h-5 w-5" />
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-semibold tracking-wide text-white">COMPASS</span>
              <span className="block text-[10px] uppercase tracking-[0.2em] text-white/45">Decision Engine</span>
            </span>
          </a>
          <ul className="hidden items-center gap-1 md:flex">
            {NAV.map((l) => (
              <li key={l.to}>
                {l.to.startsWith('/') ? (
                  <Link href={l.to} className="rounded-full px-3 py-2 text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white">{l.label}</Link>
                ) : (
                  <a href={l.to} className="rounded-full px-3 py-2 text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white">{l.label}</a>
                )}
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            <Link href="/dashboard" id="nav-launch" className="hidden rounded-full bg-white px-4 py-2 text-xs font-semibold text-black sm:inline-flex">Launch Dashboard</Link>
            <button className="liquid-glass flex h-9 w-9 items-center justify-center rounded-full text-white md:hidden" onClick={() => setOpen((v) => !v)} aria-label="Menu" aria-expanded={open}>
              {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </nav>
        {open && (
          <div className="pointer-events-auto mx-auto mt-2 max-w-6xl md:hidden">
            <ul className="landing-nav-shell flex flex-col gap-1 rounded-[1.75rem] px-3 py-3">
              {NAV.map((l) => (
                <li key={l.to}>
                  {l.to.startsWith('/') ? (
                    <Link href={l.to} onClick={() => setOpen(false)} className="block rounded-2xl px-4 py-3 text-sm text-white/80">{l.label}</Link>
                  ) : (
                    <a href={l.to} onClick={() => setOpen(false)} className="block rounded-2xl px-4 py-3 text-sm text-white/80">{l.label}</a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </header>

      <main>
        <section id="home" className="relative min-h-screen overflow-hidden">
          <video className="absolute inset-0 h-full w-full object-cover" src={heroSrc} autoPlay loop muted playsInline />
          <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/25 to-black/80" />
          <div className="relative z-10 flex min-h-screen flex-col justify-between px-6 pb-16 pt-28 sm:px-10 lg:px-20">
            <div className="mx-auto w-full max-w-5xl flex-1 pt-10">
              <motion.div className="liquid-glass mb-6 inline-flex items-center gap-2 rounded-full px-2 py-1.5" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15 }}>
                <span className="rounded-full bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-black">Live</span>
                <span className="pr-3 text-xs font-light text-white/70">4 agents · 25 SerpApi engines · 1 decision</span>
              </motion.div>
              <h1 className="max-w-4xl font-heading text-5xl italic leading-[0.88] tracking-[-2px] text-white sm:text-7xl lg:text-8xl">
                <BlurText text="Stop Searching. Start Deciding." delay={70} />
              </h1>
              <motion.p className="mt-8 max-w-xl font-body text-base font-light leading-relaxed text-white/55 sm:text-lg" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.85 }}>
                Twelve tabs open. Three price drops missed. Still no answer. COMPASS reads your goal, searches the live web
                through SerpApi, verifies every fact twice, and hands you one ranked, ready-to-approve plan — for a trip, a
                supplier, a job or a patent.
              </motion.p>
              <motion.div className="mt-10 flex flex-wrap items-center gap-3" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.05 }}>
                <Link href="/dashboard" id="hero-cta" className="liquid-glass-strong inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white">
                  Open the Command Center <ArrowUpRight className="h-4 w-4" />
                </Link>
                <a href="#pitch" className="rounded-full px-5 py-3 text-sm text-white/60 hover:text-white">Watch the demo ↓</a>
              </motion.div>
            </div>
            <div className="hero-metrics-grid mx-auto mt-16 grid w-full max-w-5xl gap-4 sm:grid-cols-3">
              {METRICS.map((m, i) => (
                <motion.div key={m.value} className="liquid-glass rounded-2xl p-5" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.15 + i * 0.1 }}>
                  <p className="font-heading text-4xl italic text-white">{m.value}</p>
                  <p className="mt-2 font-body text-xs font-light leading-relaxed text-white/45">{m.label}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section id="capabilities" className="section-seam landing-stack-section relative min-h-screen overflow-hidden">
          <video className="absolute inset-0 h-full w-full object-cover" src={capSrc} autoPlay loop muted playsInline style={{ transform: 'scaleX(-1)' }} />
          <div className="section-darken absolute inset-0" />
          <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-24 sm:px-10">
            <motion.span className="mb-4 font-body text-[10px] uppercase tracking-[0.3em] text-white/35" initial={{ opacity: 0, x: -12 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>The Four Agents</motion.span>
            <motion.h2 className="max-w-3xl font-heading text-4xl italic leading-[0.92] text-white sm:text-6xl lg:text-7xl" initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
              One prompt in. Four agents working. One decision out.
            </motion.h2>
            <div className="mt-12 grid gap-5 lg:grid-cols-3">
              {AGENTS.map((c, i) => (
                <motion.article key={c.title} className="liquid-glass rounded-2xl p-7" initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.12 }}>
                  <p className="mb-4 font-heading text-5xl italic text-white/15">0{i + 1}</p>
                  <h3 className="font-heading text-2xl italic text-white">{c.title}</h3>
                  <p className="mt-3 font-body text-sm font-light leading-relaxed text-white/45">{c.body}</p>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {c.tags.map((t) => (
                      <span key={t} className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] uppercase tracking-wider text-white/50">{t}</span>
                    ))}
                  </div>
                </motion.article>
              ))}
            </div>
            <motion.p className="mt-12 font-body text-xs tracking-[0.16em] text-white/30" initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}>
              SerpApi async fan-out · LangGraph · Supabase pgvector hybrid RAG · Upstash dedupe · Groq + Gemini · Langfuse traces
            </motion.p>
          </div>
        </section>

        <PitchDeck />
      </main>
    </div>
  )
}

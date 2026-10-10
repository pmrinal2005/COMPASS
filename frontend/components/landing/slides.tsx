'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import { ArrowUpRight, Brain, Compass, Gauge, Layers, Radar, RefreshCw, ShieldCheck, Terminal, Zap, Building2, UserRound } from 'lucide-react'
import { BlurText } from './BlurText'
import { HlsVideo } from './HlsVideo'

const V_TITLE = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260411_104229_49794008-3d16-4cb6-9a8c-73d7751b0e79.mp4'
const V_PROCESS = 'https://stream.mux.com/9JXDljEVWYwWu01PUkAemafDugK89o01BR6zqJ3aS9u00A.m3u8'
const V_CAPS_BG = 'https://stream.mux.com/s8pMcOvMQXc4GD6AX4e1o01xFogFxipmuKltNfSYza0200.m3u8'
const V_CAP_A = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260302_085844_21a8f4b3-dea5-4ede-be16-d53f6973bb14.mp4'
const V_CAP_B = 'https://stream.mux.com/T6oQJQ02cQ6N01TR6iHwZkKFkbepS34dkkIc9iukgy400g.m3u8'
const V_WHY = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260411_104032_69319010-2458-492b-b04d-b40a5dfa4482.mp4'
const V_STATS = 'https://stream.mux.com/NcU3HlHeF7CUL86azTTzpy3Tlb00d6iF3BmCdFslMJYM.m3u8'
const V_PROMPTS = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260406_094145_4a271a6c-3869-4f1c-8aa7-aeb0cb227994.mp4'
const V_CTA = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_024928_1efd0b0d-6c02-45a8-8847-1030900c4f63.mp4'

const eyebrow = 'font-body text-[10px] uppercase tracking-[0.3em] text-white/30'

function Bg({ src, className = 'absolute inset-0 h-full w-full object-cover', style }: { src: string; className?: string; style?: React.CSSProperties }) {
  return src.endsWith('.m3u8')
    ? <HlsVideo src={src} className={className} style={style} />
    : <video className={className} style={style} src={src} autoPlay loop muted playsInline />
}

/* 01 ───────────────────────────────────────────── Title */
export function TitleSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_TITLE} />
      <div className="relative z-10 flex h-full flex-col justify-between px-10 py-12 pb-20 lg:px-20">
        <motion.div className="flex items-center" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white"><Compass className="h-4 w-4 text-black" /></div>
          <span className="ml-2 font-heading text-lg italic text-white/80">COMPASS</span>
          <span className="mx-2 h-5 w-px bg-white/20" />
          <span className="font-body text-[10px] uppercase tracking-[0.2em] text-white/30">Product Demo</span>
        </motion.div>

        <div className="flex max-w-3xl flex-1 flex-col justify-center">
          <motion.div className="liquid-glass mb-6 inline-flex w-fit items-center gap-2 rounded-full px-2 py-1.5" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}>
            <span className="rounded-full bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-black">Live</span>
            <span className="pr-3 text-xs font-light text-white/70">Plan → Search → Compare → Act</span>
          </motion.div>
          <h2 className="mb-8 font-heading text-5xl italic leading-[0.85] tracking-[-3px] text-white md:text-7xl lg:text-8xl xl:text-[6.5rem]">
            <BlurText text="Ask once. Watch four agents decide." delay={80} />
          </h2>
          <motion.p className="mb-10 max-w-xl font-body text-base font-light leading-relaxed text-white/50 md:text-lg" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.9 }}>
            Type a goal in plain English. COMPASS fans out live SerpApi searches, cross-checks every fact, ranks your options
            with a transparent score, and hands you an action card to approve.
          </motion.p>
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.1 }}>
            <Link href="/dashboard" className="liquid-glass-strong inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium text-white">
              Launch the Command Center <ArrowUpRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </div>

        <motion.div className="flex flex-wrap items-center gap-x-6 gap-y-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.4 }}>
          <span className="text-[10px] uppercase tracking-[0.2em] text-white/30">Powered by</span>
          {['SerpApi', 'LangGraph', 'Supabase pgvector', 'Groq · Gemini', '$0 stack'].map((n) => (
            <span key={n} className="font-heading text-lg italic text-white/20 md:text-xl">{n}</span>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

/* 02 ───────────────────────────────────────────── Process */
const PROCESS = [
  { Icon: Brain, title: 'Orchestrator plans', desc: 'Your sentence is embedded, matched to a Playbook and turned into a Decision Graph — entities, constraints, sources, candidate actions.' },
  { Icon: Radar, title: 'Researcher fans out', desc: 'Parallel async SerpApi calls across Flights, Hotels, Maps, Shopping, Jobs, Scholar and more — deduplicated so repeats cost zero credits.' },
  { Icon: Gauge, title: 'Analyst ranks, Actor delivers', desc: 'A weighted matrix with anomaly checks scores every option. The winner becomes an approval card: Approve, Modify or Reject.' },
]

export function ProcessSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_PROCESS} />
      <div className="absolute inset-0 z-[1] bg-black/60" />
      <div className="relative z-10 flex h-full px-10 py-12 pb-20 lg:px-20">
        <div className="my-auto flex w-full flex-col items-start gap-12 lg:flex-row lg:gap-20">
          <div className="flex-1">
            <motion.span className={`mb-6 block ${eyebrow}`} initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>How a decision happens</motion.span>
            <motion.h2 className="mb-8 font-heading text-4xl italic leading-[0.9] tracking-tight text-white md:text-5xl lg:text-6xl xl:text-7xl" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              From one sentence to a verified, ranked, ready-to-approve plan
            </motion.h2>
            <motion.p className="max-w-xl font-body text-sm font-light leading-relaxed text-white/40 md:text-base" initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}>
              Not another chatbot that guesses. Every price, rating and deadline has to be corroborated by at least two independent
              sources before it reaches the ranking. If confidence is low, COMPASS re-plans itself — twice at most — then tells you honestly what it couldn&apos;t verify.
            </motion.p>
          </div>
          <div className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
            {PROCESS.map((c, i) => (
              <motion.div key={c.title} className="liquid-glass rounded-2xl p-6 lg:p-7" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.12 }}>
                <div className="mb-3 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/15 to-white/5"><c.Icon className="h-5 w-5 text-white/80" /></div>
                  <h3 className="font-body text-base font-semibold text-white">{c.title}</h3>
                </div>
                <p className="pl-[52px] font-body text-sm font-light leading-relaxed text-white/40">{c.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* 03 ───────────────────────────────────────────── Two lenses */
const LENSES = [
  { video: V_CAP_A, Icon: UserRound, title: 'COMPASS Go — for everyday life', body: '“Plan a 4-day Tokyo trip under $1,200.” Flights, hotels, local spots and currency in one verified shortlist — with price-drop watches that keep working after you close the tab.' },
  { video: V_CAP_B, Icon: Building2, title: 'COMPASS Pro — for operators', body: '“Source 3 reliable suppliers for bulk earbuds.” Vendor matrix across price, MOQ and reviews, risk news, and a draft RFQ email waiting for your sign-off. Same engine. Different lens.' },
]

export function CapabilitiesSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden bg-black">
      <HlsVideo src={V_CAPS_BG} className="absolute inset-0 h-full w-full object-cover" style={{ opacity: 0.5 }} />
      <div className="relative z-10 flex h-full flex-col px-10 py-12 pb-20 lg:px-20">
        <motion.span className={`mb-4 ${eyebrow}`} initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>Two lenses · one engine</motion.span>
        <motion.h2 className="mb-8 font-heading text-6xl italic leading-[0.85] tracking-tight text-white md:text-8xl lg:mb-auto lg:text-9xl xl:text-[10rem]" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
          Casual.<br />Enterprise. Same brain.
        </motion.h2>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
          {LENSES.map((c, i) => (
            <motion.div key={c.title} className="liquid-glass flex flex-col overflow-hidden rounded-2xl" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 + i * 0.15 }}>
              <div className="relative h-36 overflow-hidden lg:h-52"><Bg src={c.video} className="h-full w-full object-cover" /></div>
              <div className="p-6 lg:p-8">
                <h3 className="mb-2 flex items-center gap-2 font-heading text-lg italic leading-tight text-white md:text-xl"><c.Icon className="h-4 w-4 text-white/60" />{c.title}</h3>
                <p className="font-body text-sm font-light leading-relaxed text-white/40">{c.body}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* 04 ───────────────────────────────────────────── Why COMPASS */
const WHY = [
  { Icon: ShieldCheck, title: 'Two-source truth', desc: 'A price, rating or deadline is “verified” only when two independent sources agree. Single-source claims are flagged, never silently trusted.' },
  { Icon: RefreshCw, title: 'Re-plans when reality moves', desc: 'A fare spikes mid-search? The anomaly detector catches it, the Orchestrator re-plans (capped at two loops) and pivots to the next best option.' },
  { Icon: Zap, title: 'Human stays in charge', desc: 'Anything financial, legal or irreversible stops at an Approve / Modify / Reject card. COMPASS prepares — you decide.' },
  { Icon: Layers, title: 'Credit-smart by design', desc: 'Every call is fingerprinted and cached. A live credit meter shows what each session costs before expensive fan-outs fire.' },
]

export function WhyUsSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_WHY} />
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 z-[1] h-[50%]" style={{ background: 'linear-gradient(to top, black, transparent)' }} />
      <div className="relative z-10 flex h-full flex-col px-10 py-12 pb-20 lg:px-20">
        <div className="mb-auto flex flex-col lg:flex-row lg:items-end lg:justify-between">
          <div>
            <motion.span className={`mb-4 block ${eyebrow}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>Why COMPASS</motion.span>
            <motion.h2 className="font-heading text-3xl italic leading-[0.9] tracking-tight text-white md:text-4xl lg:text-5xl" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
              Search tells you what exists.<br />COMPASS tells you what to do.
            </motion.h2>
          </div>
          <motion.p className="mt-4 max-w-sm font-body text-sm font-light text-white/35 lg:mt-0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
            Most tools stop at an answer. COMPASS closes the loop — verified evidence, explainable ranking, and a one-click action.
          </motion.p>
        </div>
        <div className="flex flex-1 items-end">
          <div className="grid w-full grid-cols-2 gap-4 lg:grid-cols-4 lg:gap-6">
            {WHY.map((c, i) => (
              <motion.div key={c.title} className="liquid-glass flex flex-col rounded-2xl p-6 lg:p-8" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.1 }}>
                <div className="liquid-glass-strong mb-6 flex h-10 w-10 items-center justify-center rounded-full"><c.Icon className="h-4 w-4 text-white" /></div>
                <h3 className="mb-2 font-body text-sm font-semibold text-white md:text-base">{c.title}</h3>
                <p className="font-body text-xs font-light leading-relaxed text-white/40">{c.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* 05 ───────────────────────────────────────────── Numbers */
const STATS = [
  { n: '25', d: 'SerpApi engines wired in — Flights, Hotels, Maps, Shopping, Jobs, Scholar, Patents and more' },
  { n: '7', d: 'Declarative Playbooks: trips, deals, local, suppliers, careers, prior-art and SEO' },
  { n: '2×', d: 'Independent-source corroboration before any fact is trusted — and ≤2 re-plans per session' },
  { n: '$0', d: 'To run. Free-tier cloud everywhere, zero Docker, and it works on a 4 GB laptop' },
]

export function StatsSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_STATS} style={{ filter: 'saturate(0)' }} />
      <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/50 to-black/80" />
      <div className="relative z-10 flex h-full min-h-0 flex-col px-5 pb-20 pt-7 sm:px-10 sm:pb-24 sm:pt-10 lg:px-16 xl:px-20">
        <header className="shrink-0">
          <motion.span className={`mb-3 block ${eyebrow}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>By the numbers</motion.span>
          <motion.h2 className="max-w-4xl font-heading text-[clamp(1.85rem,4.4vw,4.1rem)] italic leading-[0.95] tracking-tight text-white" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            Serious engine. Featherweight footprint.
          </motion.h2>
        </header>
        <div className="relative mt-5 flex min-h-0 flex-1 flex-col justify-center sm:mt-7">
          <div className="stats-glow-line pointer-events-none absolute left-0 right-0 top-1/2 z-0 hidden h-px -translate-y-1/2 sm:block" />
          <div className="relative z-10 grid min-h-0 grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2 sm:grid-rows-2 sm:gap-x-12 sm:gap-y-10 lg:gap-x-20 lg:gap-y-12">
            {STATS.map((s, i) => (
              <motion.div key={s.n} className="flex min-h-0 min-w-0 flex-col justify-center gap-2 sm:gap-3" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.28 + i * 0.08 }}>
                <div className="h-px w-full max-w-lg bg-gradient-to-r from-white/50 via-violet-400/55 to-transparent" />
                <p className="font-heading text-[clamp(2.4rem,5.2vw,4.6rem)] italic leading-none text-white">{s.n}</p>
                <p className="max-w-[34ch] text-pretty break-words font-body text-[0.95rem] leading-[1.45] text-white/75 sm:max-w-[36ch] sm:text-base lg:text-lg">{s.d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* 06 ───────────────────────────────────────────── Prompts to try */
const PROMPTS = [
  { lens: 'Go', tag: 'LifeOps', q: 'Plan a 4-day Tokyo trip under $1,200, flights + hotel.', out: 'Ranked flight + stay combos, FX-aware budget, price watch, .ics itinerary.' },
  { lens: 'Pro', tag: 'Procurement', q: 'Source 3 reliable suppliers for bulk Bluetooth earbuds — compare price, MOQ and reviews.', out: 'Vendor decision matrix, risk news scan, RFQ email draft queued for approval.' },
  { lens: 'Pro', tag: 'Research & IP', q: 'Prior-art brief on solid-state battery electrolytes.', out: 'Scholar + Patents + News cross-check with a citation-backed summary report.' },
]

export function PromptsSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_PROMPTS} />
      <div className="absolute inset-0 bg-black/45" />
      <div className="relative z-10 flex h-full flex-col px-10 py-12 pb-20 lg:px-20">
        <motion.span className={`mb-4 ${eyebrow}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>Try these prompts</motion.span>
        <motion.h2 className="mb-auto font-heading text-3xl italic leading-[0.9] tracking-tight text-white md:text-4xl lg:text-5xl" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          Three questions.<br />Three finished decisions.
        </motion.h2>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3 lg:gap-6">
          {PROMPTS.map((t, i) => (
            <motion.div key={t.q} className="liquid-glass flex flex-col justify-between rounded-2xl p-8 lg:p-10" initial={{ opacity: 0, y: 25 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.12 }}>
              <div className="mb-8">
                <span className="mb-4 block font-heading text-3xl italic text-white/15">“</span>
                <p className="font-body text-sm font-light italic leading-relaxed text-white/80 lg:text-base">{t.q}</p>
              </div>
              <div className="border-t border-white/10 pt-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded-full bg-white/10 px-2.5 py-0.5 font-body text-[10px] font-semibold uppercase tracking-wider text-white/70">{t.lens}</span>
                  <span className="font-body text-xs font-light text-white/40">{t.tag}</span>
                </div>
                <p className="font-body text-xs font-light leading-relaxed text-white/50">→ {t.out}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* 07 ───────────────────────────────────────────── CTA */
export function CtaSlide() {
  return (
    <section className="relative h-full w-full overflow-hidden">
      <Bg src={V_CTA} />
      <div className="relative z-10 flex h-full flex-col px-10 py-12 pb-20 lg:px-20">
        <motion.span className={`mb-4 ${eyebrow}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>Your turn</motion.span>
        <div className="flex flex-1 flex-col items-start gap-12 lg:flex-row lg:items-center lg:gap-20">
          <div className="max-w-2xl flex-1">
            <motion.h2 className="mb-6 font-heading text-5xl italic leading-[0.85] tracking-tight text-white md:text-6xl lg:text-7xl xl:text-8xl" initial={{ opacity: 0, x: -25 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
              Your next big decision<br />is one prompt away.
            </motion.h2>
            <motion.p className="mb-10 max-w-md font-body text-sm font-light leading-relaxed text-white/40 md:text-base" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}>
              Open the Command Center and watch the thought-tree, the live SerpApi call log and the decision matrix build in real time.
              No backend? It falls back to a pre-recorded Demo Mode — zero credits spent.
            </motion.p>
            <motion.div className="flex flex-wrap items-center gap-4" initial={{ opacity: 0, x: -15 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.7 }}>
              <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 font-body text-sm font-semibold text-black">
                Enter the Dashboard <ArrowUpRight className="h-4 w-4" />
              </Link>
              <a href="#home" className="liquid-glass-strong inline-flex rounded-full px-6 py-3 font-body text-sm font-medium text-white">Back to top</a>
            </motion.div>
          </div>
          <motion.div className="liquid-glass w-full max-w-xs rounded-2xl p-8 lg:p-10" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}>
            <div className="mb-5 flex items-center gap-3">
              <div className="liquid-glass-strong flex h-10 w-10 items-center justify-center rounded-full"><Terminal className="h-4 w-4 text-white" /></div>
              <span className="font-body text-sm font-medium text-white">Inside the dashboard</span>
            </div>
            <ul className="space-y-2 font-body text-sm text-white/70">
              <li>· Animated Orchestrator thought-tree</li>
              <li>· Live SerpApi call log by engine</li>
              <li>· Fresh vs. cached retrieval heat-map</li>
              <li>· Decision matrix + confidence score</li>
              <li>· Approve / Modify / Reject action cards</li>
            </ul>
          </motion.div>
        </div>
        <motion.div className="mt-8 flex justify-between border-t border-white/10 pt-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.0 }}>
          <span className="text-xs text-white/30">© 2026 COMPASS · One decision engine, infinite verticals.</span>
          <a href="https://github.com/pmrinal2005/COMPASS" target="_blank" rel="noreferrer" className="text-xs text-white/30 hover:text-white/60">GitHub</a>
        </motion.div>
      </div>
    </section>
  )
}

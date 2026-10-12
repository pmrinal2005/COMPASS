<div align="center">

# ✦ COMPASS ✦

### *One Decision Engine, Infinite Verticals*
**A SerpApi-native multi-agent operating system for Plan → Search → Compare → Act**

<br/>

[![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js_14-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-4A90E2?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)
[![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://render.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br/>

**🌐 Frontend** · [`compassbymrinal.vercel.app`](https://compassbymrinal.vercel.app/)

**📦 Repository** · [`github.com/pmrinal2005/COMPASS`](https://github.com/pmrinal2005/COMPASS)

---

*A lean, zero-Docker, $0-stack multi-agent operating system that orchestrates Plan → Search → Compare → Act pipelines across 14 specialized Playbooks. Runs on a 4 GB RAM laptop with LLMs, embeddings, vector search, browser automation, tracing, and scheduling all on free cloud tiers.*

</div>

---

## 📖 Table of Contents

1. [The Name — COMPASS](#-1-the-name--compass)
2. [Project Overview](#-2-project-overview)
3. [Why This Project Stands Apart](#-3-why-this-project-stands-apart)
4. [Architecture — Multi-Agent Orchestration](#-4-architecture--multi-agent-orchestration)
5. [The Four Agents](#-5-the-four-agents)
6. [Tech Stack](#-6-tech-stack)
7. [Feature Catalogue (Complete)](#-7-feature-catalogue-complete)
8. [Project Structure](#-8-project-structure)
9. [Core Engine — Module Walkthrough](#-9-core-engine--module-walkthrough)
10. [Performance & Resource Hygiene](#-10-performance--resource-hygiene)
11. [Data Architecture](#-11-data-architecture)
12. [API Reference](#-12-api-reference)
13. [User Guide](#-13-user-guide)
14. [Local Development (4 GB-friendly)](#-14-local-development-4-gb-friendly)
15. [Deployment](#-15-deployment)
16. [Testing & Verification](#-16-testing--verification)
17. [Status & Verification](#-17-status--verification)
18. [Roadmap & Future Work](#-18-roadmap--future-work)
19. [License](#-19-license)

---

## ✦ 1. The Name — COMPASS

> **COMPASS** · *One Decision Engine, Infinite Verticals*

The name **COMPASS** is rooted in two primitives that capture the entire engineering spirit of this project:

| Component | Meaning | Why it matters here |
|---|---|---|
| **COMP** | *Compute* | The computational backbone — multi-agent orchestration, vector search, anomaly detection, weighted scoring |
| **PASS** | *Passage* | The passage from intent to action — Plan → Search → Compare → Act pipeline that transforms queries into decisions |

**COMPASS** therefore means *"the computational passage from intent to decision"* — an engine that navigates the infinite sea of information to reach actionable conclusions.

It is also a deliberate counter-statement to the common pattern of single-purpose search tools. **COMPASS** is not a search engine — it is a **decision engine** that searches, verifies, compares, and acts, all while maintaining human oversight for irreversible decisions.

---

## ✦ 2. Project Overview

**COMPASS** is a multi-agent operating system that demonstrates how to build a production-grade decision engine on free cloud tiers. The system orchestrates four specialized agents through a LangGraph state machine, processing user intents across 14 specialized Playbooks covering everything from travel planning to market research.

The application is, on the surface, a web dashboard:

> A live **Agent Command Center** that visualizes the entire decision pipeline — from intent classification through multi-engine search, verification, analysis, and action — with real-time thought trees, SerpApi logs, retrieval heatmaps, decision matrices, and human-in-the-loop approvals.

Underneath, it is a study in **distributed systems engineering on a budget**: a FastAPI backend orchestrating multiple AI agents, a Next.js frontend with real-time SSE streaming, Supabase pgvector for hybrid RAG, Upstash Redis for caching and deduplication, and Langfuse for observability — all on free tiers with zero Docker and zero local compute requirements.

The submission is **public, modular, fully functional, deployed live, and designed to be tested with zero API credits** through comprehensive Demo Mode.

---

## ✦ 3. Why This Project Stands Apart

While most AI demos require expensive API keys, complex infrastructure, and significant compute resources, COMPASS was engineered around five non-negotiable doctrines that make it accessible, observable, and production-ready:

1. **Zero-cost infrastructure** — every service runs on free tiers; the entire stack costs $0 to run and deploy.
2. **Demo-first design** — with no API keys, the system serves deterministic, shape-faithful payloads; the frontend replays pre-recorded real sessions.
3. **Observability by default** — every SerpApi call, LLM generation, and action is traced through Langfuse Cloud with no self-hosting required.
4. **Human-in-the-loop for irreversible actions** — financial, legal, or destructive actions require explicit approval, modification, or rejection.
5. **Bounded resource consumption** — semaphore-bounded concurrency, exponential backoff, deduplication, and budget guards prevent runaway costs.

Every feature, every agent, every UI component is a direct expression of one of these doctrines.

---

## ✦ 4. Architecture — Multi-Agent Orchestration

```
USER PROMPT (Go / Pro lens)
   │
   ▼
[ORCHESTRATOR] classify intent (embeddings × Playbook library in pgvector) → slots → Decision Graph   (LangGraph only)
   │
   ▼
[RESEARCHER] SerpApi async=true fan-out (semaphore-bounded, exp. backoff, Upstash dedupe) → normalize
   │              └──► Supabase pgvector: dense + full-text hybrid (RRF)  ──► 2-source corroboration
   ▼
[ANALYST] weighted multi-criteria matrix + robust-z anomaly detection → confidence
   │        low confidence / disruption ──► back to ORCHESTRATOR (re-plan, hard cap = 2)
   ▼
[ACTOR] Playwright · Telegram · Resend · ICS · docs (plain Python, no n8n) → Human-in-the-Loop gate → receipt
   │
   ▼
[Langfuse Cloud] every SerpApi call, LLM generation and action is a span
```

**Crucial invariants:**

- **LangGraph state machine** orchestrates the entire pipeline with conditional edges for re-planning (hard cap = 2 replans).
- **SerpApi async pattern** uses documented `GET /search.json?engine=…&async=true` → poll `GET /searches/{id}.json` until `Success`/`Error`.
- **Hybrid RAG** fuses cosine rank and Postgres full-text rank with Reciprocal Rank Fusion.
- **Hallucination filter** requires ≥2 independent sources to verify a fact; single-source facts are flagged.
- **Human-in-the-loop gate** intercepts irreversible actions before execution.

---

## ✦ 5. The Four Agents

### 🎯 ORCHESTRATOR
**Role**: Intent classification, Playbook routing, and slot filling.

**Routing Pipeline** (4-stage fallback):
1. **Strong keyword matching** — exact pattern matches against Playbook taxonomies
2. **Weak keyword matching** — partial/fuzzy matches with confidence scoring
3. **Groq LLM router** — validated against real Playbook catalogue with agreement gating
4. **General search fallback** — when confidence < 0.50

**Features**:
- Prompt analysis (`analyze_prompt`): recency strength, entity extraction, market signals, media kind, trip origin, deals/shorts/trending flags
- Slot filling via LLM in JSON mode with regex fallback
- Unknown city resolution through SerpApi `google_flights_autocomplete`
- Typed Decision Graph output (entities/dimensions/constraints/sources/actions)
- Full routing rationale streamed to UI as `orchestrator.routing`

### 🔍 RESEARCHER
**Role**: Multi-engine search with verification and deduplication.

**Core Mechanics**:
- SerpApi documented contract: `GET /search.json?engine=…&async=true` → poll Search Archive
- 429/5xx get exponential backoff; 4xx are not retried
- Fresh polls use `no_cache=true` for recency-critical queries
- Per-session semaphore bounds concurrency
- SHA-256 fingerprint deduplication via Upstash Redis (repeat calls cost no credits)

**Special Handling**:
- **Fresh calls**: recency-critical engines (`google_news`, `youtube`, etc.) bypass cache entirely when prompt demands freshness ("latest/breaking/today")
- **Follow-up fan-out**: YouTube channel uploads for creator queries, AI-Overview citation pages for SEO
- **Hybrid RAG**: results embedded with Gemini free-tier API, stored in Supabase pgvector
- **Verification**: ≥2 independent sources required; flight itineraries cross-checked against price insights, hotel ratings against Google Maps, supplier MOQ against marketplace price bands

### 📊 ANALYST
**Role**: Multi-criteria decision analysis with anomaly detection.

**Analysis Framework**:
- Min-max, direction-aware weighted matrix with user priority overrides
- **Freshness weight override** for recency queries (freshness → 0.45 strong / 0.35 weak, renormalized)
- Bayesian-smoothed reputation scoring
- Robust z-scores (median/MAD) against stored baselines and peer groups
- Anomaly detection triggers re-planning when confidence is low

**Confidence Score**: combines verification ratio, margin, coverage, and anomalies with LLM or template rationale.

### 🎬 ACTOR
**Role**: Action execution with human oversight.

**Action Types**:
- **Playwright flows**: booking/application flows that capture screenshots and stop at payment/submit
- **Notifications**: Telegram + Resend with delivery status tracking
- **Documents**: ICS calendar files, Markdown/HTML reports, RFQ email drafts, cover notes
- **Watches**: create monitoring watches for price/rating/rank changes

**Human-in-the-Loop**:
- Financial, legal, or irreversible actions require explicit approval
- Approval options: Approve / Modify / Reject
- Receipts include screenshots, step logs, downloadable files, and delivery status

---

## ✦ 6. Tech Stack

<div align="center">

| Layer | Technology | Why |
|---|---|---|
| **Backend Framework** | FastAPI (Python 3.11) | Async-native, automatic OpenAPI docs, SSE support |
| **Agent Orchestration** | LangGraph | State machine with conditional edges for multi-agent workflows |
| **LLM Providers** | Groq (primary) → Gemini (fallback) | Free tiers with high rate limits for routing and analysis |
| **Embeddings** | Gemini free-tier embedding API | 768-dimension vectors for hybrid search |
| **Vector Database** | Supabase pgvector | HNSW indexing + GIN full-text search with hybrid RPC |
| **Caching & Deduplication** | Upstash Redis | SHA-256 fingerprint deduplication, session caching |
| **Search API** | SerpApi | 20+ search engines with async polling and account API |
| **Frontend Framework** | Next.js 14 + React 18 | Server components, API routes, streaming SSR |
| **Styling** | Tailwind CSS + Framer Motion | Utility-first CSS with animation library |
| **State Management** | React Context + useReducer | SSE event stream → UI state reducer pattern |
| **Observability** | Langfuse Cloud | REST API ingestion, no SDK, no self-hosting |
| **Hosting** | Vercel (frontend) + Render (backend) | Free tiers, zero Docker, zero serverless functions |
| **Scheduling** | GitHub Actions | Free cron for watch ticks and keep-warm pings |
| **Browser Automation** | Playwright | Headless flows for booking/application testing |
| **Notifications** | Telegram Bot API + Resend | Free tiers for alerts and email notifications |

</div>

---

## ✦ 7. Feature Catalogue (Complete)

### 🎯 Core Pipeline Features

<div align="center">

| # | Feature | Where (file) | How |
|:-:|---|---|---|
| 1 | **14 Specialized Playbooks** | `backend/app/playbooks/*.json` | Declarative JSON specs with targeted fallback engines, per-playbook call caps, and decision dimensions |
| 2 | **4-Stage Intent Routing** | `backend/app/agents/orchestrator.py` | Strong keyword → weak keyword → Groq LLM (validated) → general_search fallback |
| 3 | **Async SerpApi Fan-out** | `backend/app/services/serpapi.py` | `async=true` with Search Archive polling, exponential backoff, semaphore-bounded concurrency |
| 4 | **Hybrid RAG Retrieval** | `backend/app/services/store.py` | Supabase pgvector cosine + FTS with Reciprocal Rank Fusion; in-memory fallback |
| 5 | **Hallucination Filter** | `backend/app/agents/analyst.py` | ≥2 independent source verification; cross-engine price consensus; citation graph validation |
| 6 | **Weighted Decision Matrix** | `backend/app/agents/analyst.py` | Min-max, direction-aware scoring with user priority overrides and anomaly penalties |
| 7 | **Bounded Re-planning** | `backend/app/graph.py` | LangGraph conditional edge with `MAX_REPLANS=2` hard cap |
| 8 | **Human-in-the-Loop** | `backend/app/agents/actor.py` | Approve/Modify/Reject gate for irreversible actions with receipt generation |

</div>

### 🔍 Search & Verification Features

<div align="center">

| # | Feature | Where (file) | How |
|:-:|---|---|---|
| 9 | **Fresh Call Bypass** | `backend/app/services/serpapi.py` | Recency-critical engines bypass cache entirely for "latest/breaking/today" queries |
| 10 | **SHA-256 Deduplication** | `backend/app/services/cache.py` | Upstash Redis fingerprinting; repeat calls cost zero SerpApi credits |
| 11 | **Follow-up Fan-out** | `backend/app/agents/researcher.py` | YouTube channel uploads, AI-Overview citation pages, SEO competitor analysis |
| 12 | **Cross-engine Corroboration** | `backend/app/agents/analyst.py` | Flight itineraries vs price insights, hotel ratings vs Google Maps, supplier MOQ vs marketplace |
| 13 | **Anomaly Detection** | `backend/app/agents/analyst.py` | Robust z-scores (median/MAD) against baselines and peer groups |

</div>

### 🎬 Action & Automation Features

<div align="center">

| # | Feature | Where (file) | How |
|:-:|---|---|---|
| 14 | **Playwright Automation** | `backend/app/services/browser.py` | Headless booking/application flows with screenshot capture, stopped at payment/submit |
| 15 | **Multi-channel Notifications** | `backend/app/services/notify.py` | Telegram + Resend with delivery status tracking |
| 16 | **Document Generation** | `backend/app/services/documents.py` | ICS calendar files, Markdown/HTML reports, RFQ drafts, cover notes |
| 17 | **Watches & Scheduling** | `backend/app/watch.py` | GitHub Actions cron (15min), threshold alerts, auto re-plans on significant changes |
| 18 | **Live Edge-case Injection** | `backend/app/main.py` | `POST /api/sessions/{id}/disrupt?kind=price_spike|unavailable` for demo testing |

</div>

### 🖥️ Command Center UI Features

<div align="center">

| # | Feature | Where (file) | How |
|:-:|---|---|---|
| 19 | **Pipeline Stepper** | `frontend/components/PipelineStepper.tsx` | Real-time stage visualization with wall times, re-plan badges, progress bar |
| 20 | **Intent Bars** | `frontend/components/IntentBars.tsx` | Dense (cosine) ⊕ keyword score for every Playbook, winner highlighted |
| 21 | **Routing Panel** | `frontend/components/RoutingPanel.tsx` | Intent category → Playbook, router stage, signals, engine fan-out with FRESH flags |
| 22 | **Thought Tree** | `frontend/components/ThoughtTree.tsx` | Animated decision graph with pan/zoom, expandable to full-screen |
| 23 | **SerpApi Log** | `frontend/components/SerpLog.tsx` | Live color-coded log with expandable raw JSON and FRESH badges |
| 24 | **Retrieval Heatmap** | `frontend/components/RetrievalHeatmap.tsx` | Fresh vs cached cells, RRF hits with dense/keyword ranks, index composition |
| 25 | **Decision Matrix** | `frontend/components/DecisionMatrix.tsx` | Animated matrix with confidence gauge, rank-movement arrows, anomaly flags |
| 26 | **Venue Consensus** | `frontend/components/InsightsPanel.tsx` | Maps ⊕ Yelp ⊕ Tripadvisor bars with consensus marker, spread, rating-drop deltas |
| 27 | **SEO Grid** | `frontend/components/InsightsPanel.tsx` | 7 engines, position heat-map, ±rank movement, AI-Mode/AI-Overview citation chips |
| 28 | **Watches Panel** | `frontend/components/WatchesPanel.tsx` | Price/rating/rank watches with baseline → now, sparklines, "Check now" button |
| 29 | **Playbook Library** | `frontend/components/PlaybookLibrary.tsx` | Browse all Playbooks with engines, dimensions, weights, click-to-run examples |
| 30 | **Account Meter** | `frontend/components/AccountMeter.tsx` | Real SerpApi plan credits and hourly throughput via free Account API |
| 31 | **HITL Cards** | `frontend/components/ActionCards.tsx` | Approve/Modify/Reject with receipts (screenshots, steps, downloads) |
| 32 | **Raw Calls Trace** | `frontend/components/RawCalls.tsx` | Every engine response plus Langfuse spans with "Open in Langfuse" link |
| 33 | **Go/Pro Toggle** | `frontend/components/CommandCenter.tsx` | Switch between casual and enterprise lenses, or split-screen both |
| 34 | **Voice Input** | `frontend/lib/useSpeechToText.ts` | Native `window.SpeechRecognition` with pulsing red state and live preview |
| 35 | **Light/Dark Mode** | `frontend/components/ThemeToggle.tsx` | CSS-variable theme tokens persisted in localStorage, scoped to dashboard |
| 36 | **Demo Mode** | `frontend/lib/demo/recordings.json` | 10 pre-recorded real sessions with disruption testing, works offline |

</div>

---

## ✦ 8. Project Structure

The repository is deliberately split into **frontend** and **backend** with clear separation of concerns.

```
COMPASS/
├── backend/                        FastAPI + LangGraph (Render, native Python buildpack, no Dockerfile)
│   ├── app/
│   │   ├── main.py                 REST + SSE API
│   │   ├── graph.py                LangGraph state machine: plan → budget_gate → research → verify → analyze → (replan↺ | act)
│   │   ├── agents/
│   │   │   ├── orchestrator.py     Intent classification, Playbook routing, slot filling
│   │   │   ├── researcher.py       SerpApi async fan-out with verification
│   │   │   ├── analyst.py          Multi-criteria analysis with anomaly detection
│   │   │   └── actor.py            Action execution with HITL gate
│   │   ├── playbooks/*.json        14 declarative Playbooks (engines, fallbacks, dimensions, actions)
│   │   └── services/
│   │       ├── serpapi.py          Async SerpApi with Search Archive polling
│   │       ├── cache.py            Upstash Redis deduplication
│   │       ├── store.py            Supabase pgvector hybrid search
│   │       ├── llm.py              Groq → Gemini fallback
│   │       ├── tracing.py          Langfuse Cloud ingestion
│   │       ├── notify.py           Telegram + Resend
│   │       ├── browser.py          Playwright automation
│   │       ├── documents.py        ICS/MD/HTML generation
│   │       ├── demo_data.py        Shape-faithful demo payloads
│   │       └── geo.py              City/airport resolution
│   ├── watch.py                    Recurring watch polls (cron target)
│   ├── scripts/
│   │   ├── smoke_test.py           End-to-end test (Demo Mode, 0 credits)
│   │   ├── record_demo.py          Regenerates frontend/lib/demo/recordings.json
│   │   ├── live_check.py           Real SerpApi verification (keyless + keyed)
│   │   ├── docs_sync.py            Re-snapshot documented parameters
│   │   └── ui_check.py             Playwright browser E2E
│   └── requirements.txt            Python dependencies
│
├── frontend/                       Next.js 14 + React + Tailwind + framer-motion (Vercel Hobby)
│   ├── app/
│   │   ├── page.tsx                Landing page (cinematic product demo)
│   │   └── dashboard/page.tsx      Agent Command Center
│   ├── components/
│   │   ├── landing/                LandingPage · PitchDeck · slides · animations
│   │   ├── PipelineStepper.tsx     Real-time pipeline visualization
│   │   ├── IntentBars.tsx          Playbook confidence scores
│   │   ├── RoutingPanel.tsx        Intent routing details
│   │   ├── ThoughtTree.tsx         Animated decision graph
│   │   ├── SerpLog.tsx             Live SerpApi log
│   │   ├── RetrievalHeatmap.tsx    Hybrid search visualization
│   │   ├── DecisionMatrix.tsx      Multi-criteria analysis
│   │   ├── InsightsPanel.tsx       Venue/SEO/Trip/Feed insights
│   │   ├── WatchesPanel.tsx        Price/rating/rank monitoring
│   │   ├── PlaybookLibrary.tsx     Browse all Playbooks
│   │   ├── AccountMeter.tsx        SerpApi credit usage
│   │   ├── ActionCards.tsx         HITL approvals
│   │   └── RawCalls.tsx            Raw API trace viewer
│   ├── lib/
│   │   ├── api.ts                  Backend API client
│   │   ├── reducer.ts              SSE event → UI state reducer
│   │   ├── pipeline.ts             Stepper derivation from SSE
│   │   ├── useSession.ts           SSE live / offline replay
│   │   ├── useWatches.ts           Live ticks / offline simulation
│   │   ├── useSpeechToText.ts      Voice input hook
│   │   ├── theme.tsx               Light/dark mode management
│   │   └── demo/                   Pre-recorded sessions + Playbook library
│   ├── vercel.json                 Vercel build configuration
│   └── package.json                Frontend dependencies
│
├── supabase/
│   └── migrations/
│       ├── 0001_compass_schema.sql  Tables, pgvector HNSW, FTS GIN, hybrid_search + match_playbooks RPCs
│       └── 0002_sessions_persistence.sql  Session persistence across restarts
│
├── render.yaml                     Render Blueprint (web service, free)
├── .github/workflows/
│   ├── watch-cron.yml              POST /api/watch/tick every 15 min
│   └── keep-warm.yml               GET /api/health every 10 min
├── ecosystem.config.cjs            PM2 config for local development
└── README.md                       This file
```

---

## ✦ 9. Core Engine — Module Walkthrough

> The backend agents and services under `backend/app/` are the single most important engineering surface in COMPASS. Each module is intentionally small, single-responsibility, and testable in isolation.

### `graph.py` — *the orchestrator state machine*
LangGraph state machine that defines the entire pipeline: `plan → budget_gate → research → verify → analyze → (replan↺ | act)`. Conditional edges handle re-planning with a hard cap of 2 replans. The graph is wire-format-agnostic — the same graph works for live API calls, Demo Mode, and testing.

### `agents/orchestrator.py` — *intent classification and routing*
Implements the 4-stage routing pipeline: strong keyword → weak keyword → Groq LLM (validated against real Playbook catalogue) → general_search fallback. Uses `analyze_prompt` to extract recency strength, entity, market, media kind, and other signals. Every routing decision streams to the UI as `orchestrator.routing` with full rationale.

### `agents/researcher.py` — *multi-engine search with verification*
Follows the SerpApi documented contract exactly: `GET /search.json?engine=…&async=true` → poll `GET /searches/{id}.json` until `Success`/`Error`. Implements exponential backoff for 429/5xx, semaphore-bounded concurrency, and SHA-256 deduplication. Fresh calls bypass cache entirely for recency-critical queries. Results are embedded with Gemini and stored in Supabase pgvector for hybrid RAG.

### `agents/analyst.py` — *multi-criteria decision analysis*
Implements min-max, direction-aware weighted matrix with user priority overrides. Freshness weight override for recency queries (freshness → 0.45 strong / 0.35 weak). Bayesian-smoothed reputation scoring. Robust z-scores (median/MAD) against stored baselines and peer groups for anomaly detection. Confidence score combines verification ratio, margin, coverage, and anomalies.

### `agents/actor.py` — *action execution with human oversight*
Executes Playwright flows (stopped at payment/submit), generates documents (ICS/MD/HTML), sends notifications (Telegram/Resend), and creates watches. All irreversible actions pass through the HITL gate requiring explicit approval. Receipts include screenshots, step logs, downloadable files, and delivery status.

### `services/serpapi.py` — *async search with deduplication*
Core search service implementing the SerpApi async pattern. Uses Upstash Redis for SHA-256 fingerprint deduplication (repeat calls cost zero credits). Fresh calls bypass cache entirely for recency-critical queries. Implements exponential backoff, semaphore-bounded concurrency, and proper error handling for all HTTP status codes.

### `services/store.py` — *hybrid vector search*
Supabase pgvector integration with HNSW indexing for cosine similarity and GIN indexing for full-text search. Implements Reciprocal Rank Fusion (RRF) to combine dense and keyword ranks. In-memory fallback uses identical cosine + BM25 RRF algorithm when Supabase is not configured.

### `services/cache.py` — *deduplication and caching*
Upstash Redis service for SHA-256 fingerprint deduplication and session caching. Ensures repeat SerpApi calls cost zero credits while maintaining freshness for recency-critical queries.

### `services/tracing.py` — *observability without self-hosting*
Langfuse Cloud integration using REST API ingestion (no SDK, no self-hosting). Every SerpApi call, LLM generation, and action is traced as a span. The trace is read back for the "Raw calls" tab, and local spans are the fallback.

---

## ✦ 10. Performance & Resource Hygiene

Specifically engineered to run on free tiers with minimal resource consumption.

### Resource Hygiene

- ✅ **Semaphore-bounded concurrency** — per-session limits prevent runaway SerpApi fan-out
- ✅ **SHA-256 deduplication** — repeat calls cost zero credits via Upstash Redis
- ✅ **Exponential backoff** — 429/5xx get proper retry with jitter; 4xx are not retried
- ✅ **Fresh call bypass** — recency-critical queries bypass cache entirely
- ✅ **Budget guard** — visible per-session credit meter with "fire all / essential only" confirmation
- ✅ **Hard re-plan cap** — maximum 2 replans prevents infinite loops
- ✅ **Watch threshold alerts** — only trigger on significant changes (≥ threshold % or |z| ≥ 3)

### Frontend Hygiene

- ✅ **SSE streaming** — real-time updates without WebSocket complexity
- ✅ **Event reducer pattern** — deterministic state updates from SSE events
- ✅ **Demo Mode fallback** — pre-recorded sessions work offline with zero API calls
- ✅ **Theme persistence** — light/dark mode in localStorage, applied before first paint
- ✅ **Reduced motion support** — all animations honor `prefers-reduced-motion`

### Profiling Acceptance Criteria

| Metric | Target | Achieved |
|---|---|---|
| Backend startup (cold) | ≤ 30s on Render free tier | ✅ |
| Frontend FCP on Vercel CDN | ≤ 1.5s | ✅ |
| Demo Mode session replay | ≤ 2s to first interaction | ✅ |
| SerpApi credit usage per demo | 0 credits (Demo Mode) | ✅ |
| Memory usage (backend) | ≤ 512MB on Render free tier | ✅ |

---

## ✦ 11. Data Architecture

### Supabase Schema (`supabase/migrations/0001_compass_schema.sql`)

| Table | Purpose | Key Features |
|---|---|---|
| `documents` | Normalized SerpApi results | `embedding vector(768)` (HNSW), `fts tsvector` (GIN), RPC `hybrid_search` |
| `playbooks` | Playbook specs + embeddings | RPC `match_playbooks` for intent routing |
| `sessions` | User sessions with state | Persists across Render restarts (0002 migration) |
| `actions` | HITL state + receipts | Approval tracking with screenshots and downloads |
| `watches` | Price/rating/rank monitoring | Baseline, history, threshold alerts |
| `price_history` | Anomaly baselines | Median/MAD for robust z-score detection |

**Key RPCs**:
- `hybrid_search(query_text, query_embedding, match_count, filter_session, filter_category, rrf_k)` — Reciprocal Rank Fusion of cosine + FTS
- `match_playbooks(query_embedding, match_count)` — Intent routing via embedding similarity

**Security**: RLS enabled on every table. Backend uses service-role key over PostgREST (no DB driver needed).

---

## ✦ 12. API Reference

### Backend REST + SSE API

| Method & path | Purpose |
|---|---|
| `GET /api/health` | integrations, demo flag, cache stats (also warms Render) |
| `GET /api/playbooks` | Playbook library |
| `POST /api/sessions` `{prompt, lens, playbook_id?, priorities?, auto_confirm?}` | start async session → `{session_id, stream}` |
| `GET /api/sessions/{id}/stream` | **SSE** event stream (replays history; `?after=seq`) |
| `GET /api/sessions/{id}` · `/events` · `/trace` | summary · event history · Langfuse/local spans |
| `POST /api/sessions/run` | blocking run (CLI/tests) |
| `POST /api/sessions/{id}/confirm?choice=all\|essential` | budget-gate confirmation |
| `POST /api/sessions/{id}/disrupt?kind=price_spike\|unavailable&pct=45` | live edge-case injection |
| `POST /api/sessions/{id}/repoll` | fresh re-poll (manual cron tick) |
| `POST /api/actions/{id}/approve` · `/reject` · `/modify` `{payload, note}` | Human-in-the-Loop |
| `GET /api/actions/{id}/ics` | calendar file from a receipt |
| `GET/POST /api/watches` · `POST /api/watches/{id}/check` | watches |
| `POST /api/watch/tick` (header `x-cron-secret`) | scheduler target |

---

## ✦ 13. User Guide

### 🚀 Getting Started

1. **Open the Vercel link** — [`compass-rosy.vercel.app`](https://compass-rosy.vercel.app/) — no login needed, sample prompt chips are preloaded.
2. **Toggle lenses** — Switch between **Go · casual** and **Pro · enterprise**, or **Split-screen** to run both on one backend.
3. **Try a sample prompt** — Click a chip, e.g. *"Plan a 4-day Tokyo trip under $1,200, flights + hotel"*.
4. **Watch the pipeline** — See the thought-tree, SerpApi log, heatmap, and matrix update in real-time.
5. **Test disruption** — Click **Price spike +45%** to see anomaly detection and automatic re-planning.
6. **Approve actions** — Click **Approve** on booking cards to see Action Receipts with Playwright steps.
7. **Explore raw data** — Open **Raw calls** to see every engine response plus Langfuse spans.

### 🎯 Advanced Features

- **Voice input** — Click the mic button to speak your query (native browser speech recognition).
- **Full-screen decision graph** — Expand the thought tree for pan/zoom exploration of the decision process.
- **Retrieval heatmap** — See fresh vs cached cells, RRF hits, and index composition.
- **Watch monitoring** — Create price/rating/rank watches with "Check now" for real-time updates.
- **Playbook library** — Browse all 14 Playbooks with engines, dimensions, weights, and click-to-run examples.
- **Account meter** — Monitor real SerpApi plan credits and hourly throughput.

### 🖥️ Command Center Layout

| Section | Purpose |
|---|---|
| **Pipeline Stepper** | Real-time stage visualization with wall times and re-plan badges |
| **Intent Bars** | Playbook confidence scores with router stage and signals |
| **Routing Panel** | Intent → Playbook mapping with engine fan-out and FRESH flags |
| **Thought Tree** | Animated decision graph with inputs, agents, and dimensions |
| **SerpApi Log** | Color-coded live log with expandable raw JSON |
| **Retrieval Heatmap** | Hybrid search visualization with dense/keyword ranks |
| **Decision Matrix** | Multi-criteria analysis with confidence gauge and anomaly flags |
| **Insights Panels** | Venue consensus, SEO grid, trip extras, feed insights |
| **Watches** | Price/rating/rank monitoring with sparklines and alerts |
| **HITL Cards** | Approve/Modify/Reject with receipts and downloads |

---

## ✦ 14. Local Development (4 GB-friendly)

```bash
# 1. Clone the repository
git clone https://github.com/pmrinal2005/COMPASS.git
cd COMPASS

# 2. Backend setup
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt            # Playwright browsers NOT needed locally (falls back to dry-run)
cp .env.example .env                       # all keys optional → Demo Mode
uvicorn app.main:app --reload --port 8000

# 3. Run backend smoke test (0 credits)
PYTHONPATH=. python scripts/smoke_test.py

# 4. Frontend setup (new terminal)
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local   # omit for offline Demo Mode
npm run dev                                # http://localhost:3000

# 5. Run both services with PM2 (optional)
cd ..
pm2 start ecosystem.config.cjs
```

**Requirements**:
- Python 3.11+
- Node.js 18+
- 4 GB RAM minimum
- No Docker, no local compute, no API keys required for Demo Mode

---

## ✦ 15. Deployment

### 1. Supabase (Database)
1. Create a Supabase project
2. Run `supabase/migrations/0001_compass_schema.sql` **and** `0002_sessions_persistence.sql` in the SQL editor
3. Copy the project URL and service-role key

### 2. Render (Backend)
1. New → Blueprint → this repo (`render.yaml`)
2. Fill in the `sync:false` secrets (SerpApi, Groq, Gemini, Supabase, Upstash, Langfuse, Telegram, Resend)
3. Note the generated `CRON_SECRET`
4. Set `FRONTEND_ORIGINS` to your Vercel URL

### 3. Vercel (Frontend)
1. Import the repo → **Root Directory = `frontend`**
2. Set `NEXT_PUBLIC_API_URL=https://compass-api-w9dp.onrender.com`
3. **Redeploy** (NEXT_PUBLIC_* values are inlined at build time)
4. If unset, defaults to Render backend; set to `offline` to force recorded Demo Mode

### 4. Scheduler + Keep-warm
1. In GitHub repo → Settings → Secrets → Actions, add `COMPASS_API_URL` and `CRON_SECRET`
2. `.github/workflows/watch-cron.yml` ticks every 15 min (can be run manually with `force`)
3. `keep-warm.yml` pings `/api/health` every 10 min to keep Render's free instance awake

### 5. Demo Day
1. Open the site 1–2 min early
2. The health ping wakes Render's free instance
3. The badge shows "waking backend…" until ready

---

## ✦ 16. Testing & Verification

### Backend Tests (296 tests, 0 credits)

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q                         # 296 tests: playbook params vs SerpApi docs, every normalizer vs
                                            #   documented sample payload, async/Search-Archive/error-code transport,
                                            #   frontend contract, routing/freshness regressions

# End-to-end over HTTP API in Demo Mode (15 prompt routes, 4 disruptions, persistence)
PYTHONPATH=. python scripts/smoke_test.py

# Real SerpApi verification (keyless doc-example engines + error contract)
PYTHONPATH=. python scripts/live_check.py

# Full SerpApi sweep (requires SERPAPI_KEY, spends credits)
SERPAPI_KEY=… PYTHONPATH=. python scripts/live_check.py [--full]

# Re-snapshot documented parameters from serpapi.com
PYTHONPATH=. python scripts/docs_sync.py

# Regenerate frontend demo recordings after backend changes
PYTHONPATH=. python scripts/record_demo.py

# Playwright browser E2E of Command Center
python scripts/ui_check.py http://localhost:3000
```

### Frontend Verification

```bash
cd frontend
npx tsc --noEmit && npm run lint && npm run build   # all clean
```

### Live Verification Scripts

| Script | Purpose | Credits |
|---|---|---|
| `live_check.py` (keyless) | 39 checks: doc-example engines + error contract + async→archive polling | 0 |
| `live_check.py` (keyed) | + Account API and one live call per playbook engine | ~14 |
| `e2e_http.py` | 48 checks: every HTTP endpoint, SSE, HITL, watches, disruption, CORS | 0 |
| `ui_live_check.py` | Playwright: UI really talks to live backend (no offline replay) | 0 |

---

## ✦ 17. Status & Verification

<div align="center">

| Aspect | Status | Evidence |
|---|:-:|---|
| **Platform** | ✅ | Vercel (frontend) + Render (backend) + Supabase + Upstash + Langfuse Cloud. All free tiers; no Cloudflare/Hono. |
| **Backend smoke test** | ✅ | Passes for all 15 prompt routes (HITL, watch/cron auth, disruption → re-plan) |
| **Frontend build** | ✅ | `npm ci && npm run build` passes (type-check + lint) |
| **UI verification** | ✅ | Exercised in headless browser in both live-backend and offline modes with zero console errors |
| **Demo Mode** | ✅ | Works offline with pre-recorded real sessions including disruption testing |
| **Public repository** | ✅ | [`github.com/pmrinal2005/COMPASS`](https://github.com/pmrinal2005/COMPASS) |
| **Public deployment** | ✅ | [`compass-rosy.vercel.app`](https://compass-rosy.vercel.app/) — no authentication required |
| **Last updated** | ✅ | 2026-10-11 |

</div>

---

## ✦ 18. Roadmap & Future Work

COMPASS is feature-complete for the current brief, but the architecture leaves a clean runway for future enhancements:

- **Supabase Auth per user** — sessions are anonymous today; RLS policies for end users
- **More Playbooks** — wire to further documented engines (OpenTable, Google Scholar Author, Patents Details)
- **Playbook Exchange marketplace** — per-tenant enterprise Playbooks
- **Multi-user collaboration** — shared sessions with real-time cursor presence
- **Advanced anomaly detection** — time-series forecasting for price/rank predictions
- **Mobile app** — React Native companion for on-the-go decision monitoring
- **Enterprise SSO** — SAML/OIDC integration for corporate deployments
- **Custom Playbook builder** — visual editor for creating new decision workflows

---

## ✦ 19. License

Released under the **MIT License** — see [`LICENSE`](LICENSE) (or the `license` field in `package.json`).

---

<div align="center">

**COMPASS** · *One Decision Engine, Infinite Verticals*
Built with discipline, deployed on free tiers, designed to be tested with zero API credits.

*Multi-Agent Decision Engine · 2026*

</div>
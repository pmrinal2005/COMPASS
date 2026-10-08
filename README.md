# COMPASS — "One Decision Engine, Infinite Verticals"

A **SerpApi-native multi-agent operating system** for **Plan → Search → Compare → Act**.
Lean build: zero Docker, zero local compute, $0 stack, and it runs on a 4 GB RAM laptop. Your machine only runs VS Code, a Python venv and `npm run dev`. LLMs, embeddings, vector search, browser automation, tracing and scheduling all run on free cloud tiers.

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

## URLs
| | |
|---|---|
| Frontend (Vercel) | deploy `frontend/` (see below). With no backend it runs **offline Demo Mode** |
| Backend (Render) | `https://compass-api.onrender.com` (deploy via `render.yaml`) · docs at `/docs` |
| GitHub | https://github.com/pmrinal2005/COMPASS |

## Repository layout
```
backend/                 FastAPI + LangGraph (Render, native Python buildpack, no Dockerfile)
  app/main.py            REST + SSE API
  app/graph.py           LangGraph state machine: plan → budget_gate → research → verify → analyze → (replan↺ | act)
  app/agents/            orchestrator.py · researcher.py · analyst.py · actor.py
  app/playbooks/*.json   declarative Playbooks (engines, fallbacks, dimensions, actions)
  app/services/          serpapi (async + archive polling) · cache (Upstash) · store (Supabase pgvector) ·
                         llm (Groq → Gemini) · tracing (Langfuse) · notify · browser (Playwright) · documents · demo_data · geo
  app/watch.py           recurring watch polls (cron target)
  scripts/smoke_test.py  end-to-end test (Demo Mode, 0 credits)
  scripts/record_demo.py regenerates frontend/lib/demo/recordings.json
frontend/                Next.js 14 + React + Tailwind + framer-motion (Vercel Hobby)
  app/page.tsx           Agent Command Center (Go/Pro toggle + split-screen + Playbook library + account credits)
  components/            PipelineStepper · IntentBars · ThoughtTree · SerpLog · RetrievalHeatmap · DecisionMatrix ·
                         InsightsPanel (VenueConsensus · SeoGrid · trip stays/events) · WatchesPanel · PlaybookLibrary ·
                         AccountMeter · ActionCards (HITL) · RawCalls · AnimatedNumber
  lib/                   api · reducer (event → UI state) · pipeline (stepper derived from SSE) · useSession (SSE live / offline replay) ·
                         useWatches (live ticks / offline simulation) · demo recordings (7 scenarios) + bundled Playbook library
supabase/migrations/     0001_compass_schema.sql (tables, pgvector HNSW, FTS GIN, hybrid_search + match_playbooks RPCs)
render.yaml              Render Blueprint (web service, free)
.github/workflows/       watch-cron.yml (POST /api/watch/tick every 15 min) · keep-warm.yml (GET /api/health every 10 min)
ecosystem.config.cjs     PM2 config for running both services in a local sandbox
```

## Implemented features
- **Playbooks (5):** `lifeops_trip` (Flights ×2 for corroboration, Hotels, Maps, Finance FX), `lifeops_deals` (Shopping, Amazon, Walmart, eBay), `pro_supplier` (Google, Shopping, Amazon, eBay, News risk), `career_jobs` (Jobs, News, Trends), `research_ip` (Scholar, Patents, News). Each one also has targeted **fallback engines** for re-planning.
- **Orchestrator:** embedding + keyword intent classification against the Playbook library. Uses the Supabase `match_playbooks` pgvector RPC when configured, otherwise in-process cosine. Slot filling uses an LLM in JSON mode, with a regex fallback. Unknown cities resolve through SerpApi **`google_flights_autocomplete`** (`suggestions[].airports[].id`). The output is a typed Decision Graph (entities / dimensions / constraints / sources / actions).
- **Researcher:** follows the SerpApi documented contract: `GET /search.json?engine=…&async=true`, then polls the Search Archive `GET /searches/{id}.json` until `Success`/`Error`. Other details:
  - 429/5xx get exponential backoff; 4xx are not retried.
  - Fresh polls use `no_cache=true`.
  - A per-session semaphore bounds concurrency.
  - Calls are deduplicated by SHA-256 fingerprint through **Upstash Redis**, so repeat calls cost no credits.
- **Hybrid RAG:** results are embedded with the Gemini free-tier embedding API and stored in **Supabase pgvector**. Retrieval fuses cosine rank and Postgres full-text rank with Reciprocal Rank Fusion. An in-memory fallback uses the identical cosine + BM25 RRF algorithm.
- **Hallucination filter:** a fact is "verified" only when ≥2 independent sources agree:
  - flight itinerary seen in two independent result sets plus the price-insights band
  - hotel rating cross-checked against Google Maps
  - cross-engine price consensus
  - supplier MOQ plus marketplace price band
  - salary peer band and news signals
  - citation graph / patent publication record

  Single-source facts are flagged, never passed on silently.
- **Analyst:** min-max, direction-aware weighted matrix with user priority overrides. Reputation uses a Bayesian-smoothed rating. Anomaly detection uses robust z-scores (median/MAD) against both the stored price history baseline and the peer group. Anomalies and budget breaches are penalized. The confidence score combines verification ratio, margin, coverage and anomalies, and comes with an LLM or template rationale.
- **Bounded re-planning:** LangGraph conditional edge with a hard cap (`MAX_REPLANS=2`). Once the cap is hit it returns partial results with a confidence caveat.
- **Actor + HITL:**
  - Playwright booking/application flows run inside Render only. They capture a screenshot and stop at payment/submit.
  - Other actions: ICS calendar files, Markdown/HTML reports, RFQ email drafts, cover notes, Telegram + Resend notifications, and creating watches.
  - Financial, legal or irreversible actions need **Approve / Modify / Reject**.
- **Budget guard:** visible per-session credit meter. Fan-outs above `EXPENSIVE_FANOUT_THRESHOLD` pause for a one-click "fire all / essential only" confirmation.
- **Watches + scheduling:** `POST /api/watch/tick` (secret header) re-polls every due watch with `fresh=true`. It detects ≥ threshold % or |z| ≥ 3 moves, sends a Telegram alert and triggers a bounded auto re-plan on the owning session. The free scheduler is GitHub Actions; Render cron is optional.
- **Live edge-case injection:** `POST /api/sessions/{id}/disrupt?kind=price_spike|unavailable`. The top option spikes on the next fresh poll, the anomaly is detected, the engine re-plans (flexible dates and wider hotels), the old approvals are superseded and a new HITL card appears.
- **Observability:** Langfuse Cloud ingestion REST API (no SDK, no self-hosting). The trace is read back for the "Raw calls" tab, and local spans are the fallback.
- **Command Center UI:**
  - **pipeline stepper** Plan → Search → Verify → Compare → Act, derived purely from the SSE `stage` events: per-step wall time, spinning `re-plan n/2` badge, `×n` revisit badges, a "waiting for budget" state and a progress bar
  - **intent bars**: dense (cosine) ⊕ keyword score for every Playbook, winner highlighted
  - **venue consensus** (Maps ⊕ Yelp ⊕ Tripadvisor bars with a consensus marker, spread, rating-drop deltas), **SEO grid** (7 engines, position heat-map, ±rank movement, AI-Mode/AI-Overview citation chips with the answer text, competitor leaderboard) and **trip extras** (Airbnb stays + events)
  - **watches panel**: price / rating / rank watches with baseline → now, animated sparkline, "Check now" (`POST /api/watches/{id}/check`, a real fresh SerpApi poll) and threshold alerts. With no backend it runs a clearly-labelled deterministic *simulation*
  - **Playbook library** (`GET /api/playbooks`, bundled copy offline): engines, re-plan fallback engines, decision dimensions + weights, action types, click-to-run examples
  - **account meter**: real SerpApi plan credits and hourly throughput through the free Account API (`GET /api/account`; never exposes the key / e-mail)
  - the disruption button adapts to the Playbook: *Price spike +45%* · *Rating drop −45%* · *Rank drop −8*
  - every animation honours the OS `prefers-reduced-motion` setting
  - animated thought-tree / Decision Graph
  - live colour-coded SerpApi log with expandable raw JSON
  - retrieval heat-map (fresh vs cached cells, RRF hits with dense/keyword ranks)
  - animated decision matrix with confidence gauge, rank-movement arrows and anomaly flags
  - HITL cards with receipts (screenshot, steps, .ics / .md download, RFQ drafts, delivery status)
  - raw-calls trace viewer
  - Go/Pro toggle and **split-screen** (both lenses on one backend)
- **Demo Mode everywhere:** with no `SERPAPI_KEY` the backend serves deterministic, shape-faithful SerpApi payloads (0 credits). With no `NEXT_PUBLIC_API_URL`, or if the backend is unreachable or cold-starting, the frontend **replays pre-recorded real sessions**, including the disruption, so a Vercel link always works.

## API (backend)
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

## Data architecture (Supabase, `supabase/migrations/0001_compass_schema.sql`)
- `documents`: normalized SerpApi results, `embedding vector(768)` (HNSW), generated `fts tsvector` (GIN). RPC `hybrid_search(query_text, query_embedding, match_count, filter_session, filter_category, rrf_k)`.
- `playbooks`: spec + embedding. RPC `match_playbooks(query_embedding, match_count)`.
- `sessions`, `actions` (HITL state + receipts), `watches` (params, baseline, history), `price_history` (anomaly baselines).
- RLS is enabled on every table. The backend uses the service-role key over PostgREST, so no DB driver is needed.

## Local development (4 GB-friendly)
```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # Playwright browsers NOT needed locally (falls back to dry-run)
cp .env.example .env                       # all keys optional → Demo Mode
uvicorn app.main:app --reload --port 8000
PYTHONPATH=. python scripts/smoke_test.py  # end-to-end check, 0 credits

# frontend
cd frontend && npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local   # omit for offline Demo Mode
npm run dev                                # http://localhost:3000
```

## Deployment
1. **Supabase:** create a project, then run `supabase/migrations/0001_compass_schema.sql` **and** `0002_sessions_persistence.sql` in the SQL editor (0002 lets sessions survive a Render restart). Copy the project URL and the service-role key.
2. **Render (backend):** New → Blueprint → this repo (`render.yaml`). Fill in the `sync:false` secrets (SerpApi, Groq, Gemini, Supabase, Upstash, Langfuse, Telegram, Resend). Note the generated `CRON_SECRET`. Set `FRONTEND_ORIGINS` to your Vercel URL.
3. **Vercel (frontend):** Import the repo → **Root Directory = `frontend`** (Next.js is auto-detected, and `frontend/vercel.json` pins `npm ci` / `npm run build`). Set the environment variable `NEXT_PUBLIC_API_URL=https://compass-api.onrender.com`, or leave it empty for offline Demo Mode. Deploy.
4. **Scheduler + keep-warm:** in GitHub repo → Settings → Secrets → Actions, add `COMPASS_API_URL` and `CRON_SECRET`. `.github/workflows/watch-cron.yml` then ticks every 15 min (and can be run manually, optionally with `force`), and `keep-warm.yml` pings `/api/health` every 10 min so Render's free instance stays awake.
5. **Demo day:** open the site 1–2 min early. The health ping wakes Render's free instance; the badge shows "waking backend…" until it's ready.

## How judges test it
1. Open the Vercel link. No login is needed, and sample prompt chips are preloaded.
2. Toggle **Go · casual / Pro · enterprise**, or **Split-screen** to run both lenses on one backend.
3. Click a chip, e.g. *"Plan a 4-day Tokyo trip under $1,200, flights + hotel"*, and watch the thought-tree, SerpApi log, heat-map and matrix.
4. Click **Price spike +45%**. The anomaly is flagged, a re-plan follows ("Re-plan 1/2"), the ranking changes, and old approvals are superseded.
5. Click **Approve** on the booking card to see the Action Receipt (Playwright steps / confirmation id).
6. Open **Raw calls** to see every engine response plus Langfuse spans (and the "Open in Langfuse" link when configured).

## Testing & verification
```bash
cd backend && pip install -r requirements-dev.txt
python -m pytest -q                         # 110 tests, 0 credits: playbook params vs the SerpApi docs, every normalizer vs the
                                            #   documented sample payload, async/Search-Archive/error-code transport, frontend contract
PYTHONPATH=. python scripts/smoke_test.py   # end-to-end over the HTTP API in Demo Mode (7 playbooks, 4 disruptions, persistence)
PYTHONPATH=. python scripts/live_check.py   # REAL serpapi.com: keyless doc-example engines + error contract + async→archive polling
SERPAPI_KEY=… PYTHONPATH=. python scripts/live_check.py [--full]   # + Account API and one live call per playbook engine
PYTHONPATH=. python scripts/docs_sync.py    # re-snapshot the documented parameters from serpapi.com (diff = docs drift)
PYTHONPATH=. python scripts/record_demo.py  # regenerate frontend/lib/demo/{recordings,playbooks}.json after backend changes
python scripts/ui_check.py http://localhost:3000   # Playwright browser E2E of the Command Center (live or offline)
```
`live_check.py` needs no key for its 28 checks (it uses the keyless doc-example queries serpapi.com answers itself). The keyed sweep is the only
part that spends credits and needs your `SERPAPI_KEY`; **it has not been run against your account in this repo's CI**, so run it once before demo day.

## Not yet implemented / next steps
- Supabase Auth per user (sessions are anonymous today; RLS policies for end users)
- More Playbooks wired to further documented engines (OpenTable, Google Scholar Author, Patents Details)
- Playbook Exchange marketplace and per-tenant enterprise Playbooks

## Status
- **Platform:** Vercel (frontend) + Render (backend) + Supabase + Upstash + Langfuse Cloud. All free tiers; **no Cloudflare/Hono**.
- **Verified:** backend smoke test passes for all 5 playbooks (HITL, watch/cron auth, disruption → re-plan). `npm ci && npm run build` passes (type-check + lint). The UI was exercised in a headless browser in both live-backend and offline modes with zero console errors.
- **Last updated:** 2026-10-06

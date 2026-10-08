"""COMPASS FastAPI service (Render free tier, native Python buildpack)."""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from . import graph as G
from .agents import actor
from .config import get_settings
from .models import ModifyRequest, SessionRequest, WatchRequest, new_id
from .playbooks import PLAYBOOKS
from .services.cache import cache
from .services.events import bus
from .services.llm import embedder, llm
from .services.serpapi import SerpApiError, serp
from .services.store import store
from .services.tracing import tracer
from .watch import check_watch, create_watch, tick

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    flusher = asyncio.create_task(tracer.run_flusher())
    yield
    flusher.cancel()
    await tracer.flush()
    await serp.aclose()


app = FastAPI(title="COMPASS Decision Engine", version="1.0.0", lifespan=lifespan)
origins = [o.strip() for o in settings.frontend_origins.split(",")] if settings.frontend_origins else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ meta
@app.get("/")
async def root():
    return {"name": "COMPASS", "tagline": "One Decision Engine, Infinite Verticals", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
async def health():
    return {"ok": True, "ts": time.time(), "demo_mode": settings.is_demo, "integrations": settings.integrations(),
            "llm": llm.provider, "embedder": embedder.provider, "store": store.backend, "cache": cache.stats(),
            "live_serpapi_calls": serp.total_live_calls, "sessions": len(G.RUNTIME)}


@app.get("/api/playbooks")
async def playbooks():
    """Playbook library (declarative specs) + a flat engine summary for the UI's library panel."""
    out = []
    for pb in PLAYBOOKS.values():
        item = {k: v for k, v in pb.items() if k not in ("fallback_engines",)}
        item["engine_list"] = sorted({e["engine"] for e in pb["engines"]})
        item["fallback_engine_list"] = sorted({e["engine"] for e in pb.get("fallback_engines", [])})
        out.append(item)
    return out


@app.get("/api/account")
async def account(force: bool = False):
    """SerpApi Account API (https://serpapi.com/account-api) - free, not counted toward the quota.
    api_key / e-mail / account id are stripped; in Demo Mode a placeholder is returned."""
    try:
        return await serp.account(force=force)
    except SerpApiError as e:
        raise HTTPException(e.status if e.status and 400 <= e.status < 600 else 502, str(e))


@app.get("/api/locations")
async def locations(q: str, limit: int = 5):
    """SerpApi Locations API proxy (free): canonical location names for the `location` search parameter."""
    try:
        return await serp.locations(q, limit)
    except SerpApiError as e:
        raise HTTPException(e.status if e.status and 400 <= e.status < 600 else 502, str(e))


# --------------------------------------------------------------- sessions
@app.post("/api/sessions")
async def create_session(req: SessionRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt required")
    sid = new_id("s_")
    r = G.rt(sid)

    async def runner():
        try:
            await G.run_session(sid, req.prompt.strip(), req.lens, req.playbook_id, req.priorities, req.auto_confirm)
        except Exception:
            pass

    r.task = asyncio.create_task(runner())
    return {"session_id": sid, "stream": f"/api/sessions/{sid}/stream", "credits": r.meter.as_dict()}


@app.post("/api/sessions/run")
async def run_sync(req: SessionRequest):
    """Blocking variant (CLI / tests): runs the full graph and returns the result."""
    sid = new_id("s_")
    final = await G.run_session(sid, req.prompt.strip(), req.lens, req.playbook_id, req.priorities, True)
    return _summary(sid, final)


def _summary(sid: str, st: dict) -> dict:
    r = G.rt(sid)
    return {"session_id": sid, "status": st.get("status"), "playbook_id": (st.get("graph") or {}).get("playbook_id"),
            "slots": (st.get("graph") or {}).get("slots"), "confidence": st.get("confidence"), "replans": st.get("replans", 0),
            "replan_history": st.get("replan_history", []), "verification": st.get("verification"),
            "analysis": st.get("analysis"), "actions": [a.model_dump() for a in r.actions.values()],
            "credits": r.meter.as_dict(), "call_log": st.get("call_log", []), "trace_url": tracer.trace_url(sid)}


@app.get("/api/sessions")
async def list_sessions():
    return await store.list("sessions", limit=30)


@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    if sid not in G.RUNTIME:
        if await G.ensure(sid) is None:                      # process restarted -> resume from the Supabase snapshot
            row = await store.get("sessions", sid)
            if not row:
                raise HTTPException(404, "session not found")
            return row
    return _summary(sid, G.RUNTIME[sid].state)


@app.get("/api/sessions/{sid}/events")
async def session_events(sid: str, after: int = 0):
    await G.ensure(sid)
    return bus.history(sid, after)


@app.get("/api/sessions/{sid}/stream")
async def stream(sid: str, request: Request, after: int = 0):
    await G.ensure(sid)

    async def gen():
        q = bus.subscribe(sid)
        try:
            last = after
            for e in bus.history(sid, after):
                last = e["seq"]
                yield {"event": "message", "id": str(e["seq"]), "data": json.dumps(e, default=str)}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    e = await asyncio.wait_for(q.get(), timeout=15)
                    if e["seq"] <= last:
                        continue
                    last = e["seq"]
                    yield {"event": "message", "id": str(e["seq"]), "data": json.dumps(e, default=str)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(sid, q)

    return EventSourceResponse(gen())


@app.post("/api/sessions/{sid}/confirm")
async def confirm(sid: str, choice: str = "all"):
    await G.ensure(sid)
    r = G.rt(sid)
    r.confirm_choice = choice if choice in ("all", "essential") else "all"
    r.confirm.set()
    return {"ok": True, "choice": r.confirm_choice}


@app.post("/api/sessions/{sid}/disrupt")
async def disrupt(sid: str, kind: str = "price_spike", pct: float = 45.0, slip: int = 8):
    """Live edge-case injection - the top-ranked option moves on the next fresh poll:
       price_spike / unavailable   -> flights, hotels, products, suppliers (venues: 'fully booked', domains: 'de-indexed')
       rating_drop                 -> a venue's rating falls on every platform
       rank_drop                   -> the tracked domain slips `slip` positions in every search engine"""
    if kind not in G.DISRUPTIONS:
        raise HTTPException(400, f"kind must be one of {G.DISRUPTIONS}")
    await G.ensure(sid)
    if sid not in G.RUNTIME or not G.RUNTIME[sid].state.get("analysis"):
        raise HTTPException(409, "session not ready")
    try:
        disruption = G.make_disruption(sid, kind, pct, slip)
    except ValueError:
        raise HTTPException(409, "nothing to disrupt")
    asyncio.create_task(G.repoll(sid, disruption))
    return {"ok": True, "disruption": {k: v for k, v in disruption.items() if not k.startswith("_")}}


@app.post("/api/sessions/{sid}/repoll")
async def manual_repoll(sid: str):
    if sid not in G.RUNTIME and await G.ensure(sid) is None:
        raise HTTPException(404, "session not found")
    asyncio.create_task(G.repoll(sid))
    return {"ok": True}


@app.get("/api/sessions/{sid}/trace")
async def trace(sid: str):
    remote = await tracer.fetch_remote(sid)
    return {"source": "langfuse-cloud" if remote else "local", "trace_url": tracer.trace_url(sid),
            "remote": remote, "spans": tracer.local.get(sid, [])[-300:]}


# ------------------------------------------------------------ HITL actions
async def _find_action(aid: str):
    for r in G.RUNTIME.values():
        if aid in r.actions:
            return r.actions[aid]
    row = await store.get("actions", aid)                    # after a restart: rehydrate the owning session first
    if row and await G.ensure(row.get("session_id", "")) is not None:
        for r in G.RUNTIME.values():
            if aid in r.actions:
                return r.actions[aid]
    raise HTTPException(404, "action not found")


@app.post("/api/actions/{aid}/approve")
async def approve(aid: str):
    a = await _find_action(aid)
    if a.status not in ("pending", "modified"):
        raise HTTPException(409, f"action is {a.status}")
    a.status = "approved"
    bus.publish(a.session_id, "actor.approved", {"action_id": aid}, agent="human")
    receipt = await actor.execute(a)
    await G.snapshot(a.session_id)
    return {"ok": True, "action": a.model_dump(), "receipt": receipt}


@app.post("/api/actions/{aid}/reject")
async def reject(aid: str):
    a = await _find_action(aid)
    a.status = "rejected"
    await store.put("actions", {**a.model_dump(), "created_at": a.created_at})
    await G.snapshot(a.session_id)
    bus.publish(a.session_id, "actor.rejected", {"action_id": aid}, agent="human")
    return {"ok": True, "action": a.model_dump()}


@app.post("/api/actions/{aid}/modify")
async def modify(aid: str, req: ModifyRequest):
    a = await _find_action(aid)
    if a.status not in ("pending", "modified"):
        raise HTTPException(409, f"action is {a.status}")
    a.payload = {**a.payload, **req.payload}
    a.status = "modified"
    if req.note:
        a.description = f"{a.description}  ✎ {req.note}"
    bus.publish(a.session_id, "actor.modified", {"action": a.model_dump()}, agent="human")
    return {"ok": True, "action": a.model_dump()}


@app.get("/api/actions/{aid}/ics", response_class=PlainTextResponse)
async def action_ics(aid: str):
    a = await _find_action(aid)
    if not a.receipt or "ics" not in a.receipt:
        raise HTTPException(404, "no calendar file")
    return PlainTextResponse(a.receipt["ics"], media_type="text/calendar",
                             headers={"Content-Disposition": "attachment; filename=compass.ics"})


# ----------------------------------------------------------------- watches
@app.get("/api/watches")
async def watches():
    return await store.list("watches", limit=100)


@app.post("/api/watches")
async def add_watch(req: WatchRequest):
    return await create_watch(session_id=req.session_id, label=req.label, engine=req.engine, params=req.params,
                              target_title=req.target_title, baseline_price=req.baseline_price,
                              threshold_pct=req.threshold_pct, cadence_minutes=req.cadence_minutes)


@app.post("/api/watches/{wid}/check")
async def check_one(wid: str):
    w = await store.get("watches", wid)
    if not w:
        raise HTTPException(404, "watch not found")
    return await check_watch(w, force=True)


@app.post("/api/watch/tick")
async def watch_tick(x_cron_secret: str | None = Header(default=None), force: bool = False):
    """Called by Render Cron / GitHub Actions on a schedule."""
    if settings.cron_secret and x_cron_secret != settings.cron_secret:
        raise HTTPException(401, "bad cron secret")
    return await tick(force=force)

"""LangGraph state machine — the single agent framework.

    START ─┬─(new)────► plan ─► budget_gate ─► research ─► verify ─► analyze ─┬─► act ─► END
           └─(repoll)─────────────────────────► research                      │
                                     ▲                                         │ low confidence
                                     └──────────── replan ◄────────────────────┘ (≤ max_replans)

Shared state is a TypedDict; every loop increments `replans`, and the
conditional edge refuses a further pass once the cap is hit — partial
results are surfaced with a confidence caveat instead."""
from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import actor, analyst, orchestrator, researcher
from .config import get_settings
from .models import ActionProposal, Candidate, DecisionGraph, EngineCall
from .playbooks import PLAYBOOKS
from .services.events import bus
from .services.serpapi import CreditMeter
from .services.store import store
from .services.tracing import tracer


class State(TypedDict, total=False):
    session_id: str
    prompt: str
    lens: str
    mode: str                     # new | repoll
    forced_playbook: str | None
    priorities: dict | None
    auto_confirm: bool
    graph: dict                   # DecisionGraph
    pending_calls: list[dict]
    candidates: list[dict]
    context: dict
    call_log: list[dict]
    verification: dict
    coverage: float
    analysis: dict
    confidence: float
    replans: int
    replan_history: list[dict]
    actions: list[dict]
    status: str
    fresh: bool
    disrupted: bool


class SessionRuntime:
    """Live per-session objects that should not be serialized in state."""

    def __init__(self, budget: int) -> None:
        self.meter = CreditMeter(budget)
        self.confirm = asyncio.Event()
        self.confirm_choice: str = "all"
        self.actions: dict[str, ActionProposal] = {}
        self.disruption: dict | None = None
        self.state: State = {}
        self.task: asyncio.Task | None = None


RUNTIME: dict[str, SessionRuntime] = {}


def rt(session_id: str) -> SessionRuntime:
    if session_id not in RUNTIME:
        RUNTIME[session_id] = SessionRuntime(get_settings().session_credit_budget)
    return RUNTIME[session_id]


def _stage(sid: str, stage: str, extra: dict | None = None) -> None:
    bus.publish(sid, "stage", {"stage": stage, **(extra or {})})


# ----------------------------------------------------------------- nodes
async def node_plan(state: State) -> State:
    sid = state["session_id"]
    _stage(sid, "plan")
    g = await orchestrator.plan(state["prompt"], state.get("lens", "go"), sid, state.get("forced_playbook"), state.get("priorities"))
    return {"graph": g.model_dump(), "pending_calls": [c.model_dump() for c in g.calls], "replans": 0, "replan_history": [],
            "candidates": [], "context": {}, "call_log": []}


async def node_budget_gate(state: State) -> State:
    """Expensive fan-outs prompt a one-click confirmation before firing."""
    s = get_settings()
    sid = state["session_id"]
    r = rt(sid)
    calls = state["pending_calls"]
    if len(calls) <= s.expensive_fanout_threshold and len(calls) <= r.meter.remaining or state.get("auto_confirm"):
        return {}
    _stage(sid, "awaiting_budget")
    bus.publish(sid, "budget.confirm", {"calls": len(calls), "essential": sum(1 for c in calls if c.get("essential", True)),
                                        "credits": r.meter.as_dict()}, agent="orchestrator")
    try:
        await asyncio.wait_for(r.confirm.wait(), timeout=180)
    except asyncio.TimeoutError:
        r.confirm_choice = "essential"
    if r.confirm_choice == "essential":
        calls = [c for c in calls if c.get("essential", True)]
    bus.publish(sid, "budget.confirmed", {"choice": r.confirm_choice, "calls": len(calls)}, agent="orchestrator")
    return {"pending_calls": calls}


async def node_research(state: State) -> State:
    sid = state["session_id"]
    _stage(sid, "research", {"round": state.get("replans", 0)})
    calls = [EngineCall(**c) for c in state["pending_calls"]]
    cands, ctx, log = await researcher.fan_out(sid, calls, rt(sid).meter, fresh=bool(state.get("fresh")),
                                               round_=state.get("replans", 0), disruption=rt(sid).disruption)
    ess = [l for l, c in zip(log, calls) if c.essential]
    coverage = (sum(1 for l in ess if l["ok"]) / len(ess)) if ess else 1.0
    # merge with candidates from earlier rounds (re-plan adds, never discards evidence)
    prior = [Candidate(**c) for c in state.get("candidates", [])] if state.get("replans", 0) > 0 else []
    merged = prior + cands
    ctx = {**state.get("context", {}), **ctx}
    await researcher.index_and_retrieve(sid, state["prompt"], merged)
    slim_log = [{k: v for k, v in l.items() if k != "raw"} for l in log]
    disrupted = any(c.attributes.get("disrupted") for c in cands) or bool(state.get("disrupted"))
    return {"disrupted": disrupted,"candidates": [c.model_dump() for c in merged], "context": ctx,
            "call_log": state.get("call_log", []) + slim_log,
            "coverage": max(coverage, state.get("coverage", 0) if state.get("replans", 0) > 0 else coverage), "fresh": False}


async def node_verify(state: State) -> State:
    sid = state["session_id"]
    _stage(sid, "verify")
    cands = [Candidate(**c) for c in state["candidates"]]
    summary = researcher.corroborate(cands, state.get("context", {}), get_settings().corroboration_min_sources)
    bus.publish(sid, "rag.verification", summary, agent="researcher")
    return {"candidates": [c.model_dump() for c in cands], "verification": summary}


async def node_analyze(state: State) -> State:
    sid = state["session_id"]
    _stage(sid, "analyze")
    g = DecisionGraph(**state["graph"])
    cands = [Candidate(**c) for c in state["candidates"]]
    res = await analyst.analyze(sid, g.playbook_id, cands, g.slots, g.weights, state["verification"],
                                state.get("coverage", 1.0), state.get("context", {}))
    ranked = res.pop("ranked")
    rt(sid).state["_ranked"] = ranked  # keep live objects for the actor
    return {"analysis": {k: v for k, v in res.items()}, "confidence": res["confidence"]}


def route_after_analyze(state: State) -> str:
    s = get_settings()
    pb_has_fallback = bool(PLAYBOOKS[state["graph"]["playbook_id"]].get("fallback_engines"))
    if state.get("disrupted") and state.get("replans", 0) == 0 and pb_has_fallback:
        return "replan"  # previously recommended option moved -> targeted re-plan (bounded)
    if state.get("confidence", 0) >= s.confidence_threshold:
        return "act"
    if state.get("replans", 0) >= s.max_replans:
        return "act"  # cap reached -> surface partial results with caveat
    pb = PLAYBOOKS[state["graph"]["playbook_id"]]
    if not pb.get("fallback_engines"):
        return "act"
    return "replan"


async def node_replan(state: State) -> State:
    sid = state["session_id"]
    n = state.get("replans", 0) + 1
    g = DecisionGraph(**state["graph"])
    calls = orchestrator.build_calls(g.playbook_id, g.slots, fallback_round=n)
    reasons = list(state.get("analysis", {}).get("low_confidence_reasons", []))
    if state.get("disrupted") and n == 1:
        reasons.insert(0, "previously recommended option changed on fresh poll (anomaly)")
    entry = {"iteration": n, "confidence": state.get("confidence"), "reasons": reasons,
             "new_calls": [{"engine": c.engine, "purpose": c.purpose} for c in calls], "ts": time.time()}
    _stage(sid, "replan", {"iteration": n})
    bus.publish(sid, "orchestrator.replan", {**entry, "max": get_settings().max_replans, "calls": [c.model_dump() for c in calls]},
                agent="orchestrator")
    tracer.span(sid, "orchestrator:replan", {"reasons": reasons}, {"iteration": n})
    return {"replans": n, "pending_calls": [c.model_dump() for c in calls], "replan_history": state.get("replan_history", []) + [entry]}


async def node_act(state: State) -> State:
    sid = state["session_id"]
    _stage(sid, "act")
    r = rt(sid)
    g = DecisionGraph(**state["graph"])
    an = state["analysis"]
    ranked = r.state.get("_ranked", [])
    bus.publish(sid, "agent.start", {"agent": "actor", "label": "Drafting executable plan"}, agent="actor")
    # supersede previous pending approvals when re-planning after a disruption
    for a in r.actions.values():
        if a.status == "pending":
            a.status = "rejected"
            a.receipt = {"superseded": True, "reason": "re-planned after new evidence"}
            bus.publish(sid, "actor.superseded", {"action_id": a.id}, agent="actor")
    caveat = None
    if state.get("confidence", 0) < get_settings().confidence_threshold:
        caveat = f"Partial result: confidence {state.get('confidence', 0):.0%} after {state.get('replans', 0)} re-plan(s) (cap reached)."
    proposals = actor.propose(sid, g.playbook_id, ranked, g.slots, state["prompt"], an["rationale"], an["confidence"],
                              an["matrix"]["rows"])
    for p in proposals:
        r.actions[p.id] = p
        await store.put("actions", {**p.model_dump(), "created_at": p.created_at})
        bus.publish(sid, "actor.proposal", {"action": p.model_dump()}, agent="actor")
    # low-risk, no-approval actions run immediately
    for p in proposals:
        if not p.requires_approval:
            await actor.execute(p)
    done = {"status": "awaiting_approval" if any(p.requires_approval for p in proposals) else "complete",
            "actions": [p.model_dump() for p in proposals]}
    _stage(sid, "done", {"caveat": caveat, "confidence": state.get("confidence")})
    bus.publish(sid, "session.complete", {"confidence": state.get("confidence"), "caveat": caveat,
                                          "replans": state.get("replans", 0), "credits": r.meter.as_dict(),
                                          "top": an["matrix"]["rows"][0] if an["matrix"]["rows"] else None}, agent="orchestrator")
    return done


def route_start(state: State) -> str:
    return "research" if state.get("mode") == "repoll" else "plan"


def build_graph():
    g = StateGraph(State)
    g.add_node("plan", node_plan)
    g.add_node("budget_gate", node_budget_gate)
    g.add_node("research", node_research)
    g.add_node("verify", node_verify)
    g.add_node("analyze", node_analyze)
    g.add_node("replan", node_replan)
    g.add_node("act", node_act)
    g.add_conditional_edges(START, route_start, {"plan": "plan", "research": "research"})
    g.add_edge("plan", "budget_gate")
    g.add_edge("budget_gate", "research")
    g.add_edge("research", "verify")
    g.add_edge("verify", "analyze")
    g.add_conditional_edges("analyze", route_after_analyze, {"act": "act", "replan": "replan"})
    g.add_edge("replan", "research")
    g.add_edge("act", END)
    return g.compile()


COMPILED = build_graph()


async def run_session(session_id: str, prompt: str, lens: str, forced: str | None, priorities: dict | None, auto_confirm: bool) -> State:
    r = rt(session_id)
    tracer.trace(session_id, "compass.session", {"prompt": prompt, "lens": lens})
    await store.put("sessions", {"id": session_id, "prompt": prompt, "lens": lens, "status": "running", "created_at": time.time()})
    bus.publish(session_id, "session.start", {"prompt": prompt, "lens": lens, "credits": r.meter.as_dict()})
    try:
        final = await COMPILED.ainvoke({"session_id": session_id, "prompt": prompt, "lens": lens, "mode": "new",
                                        "forced_playbook": forced, "priorities": priorities, "auto_confirm": auto_confirm},
                                       {"recursion_limit": 40})
        r.state.update(final)
        await store.put("sessions", {"id": session_id, "prompt": prompt, "lens": lens, "status": final.get("status", "complete"),
                                     "playbook_id": final["graph"]["playbook_id"], "confidence": final.get("confidence"),
                                     "replans": final.get("replans", 0), "created_at": time.time(),
                                     "summary": {"top": (final["analysis"]["matrix"]["rows"] or [None])[0],
                                                 "credits": r.meter.as_dict()}})
        return final
    except Exception as e:
        bus.publish(session_id, "session.error", {"error": repr(e)[:300]})
        raise


async def repoll(session_id: str, disruption: dict | None = None) -> State:
    """Edge-case path: fresh re-poll of the session's sources (as a cron
    watch tick would do), optionally with an injected disruption."""
    r = rt(session_id)
    st = r.state
    if not st.get("graph"):
        raise ValueError("session has no completed plan")
    r.disruption = disruption
    _stage(session_id, "repoll", {"disruption": disruption})
    bus.publish(session_id, "watch.repoll", {"disruption": disruption, "reason": "scheduled poll" if not disruption else "injected disruption"},
                agent="researcher")
    g = DecisionGraph(**st["graph"])
    calls = [c for c in g.calls]
    init: State = {**{k: v for k, v in st.items() if not k.startswith("_")}, "mode": "repoll", "fresh": True, "replans": 0,
                   "pending_calls": [c.model_dump() for c in calls], "candidates": [], "replan_history": st.get("replan_history", []),
                   "disrupted": False}
    final = await COMPILED.ainvoke(init, {"recursion_limit": 40})
    r.state.update(final)
    r.disruption = None
    return final

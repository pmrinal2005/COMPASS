"""ORCHESTRATOR / PLANNER
 1. embeds the prompt and matches it against the Playbook library
    (cosine similarity + keyword prior, LLM tie-break when available)
 2. fills playbook slots (LLM JSON extraction -> regex heuristics fallback)
 3. emits a typed Decision Graph: entities, comparison dimensions,
    constraints, required data sources (SerpApi calls), candidate actions
 4. on re-plan, adds the playbook's targeted fallback engines (bounded)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from ..models import DecisionGraph, DecisionNode, EngineCall
from ..playbooks import PLAYBOOKS, playbook_text
from ..services.events import bus
from ..services.geo import lookup
from ..services.llm import embedder, llm

_PB_VECS: dict[str, list[float]] = {}


async def _pb_vectors() -> dict[str, list[float]]:
    if not _PB_VECS:
        ids = list(PLAYBOOKS)
        vecs = await embedder.embed([playbook_text(PLAYBOOKS[i]) for i in ids])
        _PB_VECS.update(dict(zip(ids, vecs)))
    return _PB_VECS


async def classify(prompt: str, lens: str, forced: str | None = None) -> tuple[str, list[dict]]:
    if forced and forced in PLAYBOOKS:
        return forced, [{"id": forced, "score": 1.0, "name": PLAYBOOKS[forced]["name"]}]
    qv = (await embedder.embed([prompt], task="RETRIEVAL_QUERY"))[0]
    vecs = await _pb_vectors()
    pl = prompt.lower()
    words = set(re.findall(r"[a-z0-9]+", pl))
    scores = []
    for pid, pb in PLAYBOOKS.items():
        cos = sum(a * b for a, b in zip(qv, vecs[pid]))
        kw = sum(1 for k in pb["keywords"] if (k in words if " " not in k else k in pl))
        lens_bias = 0.08 if pb["lens"] == lens else 0.0
        scores.append({"id": pid, "name": pb["name"], "score": round(cos * 0.5 + min(kw, 5) * 0.16 + lens_bias, 4),
                       "cosine": round(cos, 4), "keyword_hits": kw})
    scores.sort(key=lambda x: -x["score"])
    return scores[0]["id"], scores


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "a week": 7, "weekend": 3}


def _heuristic_slots(pid: str, prompt: str) -> dict[str, Any]:
    p = prompt.strip()
    pl = p.lower()
    slots: dict[str, Any] = {}
    money = re.search(r"(?:under|below|max|budget|<|less than|up to)?\s*\$\s?([\d,]+(?:\.\d+)?)\s*(k)?", pl)
    if money:
        v = float(money.group(1).replace(",", ""))
        slots["budget"] = v * 1000 if money.group(2) else v
    if pid == "lifeops_trip":
        d = re.search(r"(\d+)[\s-]*(?:day|night)", pl)
        if d:
            slots["days"] = int(d.group(1))
        else:
            for w, n in _NUM_WORDS.items():
                if re.search(rf"\b{w}[\s-]*(?:day|night)", pl) or (w == "weekend" and "weekend" in pl) or (w == "a week" and "a week" in pl):
                    slots["days"] = n
                    break
        frm = re.search(r"\bfrom\s+([a-z][a-z .]+?)(?:\s+(?:to|under|for|in|on|with|,)|$)", pl)
        to = re.search(r"\b(?:to|in|visit|trip to)\s+([a-z][a-z .]+?)(?:\s+(?:from|under|for|on|with|trip|,)|[,.]|$)", pl)
        dest_hint = re.search(r"(?:\d+[\s-]*day\s+)([a-z][a-z ]+?)\s+trip", pl)
        if frm:
            slots["origin"] = frm.group(1).strip().title()
        if dest_hint:
            slots["destination"] = dest_hint.group(1).strip().title()
        elif to:
            slots["destination"] = to.group(1).strip().title()
        a = re.search(r"(\d+)\s*(?:adults|people|travel+ers|persons)", pl)
        if a:
            slots["adults"] = int(a.group(1))
    elif pid in ("lifeops_deals", "pro_supplier"):
        cleaned = re.sub(r"(?i)\b(find|get|the|me|best|deal|deals|on|for|cheapest|source|sourcing|reliable|suppliers?|vendors?|"
                         r"compare|price|prices|moq|reviews?|bulk|wholesale|with|good|under|a|an|of|and|\d+|\$[\d,.]+k?)\b", " ", p)
        cleaned = re.sub(r"[/,]+", " ", cleaned)
        prod = " ".join(cleaned.split()).strip(" .")
        if prod:
            slots["product"] = prod
        c = re.search(r"\b(\d+|three|two|five|four)\s+(?:reliable\s+)?(?:suppliers|vendors)", pl)
        if c:
            slots["count"] = int(c.group(1)) if c.group(1).isdigit() else _NUM_WORDS.get(c.group(1), 3)
        q = re.search(r"([\d,]+)\s*(?:units|pcs|pieces)", pl)
        if q:
            slots["quantity"] = int(q.group(1).replace(",", ""))
    elif pid == "career_jobs":
        loc = re.search(r"\b(?:in|near|at)\s+([A-Za-z][A-Za-z ,]+)$", p)
        role = re.sub(r"(?i)\b(jobs?|openings?|positions?|roles?|find|me|hiring|for)\b", " ", p)
        if loc:
            slots["location"] = loc.group(1).strip()
            role = role.replace(loc.group(0), " ")
        role = " ".join(role.split()).strip(" .")
        if role:
            slots["role"] = role
    elif pid == "research_ip":
        topic = re.sub(r"(?i)^(prior art|research landscape|landscape|research|brief|papers|patents)\s*(for|on|about|of)?\s*", "", p)
        slots["topic"] = topic.strip(" .") or p
    return slots


async def fill_slots(pid: str, prompt: str, session_id: str) -> dict[str, Any]:
    pb = PLAYBOOKS[pid]
    slots = {k: v.get("default") for k, v in pb["slots"].items()}
    slots.update({k: v for k, v in _heuristic_slots(pid, prompt).items() if v not in (None, "")})
    extracted = await llm.complete_json(
        "You extract structured slots for a decision engine. Reply ONLY with JSON containing exactly these keys "
        f"(use null if unknown): {list(pb['slots'].keys())}. Money as a plain number in USD. Cities as plain city names.",
        f"Request: {prompt}", session_id=session_id, name="orchestrator.slot_fill")
    if isinstance(extracted, dict):
        for k, v in extracted.items():
            if k in slots and v not in (None, "", 0):
                slots[k] = v
    return slots


def _derive(pid: str, slots: dict[str, Any]) -> dict[str, Any]:
    d = dict(slots)
    today = datetime.utcnow().date()
    if pid == "lifeops_trip":
        d["origin_iata"], _ = lookup(slots.get("origin"))
        d["destination_iata"], d["currency_code"] = lookup(slots.get("destination"))
        days = int(slots.get("days") or 4)
        out = today + timedelta(days=int(slots.get("lead_days") or 30))
        d["outbound_date"] = out.isoformat()
        d["return_date"] = (out + timedelta(days=days)).isoformat()
        d["outbound_date_flex"] = (out + timedelta(days=2)).isoformat()
        d["return_date_flex"] = (out + timedelta(days=days + 2)).isoformat()
        d["nights"] = days
    if pid == "career_jobs":
        d["role_keyword"] = " ".join(str(slots.get("role", "")).split()[-2:]) or "developer"
    if pid == "research_ip":
        d["recent_year"] = today.year - 3
    return d


def _render(params: dict[str, Any], vars_: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in params.items():
        if isinstance(v, str):
            for m in re.findall(r"\{(\w+)\}", v):
                v = v.replace("{" + m + "}", str(vars_.get(m, "")))
        out[k] = v
    return out


def build_calls(pid: str, vars_: dict[str, Any], fallback_round: int = 0) -> list[EngineCall]:
    pb = PLAYBOOKS[pid]
    specs = pb["engines"] if fallback_round == 0 else pb.get("fallback_engines", [])
    if fallback_round > 1:  # second re-plan widens to all fallbacks + essentials again (fresh)
        specs = pb.get("fallback_engines", [])[::-1]
    return [EngineCall(engine=s["engine"], params=_render(s["params"], vars_), purpose=s.get("purpose", ""),
                       category=s.get("category", "generic"), essential=s.get("essential", True)) for s in specs]


async def plan(prompt: str, lens: str, session_id: str, forced: str | None = None,
               priorities: dict[str, float] | None = None) -> DecisionGraph:
    bus.publish(session_id, "agent.start", {"agent": "orchestrator", "label": "Classifying intent"}, agent="orchestrator")
    pid, scores = await classify(prompt, lens, forced)
    bus.publish(session_id, "orchestrator.intent", {"playbook_id": pid, "playbook": PLAYBOOKS[pid]["name"],
                                                     "scores": scores[:5]}, agent="orchestrator")
    slots = await fill_slots(pid, prompt, session_id)
    vars_ = _derive(pid, slots)
    pb = PLAYBOOKS[pid]
    weights = {k: v["weight"] for k, v in pb["dimensions"].items()}
    if priorities:
        for k, v in priorities.items():
            if k in weights:
                weights[k] = max(0.0, float(v))
        tot = sum(weights.values()) or 1
        weights = {k: round(v / tot, 4) for k, v in weights.items()}
    calls = build_calls(pid, vars_)

    nodes: list[DecisionNode] = []
    for k, v in slots.items():
        if v not in (None, ""):
            nodes.append(DecisionNode(id=f"ent_{k}", kind="entity", label=f"{k}: {v}"))
    for k, v in pb["dimensions"].items():
        nodes.append(DecisionNode(id=f"dim_{k}", kind="dimension", label=v["label"], meta={"weight": weights[k], "direction": v["direction"]}))
    if slots.get("budget"):
        nodes.append(DecisionNode(id="con_budget", kind="constraint", label=f"Total ≤ ${float(slots['budget']):,.0f}"))
    nodes.append(DecisionNode(id="con_verify", kind="constraint", label="Facts need ≥2 independent sources"))
    for c in calls:
        nodes.append(DecisionNode(id=c.id, kind="source", label=c.engine, meta={"purpose": c.purpose, "params": c.params}))
    for a in pb["actions"]:
        nodes.append(DecisionNode(id=f"act_{a}", kind="action", label=a))

    graph = DecisionGraph(playbook_id=pid, intent=pb["description"], lens=lens, slots=vars_, nodes=nodes, calls=calls, weights=weights)
    bus.publish(session_id, "orchestrator.graph", {"graph": graph.model_dump()}, agent="orchestrator")
    return graph

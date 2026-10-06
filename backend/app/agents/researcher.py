"""SERPAPI RESEARCHER & HYBRID RAG AGENT
 * parallel async fan-out (semaphore-bounded, backoff in transport)
 * normalization of every engine response -> Candidates
 * embedding + upsert into the vector store (Supabase pgvector / memory)
 * hybrid dense + full-text retrieval (RRF) for the session query
 * 2-source corroboration filter: unverified single-source facts are
   flagged — never silently passed downstream."""
from __future__ import annotations

import asyncio
import re
import statistics
from typing import Any

from ..config import get_settings
from ..models import Candidate, EngineCall
from ..services.events import bus
from ..services.llm import embedder
from ..services.normalize import normalize
from ..services.serpapi import CreditMeter, SerpApiError, serp
from ..services.store import store


def _brief(data: dict) -> dict:
    """Trim a raw SerpApi payload for the live log (keeps metadata + first items)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k in ("search_metadata", "search_parameters", "price_insights", "summary", "search_information"):
            out[k] = v
        elif isinstance(v, list):
            out[k] = v[:2] + ([f"… +{len(v) - 2} more"] if len(v) > 2 else [])
        elif isinstance(v, dict) and k in ("interest_over_time",):
            out[k] = {"timeline_data": (v.get("timeline_data") or [])[:3]}
    return out


def candidate_key(c: Candidate) -> str:
    return c.attributes.get("match_key") or f"{c.title.lower()}|{c.source.lower()}"


def apply_disruption(session_id: str, cands: list[Candidate], disruption: dict | None) -> list[Candidate]:
    """Edge-case injection used by the live demo / chaos testing: the
    targeted option's price spikes or it disappears from the fresh poll."""
    if not disruption:
        return cands
    target = disruption.get("target_key")
    kind = disruption.get("kind", "price_spike")
    pct = float(disruption.get("pct", 45))
    out = []
    hit = 0
    for c in cands:
        if candidate_key(c) == target:
            hit += 1
            if kind == "unavailable":
                continue
            old = c.price
            c.price = round((c.price or 0) * (1 + pct / 100), 2)
            c.attributes["disrupted"] = {"kind": kind, "old_price": old, "new_price": c.price}
        out.append(c)
    if hit:
        bus.publish(session_id, "watch.disruption_detected", {"kind": kind, "target_key": target, "pct": pct, "matches": hit},
                    agent="researcher")
    return out


async def fan_out(session_id: str, calls: list[EngineCall], meter: CreditMeter, *, fresh: bool = False,
                  round_: int = 0, disruption: dict | None = None) -> tuple[list[Candidate], dict, list[dict]]:
    s = get_settings()
    sem = asyncio.Semaphore(s.serp_concurrency)
    bus.publish(session_id, "agent.start", {"agent": "researcher", "label": f"Fan-out ×{len(calls)} (async, ≤{s.serp_concurrency} in flight)",
                                             "round": round_}, agent="researcher")

    async def one(call: EngineCall) -> dict:
        try:
            res = await serp.search(call.engine, call.params, session_id=session_id, call_id=call.id, sem=sem,
                                    meter=meter, purpose=call.purpose, fresh=fresh)
            cands, ctx = normalize(call.engine, res["data"], call.category)
            for c in cands:
                c.attributes["call_id"] = call.id
                c.attributes["call_variant"] = call.params.get("sort_by", "default")
            bus.publish(session_id, "serp.response", {
                "call_id": call.id, "engine": call.engine, "cached": res["cached"], "ms": res["ms"], "mode": res["mode"],
                "results": len(cands), "status": res["data"].get("search_metadata", {}).get("status", "Success"),
                "search_id": res["data"].get("search_metadata", {}).get("id"), "raw": _brief(res["data"]),
                "credits": meter.as_dict()}, agent="researcher")
            return {"call": call, "cands": cands, "ctx": ctx, "ok": True, "cached": res["cached"], "raw": res["data"]}
        except SerpApiError as e:
            bus.publish(session_id, "serp.error", {"call_id": call.id, "engine": call.engine, "error": str(e),
                                                   "status": e.status, "essential": call.essential}, agent="researcher")
            return {"call": call, "cands": [], "ctx": {}, "ok": False, "error": str(e)}
        except Exception as e:  # never let one engine sink the session
            bus.publish(session_id, "serp.error", {"call_id": call.id, "engine": call.engine, "error": repr(e)[:200],
                                                   "essential": call.essential}, agent="researcher")
            return {"call": call, "cands": [], "ctx": {}, "ok": False, "error": repr(e)}

    results = await asyncio.gather(*(one(c) for c in calls))
    cands: list[Candidate] = []
    ctx: dict[str, Any] = {}
    for r in results:
        cands.extend(r["cands"])
        for k, v in r["ctx"].items():
            ctx.setdefault(k, v)
    cands = apply_disruption(session_id, cands, disruption)
    log = [{"call_id": r["call"].id, "engine": r["call"].engine, "params": r["call"].params, "ok": r["ok"],
            "cached": r.get("cached", False), "error": r.get("error"), "purpose": r["call"].purpose,
            "raw": r.get("raw")} for r in results]
    return cands, ctx, log


async def index_and_retrieve(session_id: str, query: str, cands: list[Candidate], k: int = 12) -> list[dict]:
    """Embed normalized results into the vector store and run hybrid retrieval."""
    docs = []
    for c in cands:
        content = " ".join(str(x) for x in [c.title, c.source, c.category, c.price and f"${c.price}",
                                            c.attributes.get("snippet", ""), c.attributes.get("description", ""),
                                            c.attributes.get("company", ""), c.attributes.get("location", "")] if x)
        docs.append({"id": f"{session_id}:{c.id}", "session_id": session_id, "engine": c.engine, "category": c.category,
                     "title": c.title, "content": content, "url": c.url, "price": c.price,
                     "metadata": {"candidate_id": c.id, "source": c.source}})
    vecs = await embedder.embed([d["content"] for d in docs])
    for d, v in zip(docs, vecs):
        d["embedding"] = v
    n = await store.upsert_documents(docs)
    qv = (await embedder.embed([query], task="RETRIEVAL_QUERY"))[0]
    hits = await store.hybrid_search(query, qv, k=k, session_id=session_id)
    bus.publish(session_id, "rag.retrieval", {"indexed": n, "backend": store.backend, "embedder": embedder.provider,
                                               "hits": [{"title": h.get("title"), "engine": h.get("engine"), "rrf": h.get("rrf_score"),
                                                         "dense_rank": h.get("dense_rank"), "keyword_rank": h.get("keyword_rank"),
                                                         "similarity": h.get("similarity"),
                                                         "candidate_id": (h.get("metadata") or {}).get("candidate_id")} for h in hits]},
                agent="researcher")
    # relevance annotation for analyst (rrf normalized 0..1)
    if hits:
        mx = max(h.get("rrf_score") or 0 for h in hits) or 1
        rel = {(h.get("metadata") or {}).get("candidate_id"): (h.get("rrf_score") or 0) / mx for h in hits}
        for c in cands:
            c.attributes["relevance"] = round(rel.get(c.id, 0.0), 4)
    return hits


def _norm_title(t: str) -> set[str]:
    stop = {"the", "a", "and", "with", "for", "of", "new", "black", "silver", "standard", "midnight", "bundle", "pack"}
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in stop and len(w) > 1}


def corroborate(cands: list[Candidate], ctx: dict, min_sources: int = 2) -> dict:
    """Mark each candidate verified only when ≥min_sources independent
    observations agree on its key fact. Returns summary stats."""
    by_cat: dict[str, list[Candidate]] = {}
    for c in cands:
        by_cat.setdefault(c.category, []).append(c)

    # ---- flights: same itinerary (flight numbers) seen in independent result sets at a consistent price
    flights = by_cat.get("flight", [])
    pi = ctx.get("price_insights") or {}
    rng = pi.get("typical_price_range") or []
    groups: dict[str, list[Candidate]] = {}
    for f in flights:
        groups.setdefault(f.attributes.get("match_key", f.title), []).append(f)
    for key, grp in groups.items():
        variants = {g.attributes.get("call_variant") for g in grp}
        prices = [g.price for g in grp if g.price]
        consistent = prices and (max(prices) - min(prices)) / max(prices) <= 0.05
        for g in grp:
            src = []
            if len(variants) >= 2 and consistent:
                src += [f"google_flights:{v}" for v in sorted(variants)]
            elif grp:
                src.append(f"google_flights:{g.attributes.get('call_variant')}")
            if rng and g.price and rng[0] * 0.6 <= g.price <= rng[1] * 1.6:
                src.append("price_insights.typical_range")
            g.corroborating_sources = sorted(set(src))
    # de-duplicate flights that appear in both variants (keep one, already verified)
    seen: set[str] = set()
    dedup_flights = []
    for f in flights:
        k = f.attributes.get("match_key", f.title)
        if k in seen:
            f.attributes["duplicate"] = True
            continue
        seen.add(k)
        dedup_flights.append(f)

    # ---- hotels: Google Hotels rating corroborated by Google Maps listing
    places = {p.attributes.get("match_key"): p for p in by_cat.get("place", [])}
    for h in by_cat.get("hotel", []):
        src = ["google_hotels"]
        p = places.get(h.attributes.get("match_key"))
        if p and p.rating and h.rating and abs(p.rating - h.rating) <= 0.6:
            src.append("google_maps")
            h.attributes["maps_rating"] = p.rating
            h.attributes["maps_reviews"] = p.reviews
        h.corroborating_sources = src

    # ---- products: price consensus across independent engines (±18% of cross-engine median)
    prods = by_cat.get("product", [])
    if prods:
        per_engine_median = {}
        for e in {p.engine for p in prods}:
            ps = [p.price for p in prods if p.engine == e and p.price]
            if ps:
                per_engine_median[e] = statistics.median(ps)
        for p in prods:
            agree = [e for e, m in per_engine_median.items() if e != p.engine and p.price and abs(p.price - m) / m <= 0.18]
            p.corroborating_sources = [p.engine] + agree

    # ---- suppliers: quoted unit price must sit inside the marketplace bulk anchor band; MOQ must be stated
    sup = by_cat.get("supplier", [])
    anchors = [p.price for p in prods if p.price]
    if sup:
        med = statistics.median(anchors) if anchors else None
        for s_ in sup:
            src = ["google:organic"]
            if med and s_.price and med * 0.15 <= s_.price <= med * 1.6:
                src.append("marketplace_price_band")
            if s_.attributes.get("moq"):
                src.append("stated_moq")
            s_.corroborating_sources = src

    # ---- jobs: salary consistent with peer postings; posting freshness stated
    jobs = by_cat.get("job", [])
    sal = [j.price for j in jobs if j.price]
    med_s = statistics.median(sal) if sal else None
    news_titles = " ".join(n.title.lower() for n in by_cat.get("news", []))
    for j in jobs:
        src = ["google_jobs"]
        if med_s and j.price and abs(j.price - med_s) / med_s <= 0.4:
            src.append("peer_salary_band")
        if (j.attributes.get("company") or "").lower() in news_titles:
            src.append("google_news")
        j.corroborating_sources = src

    # ---- research: paper has citation graph; patent has publication record + cross-topic match
    patent_words = set().union(*[_norm_title(p.title) for p in by_cat.get("patent", [])]) if by_cat.get("patent") else set()
    paper_words = set().union(*[_norm_title(p.title) for p in by_cat.get("paper", [])]) if by_cat.get("paper") else set()
    for p in by_cat.get("paper", []):
        src = ["google_scholar"]
        if p.attributes.get("cited_by", 0) > 0:
            src.append("citation_graph")
        if len(_norm_title(p.title) & patent_words) >= 2:
            src.append("google_patents")
        p.corroborating_sources = src
    for p in by_cat.get("patent", []):
        src = ["google_patents"]
        if p.attributes.get("number"):
            src.append("publication_record")
        if len(_norm_title(p.title) & paper_words) >= 2:
            src.append("google_scholar")
        p.corroborating_sources = src

    for c in cands:
        if c.category in ("news", "place"):
            c.verified = True  # context signals, not decision facts
            continue
        c.verified = len(set(c.corroborating_sources)) >= min_sources

    decision = [c for c in cands if c.category not in ("news", "place") and not c.attributes.get("duplicate")]
    verified = [c for c in decision if c.verified]
    return {"total": len(decision), "verified": len(verified),
            "flagged": [{"id": c.id, "title": c.title, "sources": c.corroborating_sources} for c in decision if not c.verified][:20],
            "ratio": round(len(verified) / len(decision), 3) if decision else 0.0}

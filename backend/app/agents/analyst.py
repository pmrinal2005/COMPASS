"""ANALYST / COMPARER
 * weighted multi-criteria decision matrix (min-max normalized per
   dimension, direction-aware, user-priority weights)
 * statistical anomaly detection: robust z-score (median/MAD) against
   (a) the candidate's own recorded price history baseline and
   (b) its peer group in the current batch
 * trip playbooks compose flight × hotel bundles under the budget
 * confidence score from verification ratio, score margin, data coverage
   and anomaly status — below threshold the Orchestrator re-plans."""
from __future__ import annotations

import math
import re
import statistics
from typing import Any

from ..config import get_settings
from ..models import Candidate
from ..playbooks import PLAYBOOKS
from ..services.aggregate import build_insights, domain_entities, venue_entities
from ..services.events import bus
from ..services.llm import llm
from ..services.store import store


def robust_z(x: float, series: list[float]) -> float:
    if len(series) < 3:
        return 0.0
    med = statistics.median(series)
    mad = statistics.median([abs(v - med) for v in series]) or (0.05 * med if med else 1.0)
    return 0.6745 * (x - med) / mad


def item_key(c: Candidate) -> str:
    if c.category == "bundle":
        return "bundle:" + str(c.attributes.get("flight_key", c.title)) + "|" + str((c.attributes.get("hotel") or {}).get("title", ""))[:40]
    if c.category == "flight":
        return "flight:" + c.attributes.get("match_key", c.title)
    if c.category in ("venue_entity", "domain"):
        return f"{c.category}:{c.attributes.get('cluster') or c.attributes.get('domain')}"
    return f"{c.category}:{c.engine}:{re.sub(r'[^a-z0-9]+', '-', c.title.lower())[:60]}:{c.source.lower()[:20]}"


async def detect_anomalies(session_id: str, cands: list[Candidate]) -> list[dict]:
    flagged = []
    by_cat: dict[str, list[float]] = {}
    for c in cands:
        if c.price and not c.attributes.get("duplicate"):
            by_cat.setdefault(c.category, []).append(c.price)
    for c in cands:
        if not c.price or c.attributes.get("duplicate"):
            continue
        hist = await store.get_prices(item_key(c))
        z_hist = robust_z(c.price, hist) if len(hist) >= 3 else 0.0
        z_peer = robust_z(c.price, by_cat.get(c.category, []))
        reason = None
        if hist and len(hist) >= 3 and abs(z_hist) >= 3.0:
            reason = f"price {'spike' if z_hist > 0 else 'drop'} vs baseline (z={z_hist:+.1f}, median ${statistics.median(hist):,.0f})"
        elif hist and len(hist) < 3 and abs(c.price - hist[-1]) / hist[-1] > 0.12:
            reason = f"price moved {100 * (c.price - hist[-1]) / hist[-1]:+.0f}% since last observation (${hist[-1]:,.0f})"
        elif c.category in ("product", "supplier") and z_peer <= -3.5:
            reason = f"suspiciously low vs peers (z={z_peer:+.1f}) — possible bait listing"
        elif abs(z_peer) >= 4.5:
            reason = f"outlier vs peer group (z={z_peer:+.1f})"
        c.attributes["z_hist"] = round(z_hist, 2)
        c.attributes["z_peer"] = round(z_peer, 2)
        if reason:
            c.anomaly = reason
            flagged.append({"id": c.id, "title": c.title, "price": c.price, "reason": reason})
    if flagged:
        bus.publish(session_id, "analyst.anomaly", {"anomalies": flagged[:12]}, agent="analyst")
    return flagged


async def detect_entity_anomalies(session_id: str, pid: str, pool: list[Candidate], slots: dict) -> list[dict]:
    """Rating / rank anomalies for the entity playbooks (no price involved):
      venue  : blended rating fell >= 0.4 stars vs. the last stored observation (or the injected disruption)
      domain : the tracked domain's CTR-weighted visibility fell >= 30 % vs. its last observation (or rank-drop disruption)"""
    flagged = []
    for c in pool:
        if pid == "lifeops_local" and c.rating:
            hist = await store.get_prices(f"venue:{c.attributes.get('cluster')}")
            if hist and hist[-1] - c.rating >= 0.4 and not c.anomaly:
                c.anomaly = f"rating fell {hist[-1]:.1f}→{c.rating:.1f} since last observation"
        elif pid == "research_seo" and c.attributes.get("tracked"):
            hist = await store.get_prices(f"seo:{c.attributes.get('domain')}:{slots.get('keyword')}:{slots.get('market')}")
            vis = c.attributes.get("visibility", 0.0)
            if hist and hist[-1] >= 0.05 and (hist[-1] - vis) / hist[-1] >= 0.30 and not c.anomaly:
                c.anomaly = f"visibility fell {hist[-1]:.1f}→{vis:.1f} (−{100 * (hist[-1] - vis) / hist[-1]:.0f}%) since last poll"
        if c.anomaly:
            flagged.append({"id": c.id, "title": c.title, "price": None, "reason": c.anomaly})
    if flagged:
        bus.publish(session_id, "analyst.anomaly", {"anomalies": flagged[:12]}, agent="analyst")
    return flagged


async def record_entity_observations(pid: str, pool: list[Candidate], slots: dict) -> None:
    for c in pool:
        if pid == "lifeops_local" and c.rating:
            await store.record_price(f"venue:{c.attributes.get('cluster')}", c.rating)
        elif pid == "research_seo" and c.attributes.get("tracked"):
            await store.record_price(f"seo:{c.attributes.get('domain')}:{slots.get('keyword')}:{slots.get('market')}",
                                     max(float(c.attributes.get("visibility", 0.0)), 0.0))


def _minmax(vals: list[float | None], direction: str) -> list[float]:
    xs = [v for v in vals if v is not None]
    if not xs:
        return [0.5] * len(vals)
    lo, hi = min(xs), max(xs)
    out = []
    for v in vals:
        if v is None:
            out.append(0.35)  # missing data is penalized, not ignored
        elif hi == lo:
            out.append(1.0)
        else:
            n = (v - lo) / (hi - lo)
            out.append(1 - n if direction == "min" else n)
    return out


def _reputation(rating: float | None, reviews: int | None) -> float | None:
    if rating is None:
        return None
    # Bayesian-smoothed rating: pulls low-review items toward 3.8
    n = reviews or 0
    return (rating * n + 3.8 * 50) / (n + 50) + 0.05 * math.log10(n + 1)


def build_bundles(cands: list[Candidate], slots: dict) -> list[Candidate]:
    flights = sorted([c for c in cands if c.category == "flight" and not c.attributes.get("duplicate")], key=lambda c: c.price or 1e9)[:7]
    hotels = sorted([c for c in cands if c.category == "hotel"], key=lambda c: c.price or 1e9)[:8]
    nights = int(slots.get("nights") or slots.get("days") or 4)
    budget = float(slots.get("budget") or 0) or None
    out = []
    for f in flights:
        for h in hotels:
            hotel_total = (h.price or 0) * nights
            total = (f.price or 0) + hotel_total
            out.append(Candidate(
                title=f"{f.source} + {h.title}", category="bundle", engine="google_flights+google_hotels", source=f.source,
                url=h.url, price=round(total, 2), rating=h.rating, reviews=h.reviews, duration_min=f.duration_min,
                verified=f.verified and h.verified, corroborating_sources=sorted(set(f.corroborating_sources + h.corroborating_sources)),
                anomaly=f.anomaly or h.anomaly,
                attributes={"flight": f.model_dump(), "hotel": h.model_dump(), "flight_key": f.attributes.get("match_key"),
                            "flight_price": f.price, "hotel_total": hotel_total, "nights": nights,
                            "stops": f.attributes.get("stops", 0), "within_budget": (total <= budget) if budget else True,
                            "relevance": max(f.attributes.get("relevance", 0), h.attributes.get("relevance", 0))}))
    return out


def dimension_values(pid: str, c: Candidate, slots: dict) -> dict[str, float | None]:
    a = c.attributes
    budget = float(slots.get("budget") or 0) or None
    risk = (0.0 if c.verified else 0.5) + (0.5 if c.anomaly else 0.0) + 0.12 * float(a.get("stops") or 0)
    if c.attributes.get("sponsored"):
        risk += 0.1
    if pid in ("lifeops_trip",):
        return {"price": c.price, "time": c.duration_min, "reputation": _reputation(c.rating, c.reviews), "risk": risk,
                "compliance": 1.0 if a.get("within_budget", True) else 0.0}
    if pid == "lifeops_deals":
        cond = str(a.get("condition") or "").lower()
        if "pre-owned" in cond or "renewed" in c.title.lower():
            risk += 0.25
        return {"price": c.price, "reputation": _reputation(c.rating, c.reviews), "risk": risk,
                "compliance": 1.0 if (not budget or (c.price or 1e9) <= budget) else 0.0}
    if pid == "pro_supplier":
        moq = a.get("moq") or a.get("lot_size")
        return {"price": c.price, "moq": float(moq) if moq else None, "reputation": _reputation(c.rating, c.reviews),
                "risk": risk, "compliance": 1.0 if c.verified else 0.0}
    if pid == "career_jobs":
        age = a.get("age_days")
        return {"salary": c.price, "freshness": (-age if age is not None else None), "fit": a.get("relevance"),
                "risk": risk + (0.0 if a.get("salary") else 0.2)}
    if pid == "lifeops_local":
        return {"reputation": _reputation(c.rating, c.reviews),
                "consensus": float(a.get("consensus", 1)) - 0.5 * float(a.get("rating_spread") or 0),
                "popularity": math.log1p(c.reviews or 0), "value": float(a["price_level"]) if a.get("price_level") else None,
                "risk": risk + (0.35 if a.get("meets_filters") is False else 0.0)}
    if pid == "research_seo":
        return {"visibility": float(a.get("visibility", 0)), "coverage": float(a.get("coverage", 0)),
                "rank": float(a["avg_position"]) if a.get("avg_position") else None, "ai": float(a.get("ai_count", 0)), "risk": risk}
    if pid == "research_ip":
        yr = a.get("year")
        return {"relevance": a.get("relevance"), "impact": math.log1p(a.get("cited_by", 0)) if c.category == "paper" else 1.5,
                "freshness": float(yr) if yr else None, "risk": risk}
    return {"price": c.price, "risk": risk}


def decision_pool(pid: str, cands: list[Candidate], slots: dict) -> list[Candidate]:
    base = [c for c in cands if not c.attributes.get("duplicate")]
    if pid == "lifeops_trip":
        return build_bundles(base, slots)
    if pid == "lifeops_deals":
        return [c for c in base if c.category == "product"]
    if pid == "pro_supplier":
        sup = [c for c in base if c.category == "supplier" and c.price]
        lots = [c for c in base if c.category == "product" and c.engine == "ebay" and c.attributes.get("lot_size")]
        return sup + lots
    if pid == "career_jobs":
        return [c for c in base if c.category == "job"]
    if pid == "research_ip":
        return [c for c in base if c.category in ("paper", "patent")]
    if pid == "lifeops_local":
        return venue_entities(base, slots)
    if pid == "research_seo":
        return domain_entities(base, slots)[0]
    return base


def score(pid: str, pool: list[Candidate], weights: dict[str, float], slots: dict) -> list[Candidate]:
    dims = PLAYBOOKS[pid]["dimensions"]
    raw = [dimension_values(pid, c, slots) for c in pool]
    normed: dict[str, list[float]] = {}
    for d, spec in dims.items():
        normed[d] = _minmax([r.get(d) for r in raw], spec["direction"])
    for i, c in enumerate(pool):
        c.breakdown = {d: round(normed[d][i] * weights.get(d, 0), 4) for d in dims}
        c.attributes["dim_raw"] = {d: (round(v, 3) if isinstance(v, float) else v) for d, v in raw[i].items()}
        c.score = round(sum(c.breakdown.values()), 4)
        if c.anomaly:  # anomalies can never silently win
            c.score = round(c.score * 0.7, 4)
        if c.attributes.get("within_budget") is False:  # budget is a constraint, not just a preference
            c.score = round(c.score * 0.8, 4)
        if c.attributes.get("meets_filters") is False:  # rating / price-level filters are constraints too
            c.score = round(c.score * 0.8, 4)
    pool.sort(key=lambda c: -(c.score or 0))
    return pool


def confidence(ranked: list[Candidate], verification: dict, coverage: float) -> tuple[float, list[str]]:
    reasons = []
    if not ranked:
        return 0.0, ["no viable candidates"]
    top = ranked[0]
    margin = (top.score or 0) - (ranked[1].score or 0) if len(ranked) > 1 else 0.2
    v_ratio = verification.get("ratio", 0)
    conf = 0.30 * (1.0 if top.verified else 0.2) + 0.25 * min(1.0, v_ratio / 0.6) + 0.20 * min(1.0, margin / 0.05 + 0.4) \
        + 0.15 * coverage + 0.10 * (0.0 if top.anomaly else 1.0)
    if not top.verified:
        reasons.append("top option lacks 2-source corroboration")
    if top.anomaly:
        reasons.append(f"top option anomaly: {top.anomaly}")
    if coverage < 0.75:
        reasons.append(f"only {coverage:.0%} of essential data sources returned")
    if top.attributes.get("within_budget") is False:
        conf -= 0.25
        reasons.append("no option within budget")
    if top.attributes.get("meets_filters") is False:
        conf -= 0.15
        reasons.append("top option misses the requested rating / price-level filters")
    if margin < 0.01:
        reasons.append("top options are nearly tied")
    return round(max(0.0, min(1.0, conf)), 3), reasons


async def rationale(session_id: str, pid: str, ranked: list[Candidate], slots: dict, conf: float) -> str:
    top = ranked[:3]
    if not top:
        return "No viable options were found."
    summary = [{"title": c.title, "price": c.price, "score": c.score, "verified": c.verified, "breakdown": c.breakdown,
                "anomaly": c.anomaly} for c in top]
    out = await llm.complete(
        "You are the Analyst agent of a decision engine. In ≤70 words explain why option #1 wins, citing the weighted "
        "dimensions and verification. No markdown, plain sentences.",
        f"Playbook: {pid}\nConstraints: {slots}\nTop options: {summary}\nConfidence: {conf}",
        session_id=session_id, name="analyst.rationale")
    if out:
        return out.strip()
    t = top[0]
    if pid == "research_seo":
        tr = next((c for c in ranked if c.attributes.get("tracked")), None)
        lead = f"“{t.title}” leads the multi-engine visibility ranking (CTR-weighted score {t.attributes.get('visibility', 0):.1f}, found in {t.attributes.get('found_engines')}/{t.attributes.get('engines_polled')} engines)"
        if tr and tr is not t:
            where = f"#{ranked.index(tr) + 1} of {len(ranked)}"
            mine = f"; tracked domain {tr.title} sits {where} with visibility {tr.attributes.get('visibility', 0):.1f}, avg position {tr.attributes.get('avg_position') or 'n/a'}, AI-cited by {tr.attributes.get('ai_count', 0)} engine(s)"
        elif tr:
            mine = f"; that is the tracked domain, AI-cited by {tr.attributes.get('ai_count', 0)} engine(s)"
        else:
            mine = "; the tracked domain does not appear in any polled engine"
        return lead + mine + "."
    if pid == "lifeops_local":
        plats = t.attributes.get("platforms") or {}
        return (f"“{t.title}” ranks #1 (score {t.score:.2f}): blended ★{t.rating} over {t.reviews:,} reviews, cross-verified on "
                f"{len(plats)} platform(s) ({', '.join(plats)}), rating spread {t.attributes.get('rating_spread', 0)}"
                f"{'' if t.attributes.get('meets_filters', True) else ' — note: misses your filters'}.")
    best_dims = sorted(t.breakdown.items(), key=lambda x: -x[1])[:2]
    parts = [f"“{t.title}” ranks #1 with score {t.score:.2f}"]
    if t.price:
        parts.append(f"at ${t.price:,.0f}")
    parts.append("leading on " + " and ".join(d for d, _ in best_dims))
    if len(top) > 1:
        parts.append(f"(+{(t.score or 0) - (top[1].score or 0):.3f} over runner-up)")
    v = "verified by " + ", ".join(t.corroborating_sources[:3]) if t.verified else "NOT yet corroborated by 2 sources"
    return " ".join(parts) + f"; {v}."


async def analyze(session_id: str, pid: str, cands: list[Candidate], slots: dict, weights: dict, verification: dict,
                  coverage: float, ctx: dict) -> dict[str, Any]:
    s = get_settings()
    bus.publish(session_id, "agent.start", {"agent": "analyst", "label": "Building decision matrix"}, agent="analyst")
    anomalies = await detect_anomalies(session_id, cands)
    seo_ctx: dict = {}
    if pid == "research_seo":
        pool, seo_ctx = domain_entities([c for c in cands if not c.attributes.get("duplicate")], slots)
    else:
        pool = decision_pool(pid, cands, slots)
    if pid in ("lifeops_local", "research_seo"):
        anomalies += await detect_entity_anomalies(session_id, pid, pool, slots)
    ranked = score(pid, pool, weights, slots)
    # recommendations for supplier playbook: diversify vendors
    if pid == "pro_supplier":
        seen, div = set(), []
        for c in ranked:
            k = c.source.split("·")[-1].strip().lower()
            if k in seen:
                continue
            seen.add(k)
            div.append(c)
        ranked = div + [c for c in ranked if c not in div]
    conf, reasons = confidence(ranked, verification, coverage)
    why = await rationale(session_id, pid, ranked, slots, conf)
    dims = PLAYBOOKS[pid]["dimensions"]
    matrix = {
        "dimensions": [{"key": k, "label": v["label"], "weight": weights.get(k, 0), "direction": v["direction"]} for k, v in dims.items()],
        "rows": [{"id": c.id, "title": c.title, "category": c.category, "engine": c.engine, "source": c.source, "url": c.url,
                  "price": c.price, "rating": c.rating, "reviews": c.reviews, "score": c.score, "breakdown": c.breakdown,
                  "raw": c.attributes.get("dim_raw"), "verified": c.verified, "sources": c.corroborating_sources,
                  "anomaly": c.anomaly, "attributes": {k: v for k, v in c.attributes.items()
                                                       if k in ("stops", "nights", "flight_price", "hotel_total", "within_budget",
                                                                "moq", "lot_size", "salary", "company", "location", "posted", "remote",
                                                                "year", "cited_by", "number", "delivery", "condition", "snippet",
                                                                "maps_rating", "departure", "arrival", "flight_numbers", "authors", "consensus", "platforms",
                                                                "price_level", "rating_spread", "meets_filters", "address", "neighborhood",
                                                                "positions", "ai_cited", "ai_count", "visibility", "coverage", "avg_position",
                                                                "share_of_voice", "tracked", "best_position", "found_engines",
                                                                "engines_polled", "domain")}}
                 for c in ranked[:12]],
    }
    insights = build_insights(pid, ranked, cands, slots, {**ctx, **seo_ctx})
    result = {"matrix": matrix, "ranked": ranked, "confidence": conf, "low_confidence_reasons": reasons,
              "rationale": why, "anomalies": anomalies, "threshold": s.confidence_threshold, "insights": insights,
              "context": {k: v for k, v in ctx.items() if k in ("price_insights", "fx", "trend", "news")}}
    bus.publish(session_id, "analyst.matrix", {"matrix": matrix, "confidence": conf, "reasons": reasons, "rationale": why,
                                                "threshold": s.confidence_threshold, "context": result["context"],
                                                "insights": insights}, agent="analyst")
    # record observations -> future baselines for anomaly detection
    await record_entity_observations(pid, ranked, slots)
    seen_keys: set[str] = set()
    for c in [x for x in cands if x.category not in ("news", "place", "event", "stay", "venue", "serp", "ai_citation") and not x.attributes.get("duplicate")][:80] + ranked[:12]:
        k = item_key(c)
        if c.price and k not in seen_keys:
            seen_keys.add(k)
            await store.record_price(k, c.price)
    return result

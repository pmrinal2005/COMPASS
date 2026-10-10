"""Entity aggregation for the cross-platform playbooks.

lifeops_local  : Google Maps + Yelp + Tripadvisor listings  -> ONE venue entity (rating consensus)
research_seo   : per-engine SERP rows + AI citations         -> ONE domain entity (CTR-weighted visibility)

The aggregated Candidates carry *deterministic* ids so the Command Center can animate rank
movement between polls, and they are rebuilt from the raw candidates on session rehydrate.
"""
from __future__ import annotations

import hashlib
import math
import statistics
from typing import Any

from ..models import Candidate
from .entities import (AI_ENGINES, ENGINE_LABEL, ENGINE_WEIGHT, SERP_ENGINES, ctr, registrable_domain)


def _h(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:10]


# ------------------------------------------------------------------ venues
def venue_entities(cands: list[Candidate], slots: dict) -> list[Candidate]:
    groups: dict[str, list[Candidate]] = {}
    for c in cands:
        if c.category == "venue" and not c.attributes.get("duplicate"):
            groups.setdefault(c.attributes.get("cluster") or c.attributes.get("match_key") or c.title.lower(), []).append(c)
    min_rating = float(slots.get("min_rating") or 0)
    cap = int(slots.get("price_cap") or 4)
    out: list[Candidate] = []
    for cid, ms in groups.items():
        plats: dict[str, Candidate] = {}
        for m in ms:                                         # best-reviewed listing per platform
            k = m.attributes.get("platform") or m.source
            if k not in plats or (m.reviews or 0) > (plats[k].reviews or 0):
                plats[k] = m
        rated = [m for m in plats.values() if m.rating]
        wsum = sum(math.log1p(m.reviews or 0) + 1 for m in rated)
        rating = round(sum(m.rating * (math.log1p(m.reviews or 0) + 1) for m in rated) / wsum, 2) if rated and wsum else None
        reviews = sum(m.reviews or 0 for m in plats.values())
        levels = [m.attributes.get("price_level") for m in plats.values() if m.attributes.get("price_level")]
        level = int(round(statistics.mean(levels))) if levels else None
        spread = round(max(m.rating for m in rated) - min(m.rating for m in rated), 2) if len(rated) > 1 else 0.0
        name = (plats.get("Google Maps") or min(ms, key=lambda x: len(x.title))).title
        verified = any(m.verified for m in ms)
        dis = next((m.attributes["disrupted"] for m in ms if m.attributes.get("disrupted")), None)
        ent = Candidate(
            id=f"ent_{_h(cid)}", title=name, category="venue_entity", engine="+".join(sorted({m.engine for m in ms})),
            source=" · ".join(sorted(plats)), rating=rating, reviews=reviews, verified=verified,
            url=(plats.get("Yelp") or plats.get("Google Maps") or next(iter(plats.values()))).url,
            corroborating_sources=sorted({s for m in ms for s in m.corroborating_sources}),
            attributes={"cluster": cid, "match_key": cid, "consensus": len(plats), "price_level": level, "rating_spread": spread,
                        "meets_filters": bool((rating or 0) >= min_rating and (level is None or level <= cap)),
                        "address": next((m.attributes.get("address") for m in ms if m.attributes.get("address")), None),
                        "neighborhood": next((m.attributes.get("neighborhood") for m in ms if m.attributes.get("neighborhood")), None),
                        "relevance": max(m.attributes.get("relevance", 0) for m in ms),
                        "platforms": {k: {"title": m.title, "rating": m.rating, "reviews": m.reviews,
                                          "price_level": m.attributes.get("price_level"), "url": m.url} for k, m in plats.items()}},
        )
        if dis:
            ent.attributes["disrupted"] = dis
            if dis.get("kind") == "rating_drop":
                ent.anomaly = f"rating dropped {dis.get('old_rating')}→{dis.get('new_rating')} on every platform (fresh poll)"
        out.append(ent)
    return out


# ------------------------------------------------------------------ SEO
def domain_entities(cands: list[Candidate], slots: dict) -> tuple[list[Candidate], dict]:
    polled = sorted({c.engine for c in cands if c.category == "serp"})
    ai_engines = sorted({c.engine for c in cands if c.category == "ai_citation"})
    weights = {e: ENGINE_WEIGHT.get(e, 0.05) for e in polled}
    wsum = sum(weights.values()) or 1.0
    tracked = registrable_domain(str(slots.get("domain") or ""))
    by_dom: dict[str, list[Candidate]] = {}
    for c in cands:
        if c.category in ("serp", "ai_citation"):
            d = registrable_domain(c.attributes.get("domain") or c.source)
            if d:
                by_dom.setdefault(d, []).append(c)
    if tracked and tracked not in by_dom:
        by_dom[tracked] = []                                  # tracked domain absent everywhere -> still shown (0 visibility)
    out: list[Candidate] = []
    for dom, grp in by_dom.items():
        pos: dict[str, int] = {}
        ai: dict[str, bool] = {}
        best_url, best_pos, sample = None, 999, ""
        dis = None
        for c in grp:
            if c.category == "serp":
                p = int(c.attributes.get("position") or 99)
                if c.engine not in pos or p < pos[c.engine]:
                    pos[c.engine] = p
                if p < best_pos:
                    best_pos, best_url, sample = p, c.url, c.title
            else:
                ai[c.engine] = True
                best_url = best_url or c.url
            if c.attributes.get("disrupted"):
                dis = dis or c.attributes["disrupted"]
        vis = sum(weights[e] * ctr(p) for e, p in pos.items()) / (wsum * ctr(1)) * 100 if polled else 0.0
        avg_pos = round(statistics.mean(pos.values()), 1) if pos else None
        ent = Candidate(
            id=f"dom_{_h(dom)}", title=dom, category="domain", engine="multi-engine", source=dom, url=best_url,
            verified=any(c.verified for c in grp), corroborating_sources=sorted({s for c in grp for s in c.corroborating_sources}),
            attributes={"domain": dom, "tracked": dom == tracked, "positions": pos, "ai_cited": ai, "ai_count": len(ai),
                        "visibility": round(vis, 2), "coverage": round(len(pos) / len(polled), 3) if polled else 0.0,
                        "avg_position": avg_pos, "found_engines": len(pos), "engines_polled": len(polled), "sample_title": sample,
                        "relevance": max([c.attributes.get("relevance", 0) for c in grp] or [0]),
                        "best_position": min(pos.values()) if pos else None},
        )
        if dis:
            ent.attributes["disrupted"] = dis
            if dis.get("kind") == "rank_drop":
                ent.anomaly = f"rank dropped #{dis.get('old_position')}→#{dis.get('new_position')} in every engine (fresh poll)"
        out.append(ent)
    total_vis = sum(e.attributes["visibility"] for e in out) or 1.0
    for e in out:
        e.attributes["share_of_voice"] = round(100 * e.attributes["visibility"] / total_vis, 2)
    ctx = {"polled": polled, "ai_engines": ai_engines, "tracked": tracked, "weights": weights}
    return out, ctx


# ------------------------------------------------------------------ insights (panel payloads for the UI)
def build_insights(pid: str, ranked: list[Candidate], cands: list[Candidate], slots: dict, ctx: dict) -> dict | None:
    if pid == "lifeops_local":
        ev = [c for c in cands if c.category == "event"][:6]
        return {"kind": "venues", "city": slots.get("city"), "query": slots.get("query"),
                "platforms": ["Google Maps", "Yelp", "Tripadvisor"] if slots.get("yelp_supported", True) else ["Google Maps", "Tripadvisor"],
                "yelp_supported": bool(slots.get("yelp_supported", True)),
                "min_rating": slots.get("min_rating"), "price_cap": slots.get("price_cap"),
                "venues": [{"id": c.id, "title": c.title, "rating": c.rating, "reviews": c.reviews, "verified": c.verified,
                            "anomaly": c.anomaly, "price_level": c.attributes.get("price_level"), "spread": c.attributes.get("rating_spread"),
                            "meets_filters": c.attributes.get("meets_filters"), "platforms": c.attributes.get("platforms"), "score": c.score}
                           for c in ranked[:8]],
                "events": [{"title": e.title, "when": e.attributes.get("when"), "venue": e.attributes.get("venue"), "url": e.url,
                            "tickets": e.attributes.get("tickets"), "kind": e.attributes.get("kind"), "thumbnail": e.attributes.get("thumbnail")} for e in ev]}
    if pid == "research_seo":
        pool = ranked
        tr = next((c for c in pool if c.attributes.get("tracked")), None)
        polled = ctx.get("polled") or sorted({e for c in pool for e in c.attributes.get("positions", {})})
        ai_engines = ctx.get("ai_engines") or []
        grid = []
        for e in polled:
            pos = tr.attributes["positions"].get(e) if tr else None
            leader = min(((c.attributes["positions"].get(e), c.title) for c in pool if c.attributes["positions"].get(e)), default=(None, None))
            grid.append({"engine": e, "label": ENGINE_LABEL.get(e, e), "weight": ENGINE_WEIGHT.get(e, 0.05), "position": pos,
                         "found": pos is not None, "ctr": round(ctr(pos), 4) if pos else 0.0, "leader": leader[1], "leader_pos": leader[0]})
        ai = [{"engine": e, "label": ENGINE_LABEL.get(e, e), "cited": bool(tr and tr.attributes["ai_cited"].get(e))} for e in ai_engines]
        rank_of = (pool.index(tr) + 1) if tr in pool else None
        return {"kind": "seo", "domain": ctx.get("tracked") or slots.get("domain"), "keyword": slots.get("keyword"), "market": slots.get("market"),
                "grid": grid, "ai": ai, "rank_of": rank_of, "total_domains": len(pool),
                "visibility": tr.attributes["visibility"] if tr else 0.0, "share_of_voice": tr.attributes["share_of_voice"] if tr else 0.0,
                "coverage": tr.attributes["coverage"] if tr else 0.0, "avg_position": tr.attributes["avg_position"] if tr else None,
                "anomaly": tr.anomaly if tr else None,
                "leaders": [{"domain": c.title, "visibility": c.attributes["visibility"], "found": c.attributes["found_engines"]} for c in pool[:5]],
                "ai_text": (ctx.get("ai_text") or {}), }
    if pid == "lifeops_trip":
        ev = [c for c in cands if c.category == "event"][:5]
        stays = sorted([c for c in cands if c.category == "stay"], key=lambda c: c.price or 1e9)[:3]
        if not ev and not stays:
            return None
        return {"kind": "trip", "events": [{"title": e.title, "when": e.attributes.get("when"), "venue": e.attributes.get("venue"), "url": e.url, "kind": e.attributes.get("kind"),
                            "thumbnail": e.attributes.get("thumbnail")} for e in ev],
                "stays": [{"title": s.title, "price": s.price, "rating": s.rating, "reviews": s.reviews, "url": s.url, "verified": s.verified,
                           "qualifier": s.attributes.get("qualifier")} for s in stays]}
    return None

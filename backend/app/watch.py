"""Recurring 'watch' polls. A watch is a standing SerpApi consumer:
every tick re-queries its engine (fresh, bypassing dedupe), compares the
tracked item's price to its baseline + history (robust z / % move), and on
a significant move notifies and — if tied to a session — triggers the
bounded auto re-plan. Triggered by Render Cron / GitHub Actions hitting
POST /api/watch/tick (no workflow server)."""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

from .config import get_settings
from .models import new_id
from .services.demo_data import demo_response
from .services.entities import registrable_domain, same_entity
from .services.events import bus
from .services.normalize import normalize
from .services.notify import telegram
from .services.serpapi import CreditMeter, serp
from .services.store import store

CATEGORY = {"google_flights": "flight", "google_hotels": "hotel", "google_shopping": "product", "amazon": "product",
            "walmart": "product", "ebay": "product", "google_patents": "patent", "google_jobs": "job",
            "google_maps": "venue", "yelp": "venue", "tripadvisor": "venue", "google": "serp", "bing": "serp", "duckduckgo": "serp",
            "yahoo": "serp", "yandex": "serp", "baidu": "serp", "naver": "serp"}
METRICS = ("price", "rating", "position")


async def create_watch(*, session_id: str | None, label: str, engine: str, params: dict, target_title: str | None,
                       baseline_price: float | None, threshold_pct: float = 8.0, cadence_minutes: int = 30,
                       metric: str = "price", target_domain: str | None = None) -> dict:
    """A watch tracks ONE number per poll: a price (default), a venue rating, or a domain's rank position."""
    w = {"id": new_id("w_"), "session_id": session_id, "label": label, "engine": engine, "params": params, "metric": metric if metric in METRICS else "price",
         "target_domain": target_domain,
         "target_title": target_title, "baseline_price": baseline_price, "last_price": baseline_price,
         "threshold_pct": threshold_pct, "cadence_minutes": cadence_minutes, "active": True,
         "last_checked": None, "created_at": time.time(), "history": [], "alerts": 0}
    await store.put("watches", w)
    if session_id:
        bus.publish(session_id, "watch.created", {"watch": w}, agent="actor")
    return w


def _match(cands, w) -> Any:
    if not cands:
        return None
    if w.get("metric") == "position" and w.get("target_domain"):
        dom = registrable_domain(w["target_domain"])
        rows = [c for c in cands if registrable_domain(c.attributes.get("domain") or c.source) == dom]
        return min(rows, key=lambda c: c.attributes.get("position") or 99) if rows else None
    if w.get("metric") == "rating":
        t = w.get("target_title") or ""
        rows = [c for c in cands if t and same_entity(c.title, t)]
        return max(rows, key=lambda c: c.reviews or 0) if rows else None
    t = (w.get("target_title") or "").lower()
    if t:
        for c in cands:
            if c.title.lower() == t:
                return c
        tw = set(t.split())
        best = max(cands, key=lambda c: len(tw & set(c.title.lower().split())))
        if len(tw & set(best.title.lower().split())) >= max(1, len(tw) // 2):
            return best
    priced = [c for c in cands if c.price]
    return min(priced, key=lambda c: c.price) if priced else None


async def check_watch(w: dict, *, force: bool = False) -> dict:
    s = get_settings()
    now = time.time()
    if not force and w.get("last_checked") and now - float(w["last_checked"]) < w.get("cadence_minutes", 30) * 60:
        return {"id": w["id"], "skipped": "not due"}
    meter = CreditMeter(1)
    sem = asyncio.Semaphore(1)
    sid = w.get("session_id") or f"watch-{w['id']}"
    if s.is_demo:
        # time-bucketed drift so successive demo polls show real movement
        data = demo_response(w["engine"], w["params"], drift_bucket=int(now // 600))
        meter.spent = 1
    else:
        res = await serp.search(w["engine"], w["params"], session_id=sid, call_id=new_id("wcall_"), sem=sem, meter=meter,
                                purpose=f"watch:{w['label']}", fresh=True)
        data = res["data"]
    cands, _ = normalize(w["engine"], data, CATEGORY.get(w["engine"], "generic"), w["params"])
    hit = _match(cands, w)
    metric = w.get("metric", "price")
    if metric == "rating":
        value = hit.rating if hit else None
    elif metric == "position":
        value = float(hit.attributes.get("position")) if hit else None
        if value is None and not hit and cands:
            value = 31.0                                   # tracked domain fell out of the top 30 -> worst observable rank
    else:
        value = hit.price if hit else None
    price = value
    hist = [h["price"] for h in w.get("history", []) if h.get("price")]
    base = w.get("baseline_price") or (hist[0] if hist else price)
    change_pct = ((price - base) / base * 100) if (price and base) else 0.0
    z = 0.0
    if price and len(hist) >= 3:
        med = statistics.median(hist)
        mad = statistics.median([abs(x - med) for x in hist]) or 0.05 * med
        z = 0.6745 * (price - med) / mad
    if metric == "rating":                                  # only a *drop* is bad news for a venue
        bad = change_pct <= -w.get("threshold_pct", 8.0) or z <= -3.0
    elif metric == "position":                              # a higher number = worse rank
        bad = change_pct >= w.get("threshold_pct", 8.0) or (price and base and price - base >= 3) or z >= 3.0
    else:
        bad = abs(change_pct) >= w.get("threshold_pct", 8.0) or abs(z) >= 3.0
    triggered = bool(price and bad)
    w["history"] = (w.get("history", []) + [{"ts": now, "price": price}])[-60:]
    w["last_price"] = price
    w["last_checked"] = now
    out = {"id": w["id"], "label": w["label"], "metric": metric, "price": price, "baseline": base, "change_pct": round(change_pct, 2),
           "z": round(z, 2), "triggered": triggered, "matched": hit.title if hit else None}
    if triggered:
        w["alerts"] = w.get("alerts", 0) + 1
        fmt = (lambda v: f"${v:,.0f}") if metric == "price" else ((lambda v: f"★{v:.1f}") if metric == "rating" else (lambda v: f"#{v:.0f}"))
        out["notify"] = await telegram(f"<b>COMPASS watch</b> · {w['label']}\n{hit.title if hit else ''}\n"
                                       f"{fmt(base)} → {fmt(price)} ({change_pct:+.1f}%)")
    await store.put("watches", w)
    if w.get("session_id"):
        bus.publish(w["session_id"], "watch.tick", out, agent="researcher")
        if triggered:
            from .graph import RUNTIME, repoll  # bounded auto re-plan on the owning session
            if w["session_id"] in RUNTIME and RUNTIME[w["session_id"]].state.get("graph"):
                asyncio.create_task(repoll(w["session_id"]))
                out["replan"] = "scheduled"
    return out


async def tick(force: bool = False) -> dict:
    watches = [w for w in await store.list("watches", limit=500) if w.get("active", True)]
    results = await asyncio.gather(*(check_watch(w, force=force) for w in watches), return_exceptions=True)
    clean = [r if isinstance(r, dict) else {"error": repr(r)[:200]} for r in results]
    return {"checked": len([r for r in clean if not r.get("skipped")]), "total": len(watches), "results": clean, "ts": time.time()}

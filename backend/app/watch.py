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
from .services.events import bus
from .services.normalize import normalize
from .services.notify import telegram
from .services.serpapi import CreditMeter, serp
from .services.store import store

CATEGORY = {"google_flights": "flight", "google_hotels": "hotel", "google_shopping": "product", "amazon": "product",
            "walmart": "product", "ebay": "product", "google_patents": "patent", "google_jobs": "job"}


async def create_watch(*, session_id: str | None, label: str, engine: str, params: dict, target_title: str | None,
                       baseline_price: float | None, threshold_pct: float = 8.0, cadence_minutes: int = 30) -> dict:
    w = {"id": new_id("w_"), "session_id": session_id, "label": label, "engine": engine, "params": params,
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
    price = hit.price if hit else None
    hist = [h["price"] for h in w.get("history", []) if h.get("price")]
    base = w.get("baseline_price") or (hist[0] if hist else price)
    change_pct = ((price - base) / base * 100) if (price and base) else 0.0
    z = 0.0
    if price and len(hist) >= 3:
        med = statistics.median(hist)
        mad = statistics.median([abs(x - med) for x in hist]) or 0.05 * med
        z = 0.6745 * (price - med) / mad
    triggered = bool(price and (abs(change_pct) >= w.get("threshold_pct", 8.0) or abs(z) >= 3.0))
    w["history"] = (w.get("history", []) + [{"ts": now, "price": price}])[-60:]
    w["last_price"] = price
    w["last_checked"] = now
    out = {"id": w["id"], "label": w["label"], "price": price, "baseline": base, "change_pct": round(change_pct, 2),
           "z": round(z, 2), "triggered": triggered, "matched": hit.title if hit else None}
    if triggered:
        w["alerts"] = w.get("alerts", 0) + 1
        out["notify"] = await telegram(f"<b>COMPASS watch</b> · {w['label']}\n{hit.title if hit else ''}\n"
                                       f"${base:,.0f} → ${price:,.0f} ({change_pct:+.1f}%)")
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

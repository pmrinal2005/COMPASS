"""ACTOR / AUTOMATOR
Turns the top recommendation into executable ActionProposals. Anything
with financial, legal or irreversible consequence (booking, applying,
sending an RFQ) is created with requires_approval=True and only runs
after a Human-in-the-Loop Approve. Low-risk actions (generate document,
calendar file) are still shown as cards but may auto-run.
Execution = plain Python functions (Playwright, Telegram, Resend, ICS,
docs) — no workflow server."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from ..models import ActionProposal, Candidate
from ..services import documents as docs
from ..services.browser import run_flow
from ..services.events import bus
from ..services.notify import email, telegram
from ..services.store import store
from ..services.tracing import tracer


def _c(c: Candidate) -> dict:
    return c.model_dump()


def propose(session_id: str, pid: str, ranked: list[Candidate], slots: dict, prompt: str, rationale: str,
            conf: float, matrix_rows: list[dict], insights: dict | None = None) -> list[ActionProposal]:
    if not ranked:
        return []
    top = ranked[0]
    acts: list[ActionProposal] = []
    extra: list[str] = []
    if insights and insights.get("kind") == "seo":
        extra = ["## Engine grid", "", "| Engine | Position | Leader |", "|---|---|---|"] + \
                [f"| {g['label']} | {('#' + str(g['position'])) if g['found'] else 'not in top results'} | {g.get('leader') or '—'} |" for g in insights["grid"]] + \
                ["", "**AI citations:** " + (", ".join(f"{a['label']}: {'cited ✅' if a['cited'] else 'not cited'}" for a in insights["ai"]) or "n/a")]
    elif insights and insights.get("kind") == "venues":
        extra = ["## Platform consensus", ""] + [f"- **{v['title']}** — " + ", ".join(f"{k} ★{p.get('rating')}" for k, p in (v.get("platforms") or {}).items())
                                                    for v in insights["venues"][:5]]
        if insights.get("events"):
            extra += ["", "## What's on", ""] + [f"- {e['title']} ({e.get('when') or 'soon'})" for e in insights["events"][:4]]
    report_md = docs.markdown_report(f"COMPASS decision — {pid}", prompt, rationale, matrix_rows, conf, extra or None)

    if pid == "lifeops_trip":
        f = top.attributes.get("flight", {})
        h = top.attributes.get("hotel", {})
        acts.append(ActionProposal(session_id=session_id, type="booking_flow", risk="high",
                                   title=f"Book trip bundle · ${top.price:,.0f}",
                                   description=f"Flight {f.get('title', '')} (${f.get('price', 0):,.0f}) + {h.get('title', '')} "
                                               f"× {top.attributes.get('nights')} nights. Playwright walks pre-checkout; payment stays manual.",
                                   payload={"candidate": _c(top), "url": h.get("url") or "https://www.google.com/travel/flights",
                                            "steps": ["Open booking page", "Verify live price matches recommendation",
                                                      "Select dates & guests", "Fill traveler details (from profile)", "Stop at payment for human"]}))
        fa = f.get("attributes", {})
        acts.append(ActionProposal(session_id=session_id, type="calendar_invite", risk="low", requires_approval=False,
                                   title="Add trip to calendar (.ics)",
                                   description="Outbound flight, hotel check-in/out and return as calendar events.",
                                   payload={"events": [
                                       {"title": f"✈ {f.get('title', 'Flight')}", "start": fa.get("departure"), "end": fa.get("arrival"),
                                        "description": f"Flights: {', '.join(x for x in (fa.get('flight_numbers') or []) if x)}"},
                                       {"title": f"🏨 Check-in {h.get('title', '')}", "start": slots.get("outbound_date"),
                                        "end": slots.get("return_date"), "location": slots.get("destination", "")}]}))
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title="Watch this fare for price moves",
                                   description="Poll Google Flights on a schedule; alert + auto re-plan on a ≥8% move.",
                                   payload={"engine": "google_flights", "label": f"{slots.get('origin_iata')}→{slots.get('destination_iata')}",
                                            "params": {"departure_id": slots.get("origin_iata"), "arrival_id": slots.get("destination_iata"),
                                                       "outbound_date": slots.get("outbound_date"), "return_date": slots.get("return_date"),
                                                       "currency": "USD", "hl": "en", "type": "1", "adults": str(slots.get("adults") or 1)},
                                            "target_title": f.get("title"), "baseline_price": f.get("price")}))
    elif pid == "lifeops_deals":
        acts.append(ActionProposal(session_id=session_id, type="booking_flow", risk="high",
                                   title=f"Buy from {top.source} · ${top.price:,.2f}",
                                   description="Playwright opens the listing, verifies price & stock, adds to cart and stops before payment.",
                                   payload={"candidate": _c(top), "url": top.url,
                                            "steps": ["Open listing", "Verify price & stock", "Add to cart", "Stop at payment for human"]}))
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title="Watch for a price drop",
                                   description="Re-check this product across merchants; alert on ≥8% drop.",
                                   payload={"engine": top.engine if top.engine != "walmart" else "google_shopping",
                                            "label": slots.get("product"),
                                            "params": {"q": slots.get("product"), "gl": "us", "hl": "en"} if top.engine != "amazon"
                                            else {"k": slots.get("product"), "amazon_domain": "amazon.com"},
                                            "target_title": top.title, "baseline_price": top.price}))
    elif pid == "pro_supplier":
        n = int(slots.get("count") or 3)
        shortlist = matrix_rows[:n]
        rfqs = [docs.rfq_email(slots.get("product", "product"), int(slots.get("quantity") or 500), r) for r in shortlist]
        acts.append(ActionProposal(session_id=session_id, type="email_rfq", risk="medium",
                                   title=f"Send RFQ to top {len(shortlist)} suppliers",
                                   description="Draft RFQs (tiered pricing, MOQ, lead time, certifications) queued for your approval.",
                                   payload={"suppliers": [{"title": r["title"], "url": r.get("url"), "price": r.get("price")} for r in shortlist],
                                            "drafts": rfqs}))
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title="Monitor supplier price band",
                                   description="Weekly sweep of wholesale price anchors; alert on ≥8% shifts.",
                                   payload={"engine": "google_shopping", "label": f"{slots.get('product')} bulk",
                                            "params": {"q": f"{slots.get('product')} bulk lot wholesale", "gl": "us", "hl": "en"},
                                            "target_title": None, "baseline_price": top.price}))
    elif pid == "career_jobs":
        acts.append(ActionProposal(session_id=session_id, type="application", risk="high",
                                   title=f"Apply: {top.title}",
                                   description="Tailored cover note generated; Playwright opens the application form and pre-fills — you submit.",
                                   payload={"candidate": _c(top), "url": top.url, "cover_note": docs.cover_note(_c(top)),
                                            "steps": ["Open application", "Pre-fill profile", "Attach résumé + cover note", "Stop before submit"]}))
        acts.append(ActionProposal(session_id=session_id, type="calendar_invite", risk="low", requires_approval=False,
                                   title="Block interview-prep time (.ics)", description="2 prep sessions in your calendar.",
                                   payload={"events": [{"title": f"Interview prep — {top.attributes.get('company')}",
                                                        "description": top.title}]}))
    elif pid == "lifeops_local":
        plats = top.attributes.get("platforms") or {}
        sat = datetime.utcnow() + timedelta(days=(5 - datetime.utcnow().weekday()) % 7 or 7)
        acts.append(ActionProposal(session_id=session_id, type="booking_flow", risk="high",
                                   title=f"Reserve a table · {top.title}",
                                   description=f"Cross-verified on {len(plats)} platform(s) ({', '.join(plats)}) · blended ★{top.rating}. "
                                               "Playwright opens the listing, checks hours/availability, fills the party details and stops before confirming.",
                                   payload={"candidate": _c(top), "url": top.url,
                                            "steps": ["Open venue listing", "Verify rating & hours match the matrix", "Select party size & time",
                                                      "Fill guest details (from profile)", "Stop before confirmation for human"]}))
        acts.append(ActionProposal(session_id=session_id, type="calendar_invite", risk="low", requires_approval=False,
                                   title="Add the table to calendar (.ics)", description="Saturday 19:00 hold with the address and platform links.",
                                   payload={"events": [{"title": f"🍽 {top.title}", "start": sat.strftime("%Y-%m-%d") + " 19:00",
                                                        "end": sat.strftime("%Y-%m-%d") + " 21:00", "location": top.attributes.get("address") or slots.get("city", ""),
                                                        "description": f"{slots.get('query', '')} · ★{top.rating} on {', '.join(plats)}"}]}))
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title="Watch this venue's rating",
                                   description="Re-poll Google Maps on a schedule; alert + auto re-plan if the rating drops ≥ 8 %.",
                                   payload={"engine": "google_maps", "label": f"{top.title} ★", "metric": "rating",
                                            "params": {"q": f"{slots.get('query')} in {slots.get('city')}", "type": "search", "hl": "en", "gl": slots.get("gl", "us")},
                                            "target_title": (plats.get("Google Maps") or {}).get("title") or top.title, "baseline_price": top.rating}))
    elif pid == "research_seo":
        dom = slots.get("domain")
        tr = next((c for c in ranked if c.attributes.get("tracked")), top)       # the TRACKED domain, not the SERP leader
        pos = (tr.attributes.get("positions") or {})
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title=f"Watch {dom} rank on Google",
                                   description="Poll Google organic on a schedule; alert + auto re-plan if the tracked domain slips ≥ 8 % (or ≥ 3 positions).",
                                   payload={"engine": "google", "label": f"{dom} · {slots.get('keyword')}", "metric": "position", "target_domain": dom,
                                            "params": {"q": slots.get("keyword"), "gl": slots.get("gl", "us"), "hl": slots.get("hl", "en")},
                                            "target_title": dom, "baseline_price": float(pos.get("google")) if pos.get("google") else None}))
    elif pid == "research_ip":
        acts.append(ActionProposal(session_id=session_id, type="watch", risk="low", title="Weekly prior-art watch",
                                   description="Re-run Patents sweep weekly; notify on new filings.",
                                   payload={"engine": "google_patents", "label": slots.get("topic"), "params": {"q": slots.get("topic")},
                                            "target_title": None, "baseline_price": None}))

    acts.append(ActionProposal(session_id=session_id, type="document", risk="low", requires_approval=False,
                               title="Generate decision report", description="Markdown + HTML report with matrix, rationale & sources.",
                               payload={"markdown": report_md}))
    acts.append(ActionProposal(session_id=session_id, type="notify", risk="low",
                               title="Send summary via Telegram + email",
                               description="Push the recommendation and receipt to your channels.",
                               payload={"text": f"<b>COMPASS</b> · {pid}\n#1 {top.title}" + (f" — ${top.price:,.0f}" if top.price else "")
                                                + f"\nConfidence {conf:.0%}\n{rationale[:500]}", "markdown": report_md}))
    return acts


async def execute(action: ActionProposal) -> dict[str, Any]:
    """Run an approved action; returns a receipt."""
    t0 = time.time()
    p = action.payload
    sid = action.session_id
    bus.publish(sid, "actor.executing", {"action_id": action.id, "type": action.type, "title": action.title}, agent="actor")
    receipt: dict[str, Any] = {"action_id": action.id, "type": action.type, "title": action.title}

    if action.type in ("booking_flow", "application"):
        receipt["browser"] = await run_flow(p.get("url"), p.get("steps", []))
        receipt["confirmation"] = f"CMP-{action.id[-6:].upper()}"
        if p.get("cover_note"):
            receipt["cover_note"] = p["cover_note"]
    elif action.type == "calendar_invite":
        receipt["ics"] = docs.ics(p.get("events", []))
        receipt["filename"] = "compass-trip.ics"
    elif action.type == "document":
        receipt["markdown"] = p.get("markdown", "")
        receipt["html"] = docs.md_to_html(p.get("markdown", ""))
    elif action.type == "email_rfq":
        sent = []
        for d in p.get("drafts", []):
            sent.append(await email(d["subject"], "<pre style='font-family:system-ui'>" + d["body"] + "</pre>"))
        receipt["drafts"] = p.get("drafts", [])
        receipt["delivery"] = sent
    elif action.type == "notify":
        receipt["delivery"] = [await telegram(p.get("text", "")),
                               await email("COMPASS recommendation", docs.md_to_html(p.get("markdown", "")))]
    elif action.type == "watch":
        from ..watch import create_watch  # local import avoids cycle
        w = await create_watch(session_id=sid, label=p.get("label") or "watch", engine=p["engine"], params=p["params"],
                               target_title=p.get("target_title"), baseline_price=p.get("baseline_price"),
                               metric=p.get("metric", "price"), target_domain=p.get("target_domain"))
        receipt["watch"] = w
    receipt["elapsed_s"] = round(time.time() - t0, 2)
    receipt["executed_at"] = time.time()
    action.status = "executed"
    action.receipt = receipt
    await store.put("actions", {**action.model_dump(), "created_at": action.created_at})
    tracer.span(sid, f"actor:{action.type}", {"action_id": action.id}, {k: v for k, v in receipt.items() if k not in ("html", "ics")})
    bus.publish(sid, "actor.receipt", {"action_id": action.id, "receipt": {k: v for k, v in receipt.items() if k != "html"}}, agent="actor")
    return receipt

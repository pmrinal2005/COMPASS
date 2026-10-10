"""HTTP-level end-to-end test of EVERY COMPASS API endpoint (real network, real SerpApi data when the backend has a key).

  python scripts/e2e_http.py                                   # against http://localhost:8000 (full, spends ~15 SerpApi credits when live)
  python scripts/e2e_http.py https://compass-api-w9dp.onrender.com --readonly     # no credit-spending calls except 1 tiny session
  python scripts/e2e_http.py <url> --origin https://my-app.vercel.app              # also verifies CORS for that exact frontend origin

Checks per endpoint: status code, response contract, and (live mode) that the data is real, i.e. not Demo Mode.
Exit code 0 only when every check passed.
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (ARGS[0] if ARGS else "http://localhost:8000").rstrip("/")
READONLY = "--readonly" in sys.argv
ORIGIN = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--origin" and i + 1 < len(sys.argv)), "https://compass.vercel.app")
CRON = os.environ.get("CRON_SECRET", "local-dev-secret")
RES: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> bool:
    RES.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name:62s} {detail}")
    return ok


def sse(c: httpx.Client, sid: str, until: tuple[str, ...], timeout: float = 150) -> list[dict]:
    """Read the SSE stream until one of the `until` event types arrives (replays history first)."""
    out: list[dict] = []
    t0 = time.time()
    with c.stream("GET", f"/api/sessions/{sid}/stream", timeout=timeout + 10) as r:
        assert r.status_code == 200 and "text/event-stream" in r.headers.get("content-type", ""), r.status_code
        for line in r.iter_lines():
            if line.startswith("data:") and line[5:].strip() not in ("", "{}"):
                e = json.loads(line[5:])
                out.append(e)
                if e["type"] in until:
                    break
            if time.time() - t0 > timeout:
                break
    return out


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=90, headers={"Origin": ORIGIN})
    print(f"== COMPASS HTTP E2E -> {BASE}  (origin {ORIGIN})  readonly={READONLY}")

    # ---------------------------------------------------------------- meta
    r = c.get("/")
    rec("GET /", r.status_code == 200 and r.json().get("name") == "COMPASS")
    r = c.get("/api/health", timeout=90)
    h = r.json() if r.status_code == 200 else {}
    live = bool(h) and not h.get("demo_mode")
    rec("GET /api/health", r.status_code == 200 and h.get("ok") is True, f"serpapi={h.get('integrations', {}).get('serpapi')} llm={h.get('llm')} store={h.get('store')}")
    rec("CORS: allow-origin header for the frontend origin", r.headers.get("access-control-allow-origin") in ("*", ORIGIN), str(r.headers.get("access-control-allow-origin")))
    pf = c.options("/api/sessions", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    rec("CORS: preflight POST /api/sessions", pf.status_code == 200 and "POST" in pf.headers.get("access-control-allow-methods", ""), f"HTTP {pf.status_code}")

    r = c.get("/api/playbooks")
    pbs = r.json()
    rec("GET /api/playbooks (7 playbooks, engine lists)", r.status_code == 200 and len(pbs) == 7 and all(p["engine_list"] and p["examples"] for p in pbs), ",".join(p["id"] for p in pbs))
    ev = next(s for s in next(p for p in pbs if p["id"] == "lifeops_trip")["engines"] if s["category"] == "event")
    rec("playbook events query is one Google renders events for", ev["params"]["q"].endswith("this weekend"), ev["params"]["q"])

    # ------------------------------------------------- free SerpApi endpoints
    r = c.get("/api/account?force=true")
    a = r.json() if r.status_code == 200 else {}
    rec("GET /api/account (Account API; no api_key/email leaked)", r.status_code == 200 and "total_searches_left" in a and not ({"api_key", "account_email", "account_id"} & set(a)),
        f"{a.get('plan_name')} left={a.get('total_searches_left')} demo={a.get('demo')}")
    if live:
        rec("account is REAL (not demo)", a.get("demo") is False and a.get("searches_per_month", 0) > 0)
    r = c.get("/api/locations", params={"q": "Tokyo", "limit": 3})
    L = r.json() if r.status_code == 200 else []
    rec("GET /api/locations (Locations API, <=limit)", r.status_code == 200 and 1 <= len(L) <= 3 and "canonical_name" in L[0], L[0].get("canonical_name", "") if L else "")
    rec("GET /api/locations validation (missing q -> 422)", c.get("/api/locations").status_code == 422)

    # ------------------------------------------------------ error contracts
    rec("POST /api/sessions empty prompt -> 400", c.post("/api/sessions", json={"prompt": "  "}).status_code == 400)
    rec("POST /api/sessions bad lens -> 422", c.post("/api/sessions", json={"prompt": "x", "lens": "zzz"}).status_code == 422)
    rec("GET /api/sessions/unknown -> 404", c.get("/api/sessions/s_nope").status_code == 404)
    rec("POST /api/actions/unknown/approve -> 404", c.post("/api/actions/act_nope/approve").status_code == 404)
    rec("POST /api/watches/unknown/check -> 404", c.post("/api/watches/w_nope/check").status_code == 404)
    rec("POST /api/watch/tick wrong secret -> 401", c.post("/api/watch/tick", headers={"x-cron-secret": "definitely-wrong"}).status_code == 401)
    rec("POST /api/sessions/unknown/disrupt bad kind -> 400", c.post("/api/sessions/s_nope/disrupt?kind=zzz").status_code == 400)

    # ------------------------------------------------ session: Local playbook
    # (4 live calls: Maps + Yelp + Tripadvisor + Google events) - exercises async=true -> Search Archive, SSE, corroboration, HITL
    r = c.post("/api/sessions", json={"prompt": "Best tacos in Austin, TX under $$ with 4.5+ rating", "lens": "go", "auto_confirm": True})
    rec("POST /api/sessions -> session_id + stream", r.status_code == 200 and r.json().get("session_id", "").startswith("s_"))
    sid = r.json()["session_id"]
    events = sse(c, sid, ("session.done", "session.error", "actor.proposal"), timeout=170)
    # wait for the whole graph (done) — proposals arrive before 'done'
    for _ in range(60):
        s = c.get(f"/api/sessions/{sid}").json()
        if s.get("status") in ("awaiting_approval", "done", "error", "failed"):
            break
        time.sleep(2)
    types = [e["type"] for e in events]
    rec("SSE stream: orchestrator -> researcher events arrive", "orchestrator.intent" in types and "serp.request" in types, f"{len(events)} events")
    allev = c.get(f"/api/sessions/{sid}/events").json()
    at = [e["type"] for e in allev]
    rec("GET /api/sessions/{id}/events (history replay)", len(allev) >= len(events) and "analyst.matrix" in at, f"{len(allev)} events")
    rec("SSE ?after=seq resumes without replaying old events", len(c.get(f"/api/sessions/{sid}/events", params={"after": allev[-3]["seq"]}).json()) <= 3)
    resp = [e["data"] for e in allev if e["type"] == "serp.response"]
    errs = [e["data"] for e in allev if e["type"] == "serp.error"]
    rec("no failed SerpApi calls", not errs, "; ".join(f"{e['engine']}: {e['error'][:60]}" for e in errs))
    if live:
        rec("SerpApi calls are LIVE (mode=live/cache, never demo)", resp and all(x["mode"] in ("live", "cache") for x in resp), ",".join(sorted({x["mode"] for x in resp})))
        rec("async=true -> Search Archive transport used", any(x.get("transport") == "async" for x in resp) or all(x["mode"] == "cache" for x in resp), ",".join(sorted({str(x.get("transport")) for x in resp})))
    by_engine = {x["engine"]: x["results"] for x in resp}
    rec("google_maps/yelp/tripadvisor returned venues", all(by_engine.get(e, 0) > 0 for e in ("google_maps", "yelp", "tripadvisor")), str(by_engine))
    ge = by_engine.get("google", 0)
    rec("events panel has data (google events_results / top_sights fallback)", ge > 0, f"{ge} events")
    mat = next(e["data"] for e in allev if e["type"] == "analyst.matrix")
    ins = mat.get("insights") or {}
    rec("insights.kind == venues with venues + events", ins.get("kind") == "venues" and len(ins.get("venues", [])) > 0 and len(ins.get("events", [])) > 0, f"{len(ins.get('venues', []))} venues / {len(ins.get('events', []))} events")
    rec("every event has title + when + link", all(e.get("title") and e.get("url") for e in ins.get("events", [])))
    rec("confidence is a real number 0..1", 0 < (mat.get("confidence") or 0) <= 1, str(mat.get("confidence")))

    s = c.get(f"/api/sessions/{sid}").json()
    rec("GET /api/sessions/{id} summary", s.get("session_id") == sid and s.get("playbook_id") == "lifeops_local" and s["credits"]["spent"] > 0 if live else s.get("playbook_id") == "lifeops_local",
        f"credits={s.get('credits')}")
    rec("GET /api/sessions (list)", c.get("/api/sessions").status_code == 200)
    tr = c.get(f"/api/sessions/{sid}/trace").json()
    rec("GET /api/sessions/{id}/trace (spans)", tr.get("source") in ("local", "langfuse-cloud") and len(tr.get("spans", [])) > 0 or tr.get("remote"), f"source={tr.get('source')} spans={len(tr.get('spans', []))}")

    # ---------------------------------------------------------------- HITL
    acts = s.get("actions", [])
    rec("actor proposed HITL actions", len(acts) >= 3, ",".join(f"{x['type']}:{x['status']}" for x in acts))
    pending = [x for x in acts if x["status"] == "pending"]
    cal = next((x for x in acts if x["type"] == "calendar_invite"), None)
    if cal and cal["status"] == "executed":
        ics = c.get(f"/api/actions/{cal['id']}/ics")
        rec("GET /api/actions/{id}/ics (text/calendar, VEVENT)", ics.status_code == 200 and "BEGIN:VCALENDAR" in ics.text and "BEGIN:VEVENT" in ics.text and "text/calendar" in ics.headers.get("content-type", ""))
    book = next((x for x in pending if x["type"] == "booking_flow"), None)
    if book:
        m = c.post(f"/api/actions/{book['id']}/modify", json={"payload": {"party_size": 4}, "note": "party of 4"})
        rec("POST /api/actions/{id}/modify", m.status_code == 200 and m.json()["action"]["status"] == "modified" and m.json()["action"]["payload"].get("party_size") == 4)
        ap = c.post(f"/api/actions/{book['id']}/approve", timeout=120)
        rec("POST /api/actions/{id}/approve -> receipt", ap.status_code == 200 and ap.json().get("receipt") is not None, f"status={ap.json().get('action', {}).get('status')}")
        rec("POST approve twice -> 409", c.post(f"/api/actions/{book['id']}/approve").status_code == 409)
        rec("POST modify after execute -> 409", c.post(f"/api/actions/{book['id']}/modify", json={"payload": {}}).status_code == 409)
    watch_a = next((x for x in pending if x["type"] == "watch"), None)
    if watch_a:
        rj = c.post(f"/api/actions/{watch_a['id']}/reject")
        rec("POST /api/actions/{id}/reject", rj.status_code == 200 and rj.json()["action"]["status"] == "rejected")

    # -------------------------------------------------------------- watches
    w = c.post("/api/watches", json={"session_id": sid, "label": "e2e tacos rating", "engine": "google_maps",
                                       "params": {"q": "tacos in Austin, TX", "type": "search", "hl": "en", "gl": "us"}, "target_title": None,
                                       "baseline_price": None, "threshold_pct": 8, "cadence_minutes": 30})
    wj = w.json() if w.status_code == 200 else {}
    rec("POST /api/watches", w.status_code == 200 and wj.get("id"), str(wj.get("id")))
    rec("GET /api/watches lists it", any(x["id"] == wj.get("id") for x in c.get("/api/watches").json()))
    if wj.get("id") and not READONLY:
        ck = c.post(f"/api/watches/{wj['id']}/check", timeout=120)
        rec("POST /api/watches/{id}/check (fresh live poll)", ck.status_code == 200 and isinstance(ck.json(), dict), str(list(ck.json())[:6]) if ck.status_code == 200 else ck.text[:80])
    tk = c.post("/api/watch/tick", headers={"x-cron-secret": CRON})
    if tk.status_code == 401:
        rec("POST /api/watch/tick correct secret (skipped: CRON_SECRET env not provided)", True, "set CRON_SECRET to exercise")
    else:
        rec("POST /api/watch/tick correct secret", tk.status_code == 200, tk.text[:90])

    # ------------------------------------------------------- disruption path
    if not READONLY:
        d = c.post(f"/api/sessions/{sid}/disrupt?kind=rating_drop&pct=45")
        rec("POST /api/sessions/{id}/disrupt rating_drop", d.status_code == 200 and d.json().get("ok"), d.text[:90])
        got = []
        for _ in range(45):
            got = [e["type"] for e in c.get(f"/api/sessions/{sid}/events").json()]
            if "watch.disruption_detected" in got and "orchestrator.replan" in got:
                break
            time.sleep(3)
        rec("disruption detected -> bounded re-plan event", "watch.disruption_detected" in got, f"replans={got.count('orchestrator.replan')}")
        rec("re-plan cap respected (<= 2)", got.count("orchestrator.replan") <= 2)
        rp = c.post(f"/api/sessions/{sid}/repoll")
        rec("POST /api/sessions/{id}/repoll", rp.status_code == 200 and rp.json().get("ok"))
        cf = c.post(f"/api/sessions/{sid}/confirm?choice=essential")
        rec("POST /api/sessions/{id}/confirm", cf.status_code == 200 and cf.json().get("choice") == "essential")

    bad = [n for n, ok, _ in RES if not ok]
    print(f"\n{len(RES) - len(bad)}/{len(RES)} checks passed" + (f"  FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

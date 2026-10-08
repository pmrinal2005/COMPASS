"""End-to-end smoke test (Demo Mode, zero credits, no network):
all 7 playbooks -> HITL approve -> metric-aware watches -> cron tick auth -> live disruption
(price_spike / rating_drop / rank_drop / unavailable) -> bounded re-plan -> session persistence
(snapshot + rehydrate) -> Account / Locations / Playbook-library endpoints -> SerpApi docs compliance.

Usage: cd backend && PYTHONPATH=. python scripts/smoke_test.py"""
import asyncio
import os

os.environ.setdefault("DEMO_MODE", "true")
os.environ["CRON_SECRET"] = "smoke"
os.environ["PLAYWRIGHT_ENABLED"] = "false"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import graph as G  # noqa: E402
from app.main import app  # noqa: E402
from app.playbooks import PLAYBOOKS  # noqa: E402
from app.services.events import bus  # noqa: E402
from app.services.serpapi import SerpApiClient, classify_error  # noqa: E402

PROMPTS = [
    ("Plan a 4-day Tokyo trip under $1,200, flights + hotel", "go", "lifeops_trip"),
    ("Source 3 reliable suppliers for bulk Bluetooth earbuds, compare price/MOQ/reviews", "pro", "pro_supplier"),
    ("Find the best deal on Sony WH-1000XM5 headphones", "go", "lifeops_deals"),
    ("Remote senior React developer jobs", "go", "career_jobs"),
    ("Prior art for solid-state battery dendrite suppression", "pro", "research_ip"),
    ("Best tacos in Austin, TX under $$ with 4.5+ rating", "go", "lifeops_local"),
    ("Track SEO visibility of serpapi.com for \"google search api\" across search engines", "pro", "research_seo"),
]

# Documented parameters per engine: snapshot parsed from serpapi.com itself (refresh with `python scripts/docs_sync.py`).
import json  # noqa: E402
from pathlib import Path  # noqa: E402

_SNAP = json.loads((Path(__file__).resolve().parents[1] / "app" / "docs" / "serpapi_params.json").read_text())["engines"]
DOC_PARAMS = {e: " ".join(k for k in p if k not in ("engine", "api_key")) for e, p in _SNAP.items()}
REQUIRED = {e: {k for k, v in p.items() if v} - {"engine", "api_key"} for e, p in _SNAP.items()}
META = {"output", "device", "no_cache", "async", "zero_trace", "json_restrictor"}
DEPRECATED = {"google_events"}      # docs: "deprecated and no longer accepts new requests" (HTTP 400 Unsupported search engine)


def check_docs_compliance() -> None:
    """Static contract checks against the documented SerpApi parameters + transport rules."""
    n = 0
    for pid, pb in PLAYBOOKS.items():
        for grp in ("engines", "fallback_engines"):
            for sp in pb.get(grp, []):
                e, ps = sp["engine"], set(sp["params"])
                assert e in DOC_PARAMS, f"{pid}: engine {e} is not a documented SerpApi engine"
                assert e not in DEPRECATED, f"{pid}: engine {e} is deprecated upstream"
                assert not (ps - set(DOC_PARAMS[e].split()) - META), f"{pid}/{e}: undocumented params {ps - set(DOC_PARAMS[e].split())}"
                assert REQUIRED.get(e, set()) <= ps, f"{pid}/{e}: missing required {REQUIRED[e] - ps}"
                n += 1
    c = SerpApiClient()
    c.s = c.s.model_copy(update={"serpapi_key": "k", "serpapi_zero_trace": False})
    fresh, asyn = c.build_query("google", {"q": "x"}, fresh=True, use_async=True), c.build_query("google", {"q": "x"}, fresh=False, use_async=True)
    assert "no_cache" in fresh and "async" not in fresh, "async and no_cache must never be combined (docs)"
    assert asyn.get("async") == "true" and "no_cache" not in asyn and asyn["output"] == "json"
    assert classify_error(429, "Your account has run out of searches.").kind == "out_of_searches"
    assert classify_error(429, "Too many requests per hour").retryable and classify_error(410, "gone").kind == "gone"
    assert classify_error(401, "Invalid API key").kind == "auth" and classify_error(503, "x").retryable
    print(f"ok  SerpApi docs compliance: {n} playbook calls use only documented params; async XOR no_cache; 410/429/401/503 mapping")


async def main() -> None:
    check_docs_compliance()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t", timeout=120) as c:
        assert (await c.get("/api/health")).json()["ok"]
        res: dict[str, dict] = {}
        for prompt, lens, expected in PROMPTS:
            r = (await c.post("/api/sessions/run", json={"prompt": prompt, "lens": lens})).json()
            assert r["playbook_id"] == expected, (prompt, r["playbook_id"])
            assert r["analysis"]["matrix"]["rows"], expected
            assert r["actions"], expected
            assert r["replans"] <= 2
            assert r["analysis"].get("insights") is not None or expected not in ("lifeops_local", "research_seo"), expected
            res[expected] = r
            print(f"ok  {expected:14s} conf={r['confidence']:.2f} credits={r['credits']['spent']} actions={len(r['actions'])} "
                  f"top={r['analysis']['matrix']['rows'][0]['title'][:34]}")

        # ---- entity playbooks are cross-source verified
        loc = res["lifeops_local"]["analysis"]["insights"]
        assert loc["kind"] == "venues" and loc["venues"] and all(len(v["platforms"]) >= 2 for v in loc["venues"][:3]), "venues must be seen on >=2 platforms"
        seo = res["research_seo"]["analysis"]["insights"]
        assert seo["kind"] == "seo" and len(seo["grid"]) >= 5 and seo["ai"], "SEO grid must span >=5 engines + AI citations"
        print(f"ok  cross-platform consensus ({len(loc['venues'][0]['platforms'])} platforms) + SEO grid ({len(seo['grid'])} engines, {len(seo['ai'])} AI)")

        # ---- HITL + metric-aware watches
        trip = res["lifeops_trip"]
        booking = next(a for a in trip["actions"] if a["type"] == "booking_flow")
        ap = (await c.post(f"/api/actions/{booking['id']}/approve")).json()
        assert ap["action"]["status"] == "executed" and ap["receipt"]["confirmation"]
        for pid, metric in (("lifeops_trip", "price"), ("lifeops_local", "rating"), ("research_seo", "position")):
            watch = next(a for a in res[pid]["actions"] if a["type"] == "watch")
            w = (await c.post(f"/api/actions/{watch['id']}/approve")).json()
            assert w["action"]["status"] == "executed" and w["receipt"]["watch"]["metric"] == metric, (pid, w)
        assert (await c.post("/api/watch/tick")).status_code == 401
        tick = (await c.post("/api/watch/tick?force=true", headers={"x-cron-secret": "smoke"})).json()
        assert tick["checked"] >= 3 and not any("error" in r for r in tick["results"]), tick
        print(f"ok  HITL approve + price/rating/position watches + cron tick ({tick['checked']} watches)")

        # ---- disruptions -> bounded re-plan, one per failure mode
        for key, kind in (("lifeops_trip", "price_spike"), ("lifeops_local", "rating_drop"), ("research_seo", "rank_drop"), ("lifeops_deals", "unavailable")):
            sid = res[key]["session_id"]
            before = res[key]["analysis"]["matrix"]["rows"][0]["title"]
            assert (await c.post(f"/api/sessions/{sid}/disrupt?kind={kind}&pct=45")).json()["ok"]
            for _ in range(60):
                await asyncio.sleep(0.5)
                s = (await c.get(f"/api/sessions/{sid}")).json()
                if s["replans"] >= 1 and s["status"] == "awaiting_approval":
                    break
            assert s["replans"] >= 1 and s["replans"] <= 2, f"{key}: disruption should trigger a bounded re-plan"
            print(f"ok  disruption {kind:12s} {key:13s} -> re-plan x{s['replans']} #1: {before[:22]!r} -> {s['analysis']['matrix']['rows'][0]['title'][:26]!r}"
                  f" anomalies={len(s['analysis']['anomalies'])}")
        assert (await c.post(f"/api/sessions/{res['lifeops_trip']['session_id']}/disrupt?kind=bogus")).status_code == 400

        # ---- persistence: drop the in-memory runtime (== Render restart) and resume from the snapshot
        sid = res["research_seo"]["session_id"]
        n_events = len(bus.history(sid))
        G.RUNTIME.pop(sid)
        bus._history.pop(sid, None)
        s = (await c.get(f"/api/sessions/{sid}")).json()
        assert s["playbook_id"] == "research_seo" and s["analysis"]["insights"]["kind"] == "seo"
        assert len((await c.get(f"/api/sessions/{sid}/events")).json()) >= n_events - 2
        pend = next(a for a in s["actions"] if a["status"] == "pending" and a["type"] == "watch")
        assert (await c.post(f"/api/actions/{pend['id']}/approve")).json()["action"]["status"] == "executed"
        print(f"ok  persistence: session rehydrated from snapshot ({n_events} events, {len(s['actions'])} actions) and HITL still works")

        # ---- ancillary SerpApi-docs endpoints
        acc = (await c.get("/api/account")).json()
        assert "plan_name" in acc and "api_key" not in acc and "account_email" not in acc
        locs = (await c.get("/api/locations?q=Austin&limit=3")).json()
        assert locs and "canonical_name" in locs[0]
        lib = (await c.get("/api/playbooks")).json()
        assert len(lib) == len(PLAYBOOKS) == 7 and all(p["engine_list"] for p in lib)
        print(f"ok  /api/account (secrets stripped), /api/locations, /api/playbooks ({len(lib)} playbooks)")

        # ---- frontend contract: the bundled offline library + recordings must match what this backend serves
        import json as _json
        from pathlib import Path as _P
        demo = _P(__file__).resolve().parents[2] / "frontend" / "lib" / "demo"
        bundled = {p["id"]: p for p in _json.loads((demo / "playbooks.json").read_text())}
        assert set(bundled) == {p["id"] for p in lib}, "frontend/lib/demo/playbooks.json is stale -> run scripts/record_demo.py"
        assert all(bundled[p["id"]]["engine_list"] == p["engine_list"] for p in lib)
        rec = _json.loads((demo / "recordings.json").read_text())
        assert {"tokyo", "tacos", "seo", "earbuds", "headphones", "jobs", "prior_art"} == set(rec), "7 offline scenarios expected"
        assert all(r["events"] for r in rec.values()) and sum(1 for r in rec.values() if r.get("disruption")) == 4
        print(f"ok  frontend contract: bundled library ({len(bundled)} playbooks) + {len(rec)} recorded scenarios (4 with disruption) match the backend")
    print("ALL SMOKE TESTS PASSED")


asyncio.run(main())

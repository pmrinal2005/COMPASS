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

# Documented parameter names per engine (https://serpapi.com/<engine>-api) - every playbook call must stay inside this set.
DOC_PARAMS = {
    "yelp": "find_desc find_loc l yelp_domain cflt sortby attrs start",
    "tripadvisor": "q lat lon tripadvisor_domain ssrc offset limit",
    "google_events": "q location uule gl hl start htichips",
    "airbnb": "q map_bounds airbnb_domain currency check_in_date check_out_date adults children infants pets room_type min_price max_price bedrooms beds "
              "bathrooms property_types amenities accessibility_features host_languages instant_book self_check_in guest_favorite luxe page",
    "bing": "q location lat lon mkt cc first filters device", "duckduckgo": "q kl search_assist safe df start m",
    "yahoo": "p yahoo_domain vc vl b vm vs vf fr2 d device", "yandex": "text yandex_domain lang lr family_mode fix_typo groups_on_page sort_mode period p",
    "baidu": "q ct pn rn gpc q5 q6 bs oq f device", "naver": "query start page num where sort_by period device",
    "google_ai_mode": "q location uule gl hl continuable subsequent_request_token image_url device", "google_ai_overview": "page_token",
    "google_flights": "departure_id arrival_id gl hl currency type outbound_date return_date travel_class multi_city_json show_hidden exclude_basic deep_search adults "
                      "children infants_in_seat infants_on_lap sort_by stops exclude_airlines include_airlines bags max_price outbound_times return_times emissions "
                      "layover_duration exclude_conns max_duration selected_flights_json departure_token booking_token",
    "google_hotels": "q gl hl currency check_in_date check_out_date adults children children_ages sort_by min_price max_price property_types amenities rating brands "
                     "hotel_class free_cancellation special_offers eco_certified vacation_rentals bedrooms bathrooms next_page_token property_token",
    "google_maps": "q ll location lat lon z m nearby google_domain hl gl data place_id data_cid type min_price max_price min_rating open_state open_on_day open_at_hour start",
    "google_flights_autocomplete": "q gl hl exclude_regions", "google_jobs": "q location uule google_domain gl hl next_page_token chips lrad ltype uds",
    "google_finance": "q hl window",
    "google_shopping": "q location uule google_domain gl hl shoprs min_price max_price sort_by free_shipping on_sale small_business safe start device",
    "google_shopping_light": "q location uule google_domain gl hl shoprs min_price max_price sort_by free_shipping on_sale small_business safe start device",
    "amazon": "k amazon_domain language delivery_zip shipping_location s node rh dc page device",
    "walmart": "query walmart_domain sort soft_sort cat_id facet store_id min_price max_price spelling nd_en page device include_filters",
    "ebay": "_nkw ebay_domain _salic _pgn _ipg _blrs show_only buying_format _sasl _saslop popular_filters _udlo _udhi _sop _dmd category_id _stpos",
    "google_trends": "q hl geo region data_type tz cat gprop date csv include_low_search_volume",
    "google_scholar": "q cites as_ylo as_yhi scisbd cluster hl lr start num as_sdt safe filter as_vis as_rr",
    "google_patents": "q page num sort clustered dups patents scholar before after inventor assignee country language status type litigation",
    "google_news": "q gl hl topic_token kgmid publication_token section_token story_token so",
    "google": "q location uule lat lon radius ludocid lsig kgmid si ibp uds color_scheme google_domain gl hl cr lr tbs safe nfpr filter tbm start device",
}
REQUIRED = {"google_hotels": {"q", "check_in_date", "check_out_date"}, "google_maps": {"type"}, "yelp": {"find_loc"}, "tripadvisor": {"q"},
            "bing": {"q"}, "duckduckgo": {"q"}, "yahoo": {"p"}, "yandex": {"text"}, "baidu": {"q"}, "naver": {"query"}, "google_ai_mode": {"q"},
            "google_events": {"q"}, "google_jobs": {"q"}, "google_finance": {"q"}}


def check_docs_compliance() -> None:
    """Static contract checks against the documented SerpApi parameters + transport rules."""
    n = 0
    for pid, pb in PLAYBOOKS.items():
        for grp in ("engines", "fallback_engines"):
            for sp in pb.get(grp, []):
                e, ps = sp["engine"], set(sp["params"])
                assert e in DOC_PARAMS, f"{pid}: engine {e} is not a documented SerpApi engine"
                assert not (ps - set(DOC_PARAMS[e].split())), f"{pid}/{e}: undocumented params {ps - set(DOC_PARAMS[e].split())}"
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
    print("ALL SMOKE TESTS PASSED")


asyncio.run(main())

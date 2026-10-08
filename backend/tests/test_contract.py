"""SerpApi contract tests (no network, 0 credits).

Three layers, all anchored to the *documentation* rather than to our own demo data:
  1. every Playbook call only uses parameters documented on serpapi.com (snapshot: app/docs/serpapi_params.json, refreshed by scripts/docs_sync.py)
  2. every normalizer parses the real sample payload that serpapi.com publishes for that engine (tests/fixtures/<engine>.json)
  3. the transport honours the documented async / Search-Archive / error-code contract (httpx.MockTransport)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.playbooks import PLAYBOOKS
from app.services.entities import price_level, serp_domain
from app.services.normalize import normalize
from app.services.serpapi import CreditMeter, SerpApiClient, SerpApiError, classify_error

HERE = Path(__file__).parent
FIX = HERE / "fixtures"
DOCS = json.loads((HERE.parent / "app" / "docs" / "serpapi_params.json").read_text())["engines"]
META_PARAMS = {"engine", "api_key", "output", "device", "no_cache", "async", "zero_trace", "json_restrictor"}
DEPRECATED_ENGINES = {"google_events"}      # docs: "has been deprecated and no longer accepts new requests"


def fx(engine: str) -> dict:
    return json.loads((FIX / f"{engine}.json").read_text())


# ------------------------------------------------------------------ 1. playbooks vs docs
def _calls():
    for pid, pb in PLAYBOOKS.items():
        for grp in ("engines", "fallback_engines"):
            for i, sp in enumerate(pb.get(grp, [])):
                yield pytest.param(pid, grp, sp, id=f"{pid}:{grp}[{i}]:{sp['engine']}")


@pytest.mark.parametrize("pid,grp,sp", list(_calls()))
def test_playbook_call_matches_documented_params(pid, grp, sp):
    e = sp["engine"]
    assert e in DOCS, f"{e} is not a documented SerpApi engine page"
    assert e not in DEPRECATED_ENGINES, f"{e} is deprecated upstream and rejects requests (HTTP 400)"
    given, doc = set(sp["params"]), set(DOCS[e])
    assert not (given - doc - META_PARAMS), f"undocumented params for {e}: {given - doc - META_PARAMS}"
    required = {k for k, v in DOCS[e].items() if v} - {"engine", "api_key"}
    assert required <= given, f"missing documented required params for {e}: {required - given}"


def test_every_playbook_engine_has_a_documented_sample_or_is_known():
    known_without_sample = {"google_ai_overview"}      # needs a page_token from a prior google call
    for pb in PLAYBOOKS.values():
        for sp in pb["engines"] + pb.get("fallback_engines", []):
            assert (FIX / f"{sp['engine']}.json").exists() or sp["engine"] in known_without_sample, sp["engine"]


# ------------------------------------------------------------------ 2. normalizers vs real docs samples
CATEGORY = {"google_maps": "venue", "yelp": "venue", "google": "serp", "bing": "serp", "duckduckgo": "serp", "yahoo": "serp", "yandex": "serp",
            "baidu": "serp", "naver": "serp", "google_ai_mode": "ai_citation", "google_shopping": "product", "google_shopping_light": "product"}
EXPECT_MIN = {"airbnb": 5, "amazon": 10, "baidu": 3, "bing": 1, "duckduckgo": 5, "ebay": 10, "google": 5, "google_ai_mode": 5, "google_flights": 3,
              "google_hotels": 5, "google_jobs": 3, "google_maps": 5, "google_news": 3, "google_patents": 3, "google_scholar": 3, "google_shopping": 10,
              "google_shopping_light": 10, "naver": 5, "walmart": 10, "yahoo": 3, "yandex": 3, "yelp": 5}


@pytest.mark.parametrize("engine,minimum", sorted(EXPECT_MIN.items()))
def test_normalizer_parses_docs_sample(engine, minimum):
    d = fx(engine)
    cands, _ = normalize(engine, d, CATEGORY.get(engine, "generic"), d.get("search_parameters"))
    assert len(cands) >= minimum, f"{engine}: parsed {len(cands)} candidates from the official docs sample"
    assert all(c.title is not None for c in cands)


def test_finance_trends_context_extracted():
    assert normalize("google_finance", fx("google_finance"), "generic", {})[1]["fx"]["rate"]
    assert len(normalize("google_trends", fx("google_trends"), "generic", {})[1]["trend"]) > 5


def test_flights_context_and_fields():
    d = fx("google_flights")
    cands, ctx = normalize("google_flights", d, "flight", d["search_parameters"])
    assert ctx["price_insights"]["lowest_price"] and all(c.price and c.duration_min for c in cands)


def test_tripadvisor_documented_place_types():
    """Docs: place_type is one of GEO, ACCOMMODATION, AIRLINE, ATTRACTION, ATTRACTION_PRODUCT, EATERY, VACATION_RENTAL.
    Restaurants are `EATERY` - the previous `RESTAURANT` filter silently dropped every real Tripadvisor restaurant."""
    d = fx("tripadvisor")
    eateries = [p for p in d["places"] if p["place_type"] == "EATERY"]
    assert eateries, "docs sample should contain at least one EATERY row"
    out = normalize("tripadvisor", d, "venue", d["search_parameters"])[0]
    assert sorted(c.title for c in out) == sorted(p["title"] for p in eateries)
    assert all(c.category == "venue" and c.source == "Tripadvisor" for c in out)
    other = {p["place_type"] for p in d["places"]} - {"EATERY"}
    assert {"GEO", "ACCOMMODATION"} <= other                      # non-restaurants are never returned as venues
    allp = normalize("tripadvisor", d, "generic", d["search_parameters"])[0]
    assert len(allp) > len(out)                                    # ...but are kept for non-venue use


def test_google_maps_price_bands_are_understood():
    """Google Maps documents prices as bands ($1-10, $10-20 ...), Yelp as symbols ($..$$$$)."""
    d = fx("google_maps")
    levels = {c.attributes["price_level"] for c in normalize("google_maps", d, "venue", d["search_parameters"])[0]}
    assert levels & {1, 2}, levels
    assert [price_level(v) for v in ("$", "$$", "$$$$", "$1–10", "$10–20", "$30–50", "$100+", None, "€€")] == [1, 2, 4, 1, 2, 3, 4, None, None]
    y = fx("yelp")
    assert any(c.attributes["price_level"] for c in normalize("yelp", y, "venue", y["search_parameters"])[0])


def test_events_results_from_google_search_api_and_legacy_shape():
    """google_events is deprecated: events come from `events_results` of engine=google. `venue` may be a str or an object."""
    legacy = fx("google_events")
    c1, _ = normalize("google", legacy, "event", {"q": "Events in Austin"})
    assert len(c1) >= 5 and all(c.category == "event" for c in c1)
    modern = {"events_results": [{"title": "Austin, TX", "date": {"start_date": "Aug 30", "when": "Sat 6:00 PM"}, "venue": "ACL Live",
                                   "price": "$158", "extracted_price": 158, "link": "https://x.test/e", "ticket_info": [{"source": "AXS", "link": "u"}]}]}
    c2, _ = normalize("google", modern, "event", {"q": "Events in Austin"})
    assert c2[0].attributes["venue"] == "ACL Live" and c2[0].attributes["tickets"] == ["AXS"]
    assert normalize("google", legacy, "serp", {})[0] == [] or all(c.category == "serp" for c in normalize("google", legacy, "serp", {})[0])


def test_serp_rows_and_domains_from_docs_samples():
    for e in ("google", "bing", "duckduckgo", "yahoo", "yandex", "baidu", "naver"):
        d = fx(e)
        rows, _ = normalize(e, d, "serp", d.get("search_parameters"))
        assert rows and all(r.attributes["position"] >= 1 for r in rows)
        assert sum(1 for r in rows if r.attributes["domain"]) >= max(1, len(rows) // 2), f"{e}: domains not extracted"
    assert serp_domain({"link": "https://www.bing.com/ck/a?x=1", "displayed_link": "https://www.tripadvisor.ca › Restaurants"}) == "tripadvisor.ca"


def test_naver_where_web_returns_organic_results():
    """Verified against the live API: `where=web` -> organic_results[]; default `where=nexearch` -> web_results[]. Both must normalise."""
    row = {"position": 1, "title": "Coffee - Wikipedia", "link": "https://en.wikipedia.org/wiki/Coffee", "displayed_link": "en.wikipedia.org", "snippet": "x"}
    a, _ = normalize("naver", {"organic_results": [row]}, "serp", {"query": "Coffee", "where": "web"})
    b, _ = normalize("naver", {"web_results": [row]}, "serp", {"query": "Coffee"})
    assert len(a) == len(b) == 1 and a[0].attributes["domain"] == b[0].attributes["domain"] == "wikipedia.org"


def test_ai_mode_references_become_citations():
    d = fx("google_ai_mode")
    c, ctx = normalize("google_ai_mode", d, "ai_citation", {})
    assert len(c) >= 10 and all(x.category == "ai_citation" and x.attributes["domain"] for x in c)
    assert ctx["ai_text"]["google_ai_mode"]


def test_flights_autocomplete_documented_shape():
    sug = fx("google_flights_autocomplete")["suggestions"]
    assert any(a.get("id") for s in sug for a in (s.get("airports") or [])), "suggestions[].airports[].id is the IATA code we resolve with"


# ------------------------------------------------------------------ 3. transport contract (mocked SerpApi)
def make_client(handler, **overrides) -> SerpApiClient:
    c = SerpApiClient()
    c.s = c.s.model_copy(update={"serpapi_key": "test-key", "demo_mode": False, "serp_poll_interval": 0.01, "serp_max_retries": 2, **overrides})
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://serpapi.com")
    return c


def run_search(c: SerpApiClient, engine="bing", params=None, fresh=False):
    from app.services.cache import cache
    cache._mem.clear() if hasattr(cache, "_mem") else None
    async def go():
        return await c.search(engine, params or {"q": f"coffee-{id(c)}-{fresh}"}, session_id="t", call_id="c1", sem=asyncio.Semaphore(2),
                              meter=CreditMeter(10), fresh=fresh)
    return asyncio.run(go())


def test_async_flow_submits_then_polls_search_archive():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.url.path, dict(req.url.params)))
        if req.url.path == "/search.json":
            return httpx.Response(200, json={"search_metadata": {"id": "abc123", "status": "Queued"}})
        n = sum(1 for p, _ in seen if p.startswith("/searches/"))
        status = "Processing" if n < 2 else "Success"
        return httpx.Response(200, json={"search_metadata": {"id": "abc123", "status": status}, "organic_results": [{"position": 1, "title": "x", "link": "https://a.test"}]})

    res = run_search(make_client(handler))
    assert res["transport"] == "async" and res["data"]["search_metadata"]["status"] == "Success"
    submit = seen[0][1]
    assert submit["async"] == "true" and "no_cache" not in submit and submit["output"] == "json" and submit["api_key"] == "test-key"
    assert seen[1][0] == "/searches/abc123.json" and seen[1][1] == {"api_key": "test-key"}
    assert len([p for p, _ in seen if p.startswith("/searches/")]) == 2          # polled until Success


def test_fresh_poll_is_blocking_no_cache_never_async():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json={"search_metadata": {"id": "z", "status": "Success"}, "organic_results": []})

    res = run_search(make_client(handler), fresh=True)
    assert res["transport"] == "sync" and len(seen) == 1
    assert seen[0].get("no_cache") == "true" and "async" not in seen[0]            # documented: async and no_cache can't be combined


def test_zero_trace_forces_blocking_mode():
    seen = []

    def handler(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json={"search_metadata": {"id": "z", "status": "Success"}})

    res = run_search(make_client(handler, serpapi_zero_trace=True))
    assert res["transport"] == "sync" and seen[0]["zero_trace"] == "true" and "async" not in seen[0]


@pytest.mark.parametrize("status,msg,kind,retryable", [
    (401, "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key", "auth", False),
    (403, "forbidden", "auth", False),
    (410, "Gone", "gone", False),
    (429, "Your account has run out of searches.", "out_of_searches", False),
    (429, "Your hourly throughput limit has been exceeded.", "throttled", True),
    (500, "Internal error", "error", True),
    (503, "Service unavailable", "error", True),
    (400, "Unsupported `google_events` search engine.", "bad_request", False),
])
def test_documented_error_codes(status, msg, kind, retryable):
    e = classify_error(status, msg)
    assert (e.kind, e.retryable) == (kind, retryable)


def test_retry_on_throttle_then_success_and_no_retry_on_401():
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": "Your hourly throughput limit has been exceeded."})
        return httpx.Response(200, json={"search_metadata": {"id": "ok", "status": "Success"}, "organic_results": []})

    c = make_client(flaky, serp_async=False)
    import app.services.serpapi as mod
    orig = asyncio.sleep
    async def fast(_): return None
    mod.asyncio.sleep = fast
    try:
        assert run_search(c)["data"]["search_metadata"]["status"] == "Success" and calls["n"] == 3
        bad = {"n": 0}
        def unauth(req):
            bad["n"] += 1
            return httpx.Response(401, json={"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"})
        with pytest.raises(SerpApiError) as ei:
            run_search(make_client(unauth, serp_async=False))
        assert ei.value.kind == "auth" and bad["n"] == 1
    finally:
        mod.asyncio.sleep = orig


def test_success_with_error_key_is_an_empty_result_not_a_failure():
    def handler(req):
        return httpx.Response(200, json={"search_metadata": {"id": "e", "status": "Success"}, "error": "Google hasn't returned any results for this query."})
    res = run_search(make_client(handler, serp_async=False))
    assert res["data"]["error"].startswith("Google hasn't")


def test_async_error_status_raises():
    def handler(req):
        if req.url.path == "/search.json":
            return httpx.Response(200, json={"search_metadata": {"id": "q1", "status": "Queued"}})
        return httpx.Response(200, json={"search_metadata": {"id": "q1", "status": "Error"}, "error": "boom"})
    with pytest.raises(SerpApiError):
        run_search(make_client(handler))


def test_account_api_strips_secrets():
    raw = {"account_id": "1", "api_key": "secret", "account_email": "a@b.c", "account_status": "Active", "plan_name": "Free Plan",
           "plan_searches_left": 240, "searches_per_month": 250, "total_searches_left": 240, "this_month_usage": 10,
           "this_hour_searches": 0, "last_hour_searches": 1, "account_rate_limit_per_hour": 250, "extra_credits": 0}

    def handler(req):
        assert req.url.path == "/account.json" and req.url.params["api_key"] == "test-key"
        return httpx.Response(200, json=raw)

    out = asyncio.run(make_client(handler).account(force=True))
    assert out["total_searches_left"] == 240 and "api_key" not in out and "account_email" not in out and "account_id" not in out


def test_locations_api_needs_no_key():
    def handler(req):
        assert req.url.path == "/locations.json" and "api_key" not in req.url.params
        return httpx.Response(200, json=[{"name": "Austin", "canonical_name": "Austin,Texas,United States"}])
    assert asyncio.run(make_client(handler).locations("Austin", 50))[0]["name"] == "Austin"    # limit is clamped to the documented max (10)

"""Regression suite for the two production bug reports (no network, 0 credits):

BUG 1 — intent misrouting: "latest news in india" / "trending songs in india" must reach the
        news / media playbooks (never local discovery), with dynamic per-domain API selection.
BUG 2 — stale YouTube results: recency-flagged queries ("latest <creator> videos") must bypass
        the dedupe cache, drill into the creator channel, and rank by freshness over raw views.

Plus coverage for the second-wave engines (youtube_channel, bing_news, duckduckgo_news,
google_images, bing_videos, google_flights_deals, google_play, apple_app_store, finance quote).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.agents import orchestrator as o
from app.models import Candidate
from app.playbooks import PLAYBOOKS
from app.services import intent as I
from app.services.cache import call_fingerprint, ttl_for
from app.services.normalize import _days_ago, normalize

FIX = Path(__file__).parent / "fixtures"


def _fx(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


def _classify(prompt: str):
    return asyncio.run(o.classify(prompt, "go"))


# ------------------------------------------------------- 1. prompt analysis
@pytest.mark.parametrize("prompt,recency,strong", [
    ("latest Techno Gamerz videos", True, True),
    ("breaking news on the election", True, True),
    ("Apple stock price today", True, True),
    ("recent uploads from mkbhd", True, False),
    ("trending songs in india", True, False),
    ("Best tacos in Austin", False, False),
    ("Find the best deal on headphones", False, False),
])
def test_recency_detection(prompt, recency, strong):
    a = I.analyze_prompt(prompt)
    assert a.recency is recency and a.fresh_strong is strong, prompt


@pytest.mark.parametrize("prompt,market", [
    ("latest news in india", "in"), ("trending songs in india", "in"), ("US stocks today", "us"),
    ("news in the united kingdom", "gb"), ("flights from Delhi to NYC", None), ("best tacos", None),
])
def test_market_extraction(prompt, market):
    assert I.analyze_prompt(prompt).market == market, prompt


@pytest.mark.parametrize("prompt,entity,kind", [
    ("latest Techno Gamerz videos", "Techno Gamerz", "creator"),
    ("new MrBeast uploads", "MrBeast", "creator"),
    ("videos by @mkbhd", "mkbhd", "creator"),
    ("trending songs in india", None, None),          # generic topic, NOT a creator entity
    ("AAPL stock price", "AAPL:NASDAQ", "ticker"),
    ("Tesla shares news", "TSLA:NASDAQ", "ticker"),
])
def test_entity_extraction(prompt, entity, kind):
    a = I.analyze_prompt(prompt)
    assert (a.entity, a.entity_kind) == (entity, kind), prompt


@pytest.mark.parametrize("prompt,kind", [
    ("trending songs in india", "music"), ("latest Techno Gamerz videos", "video"),
    ("sunset wallpaper images", "image"), ("best meditation apps", "app"), ("latest news in india", "news"),
])
def test_media_kind(prompt, kind):
    assert I.analyze_prompt(prompt).media_kind == kind, prompt


# ------------------------------------------------- 2. strong/weak routing + priors
def test_strong_hits_dominate_routing():
    pid, scores = _classify("latest news in india")
    assert pid == "news_trends" and scores[0]["strong_hits"] >= 1
    pid, scores = _classify("latest Techno Gamerz videos")
    assert pid == "media_video" and scores[0]["strong_hits"] >= 1
    # entity-level creator query is NOT mapped to generic music trends
    assert scores[0].get("analysis", {}).get("entity") == "Techno Gamerz"


def test_local_discovery_prior_blocks_weak_only_routes():
    # "rated"-style weak words alone must not win a restaurant route
    pid, _ = _classify("highly rated news coverage of the election")
    assert pid != "lifeops_local"
    pid, scores = _classify("Best tacos in Austin, TX under $$ with 4.5+ rating")
    assert pid == "lifeops_local" and scores[0]["strong_hits"] >= 1


def test_every_playbook_has_strong_keywords():
    for pid, pb in PLAYBOOKS.items():
        assert pb.get("strong_keywords"), f"{pid} has no strong_keywords"


@pytest.mark.parametrize("prompt,pid", [
    ("latest news in india", "news_trends"),
    ("latest Techno Gamerz videos", "media_video"),
    ("trending songs in india", "media_video"),
    ("sunset wallpaper 4k", "media_images"),
    ("best meditation apps", "apps_store"),
    ("Apple stock price today", "finance_markets"),
    ("nonstop flights JFK to LHR next Friday", "travel_explore"),
    ("cheap weekend getaways from NYC in November", "travel_explore"),
    ("cheap trips from NYC in November", "travel_explore"),
    ("Plan a 4-day Tokyo trip under $1,200, flights + hotel", "lifeops_trip"),
    ("Best tacos in Austin, TX under $$ with 4.5+ rating", "lifeops_local"),
    ("Find the best deal on Sony WH-1000XM5 headphones", "lifeops_deals"),
])
def test_vertical_routing_regressions(prompt, pid):
    got, scores = _classify(prompt)
    assert got == pid, f"{prompt!r} -> {got}"
    assert scores[0]["confidence"] >= 0.50, f"{prompt!r} below floor: {scores[0]['confidence']}"


def test_event_tickets_do_not_hijack_travel_route():
    pid, _ = _classify("concert tickets in Austin")
    assert pid != "travel_explore"


@pytest.mark.parametrize("prompt,origin", [
    ("nonstop flights JFK to LHR next Friday", "JFK"),
    ("cheap weekend getaways from NYC in November", "NYC"),
    ("cheap trips from NYC in November", "NYC"),
    ("flights from scratch is a phrase", None),
    ("latest news in india", None),
])
def test_travel_origin_extraction(prompt, origin):
    assert I.analyze_prompt(prompt).travel_origin == origin, prompt


# ------------------------------------------------- 3. Groq router validation
def test_router_verdict_validation_accepts_only_real_catalogue_entries():
    good = {"playbook_id": "news_trends", "confidence": 0.9, "reason": "news query", "engines": ["google_news", "nope"]}
    v = I.validate_router_verdict(good)
    assert v and v["playbook_id"] == "news_trends" and v["engines"] == ["google_news"]
    assert I.validate_router_verdict({"playbook_id": "nope", "confidence": 0.9}) is None
    assert I.validate_router_verdict({"playbook_id": "news_trends", "confidence": 9}) is None
    assert I.validate_router_verdict({"playbook_id": "news_trends", "confidence": "high"}) is None
    assert I.validate_router_verdict("news_trends") is None
    assert I.validate_router_verdict(None) is None


def test_router_is_noop_without_llm_key():
    # keyless/offline test env -> deterministic classifier decides alone
    assert asyncio.run(I.route_with_llm("latest news", "go", I.analyze_prompt("latest news"))) is None


# ------------------------------------------------- 4. fresh call flags
_VARS = {"gl": "in", "geo": "IN", "topic": "songs", "query": "x", "mkt": "en-IN", "kl": "in-en"}


def test_strong_recency_marks_every_call_fresh():
    a = I.analyze_prompt("latest Techno Gamerz videos")
    calls = o.build_calls("media_video", dict(_VARS), triggers=o.triggers_for("latest Techno Gamerz videos", a), analysis=a)
    assert calls and all(c.fresh for c in calls)


def test_weak_recency_marks_only_sensitive_engines_fresh():
    a = I.analyze_prompt("recent uploads from mkbhd")
    assert a.recency and not a.fresh_strong
    calls = o.build_calls("media_video", dict(_VARS), analysis=a)
    assert all(c.fresh for c in calls)  # all three media engines are freshness-sensitive
    plain = o.build_calls("media_video", dict(_VARS), analysis=I.analyze_prompt("funny cat videos"))
    assert not any(c.fresh for c in plain)


def test_replan_rounds_are_always_fresh():
    calls = o.build_calls("media_video", dict(_VARS), fallback_round=1)
    assert calls and all(c.fresh for c in calls)


def test_youtube_carries_the_channel_followup_policy():
    calls = o.build_calls("media_video", dict(_VARS))
    yt = next(c for c in calls if c.engine == "youtube")
    assert yt.follow == "channel"


# ------------------------------------------------- 5. recency weight override
def test_freshness_weight_override_on_recency_prompts():
    w = {k: v["weight"] for k, v in PLAYBOOKS["media_video"]["dimensions"].items()}
    new_w, override = o.apply_recency_weights("media_video", w, I.analyze_prompt("latest Techno Gamerz videos"))
    assert override and new_w["freshness"] == pytest.approx(0.45, abs=0.01)
    assert new_w["popularity"] < w["popularity"]            # views no longer dominate freshness
    assert abs(sum(new_w.values()) - 1) < 0.02
    same, none = o.apply_recency_weights("media_video", w, I.analyze_prompt("funny cat videos"))
    assert none is None and same == w


# ------------------------------------------------- 6. cache: fingerprint + TTL + bypass
def test_fingerprint_is_case_sensitive_on_values():
    a = call_fingerprint("youtube", {"search_query": "Techno Gamerz"})
    b = call_fingerprint("youtube", {"search_query": "techno gamerz"})
    assert a != b                                            # creator vs generic can never collide
    assert call_fingerprint("youtube", {"search_query": "x", "api_key": "k", "async": "true"}) == \
        call_fingerprint("youtube", {"search_query": "x"})   # transport flags still excluded


def test_engine_ttls_favour_freshness():
    assert ttl_for("google_news", fresh=False) < ttl_for("google_play", fresh=False)
    assert ttl_for("youtube", fresh=True) <= 120


def test_fresh_search_bypasses_the_dedupe_cache():
    import httpx
    from app.services.cache import cache
    from app.services.serpapi import CreditMeter, SerpApiClient

    hits = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        return httpx.Response(200, json={"search_metadata": {"id": "z", "status": "Success"}, "organic_results": []})

    c = SerpApiClient()
    c.s = c.s.model_copy(update={"serpapi_key": "k", "demo_mode": False, "serp_poll_interval": 0.01})
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://serpapi.com")
    cache._mem.clear()

    async def go():
        import asyncio as aio
        sem, meter = aio.Semaphore(2), CreditMeter(10)
        p = {"q": "Cache Probe irreproducible"}
        r1 = await c.search("bing", p, session_id="t", call_id="c1", sem=sem, meter=meter, fresh=False)
        r2 = await c.search("bing", p, session_id="t", call_id="c2", sem=sem, meter=meter, fresh=False)
        r3 = await c.search("bing", p, session_id="t", call_id="c3", sem=sem, meter=meter, fresh=True)
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(go())
    assert not r1["cached"] and r2["cached"] and not r3["cached"]   # fresh forces a live pull
    assert hits["n"] == 2


# ------------------------------------------------- 7. robust age parsing
@pytest.mark.parametrize("s,lo,hi", [
    ("21h", 0.8, 1.0), ("14 hours ago", 0.5, 0.7), ("5 minutes ago", 0.0, 0.01),
    ("just now", 0.0, 0.0), ("today", 0.0, 0.0), ("yesterday", 1.0, 1.0),
    ("2 days ago", 2.0, 2.0), ("3 weeks ago", 21.0, 21.0), ("1 month ago", 30.0, 30.0),
    ("2 years ago", 700.0, 760.0), ("May 22 2026, 12:44:24 PM UTC-04:00", 100.0, 400.0),
    ("2026-09-21", 10.0, 60.0),
])
def test_days_ago_parses_every_flavour(s, lo, hi):
    v = _days_ago(s)
    assert v is not None and lo <= v <= hi, (s, v)


def test_days_ago_rejects_garbage():
    assert _days_ago(None) is None and _days_ago("") is None and _days_ago("someday maybe") is None


# ------------------------------------------------- 8. new normalizers vs docs samples
@pytest.mark.parametrize("engine,category,minimum", [
    ("youtube_channel", "media", 5), ("bing_news", "news", 3), ("duckduckgo_news", "news", 3),
    ("google_images", "image", 5), ("bing_videos", "media", 5), ("yahoo_videos", "media", 5),
    ("google_flights_deals", "destination", 5), ("google_play", "app", 1), ("apple_app_store", "app", 5),
])
def test_new_normalizer_parses_docs_sample(engine, category, minimum):
    d = _fx(engine)
    cands, _ = normalize(engine, d, category, d.get("search_parameters"))
    assert len(cands) >= minimum, f"{engine}: {len(cands)} candidates"
    assert all(c.title for c in cands)


def test_youtube_channel_exposes_channel_and_uploads():
    cands, ctx = normalize("youtube_channel", _fx("youtube_channel"), "media", {})
    assert ctx["channel"]["subscribers"] == 471000000
    assert all(c.category == "media" and c.attributes.get("views") for c in cands)
    assert cands[0].attributes["age_days"] == pytest.approx(2.0)


def test_youtube_search_surfaces_channel_followup():
    _, ctx = normalize("youtube", _fx("youtube"), "media", {})
    assert ctx["channel_followup"]["channel_id"] == "MrBeast"


def test_finance_quote_candidate_and_change():
    cands, ctx = normalize("google_finance", _fx("google_finance"), "finance", {})
    q = next(c for c in cands if c.category == "quote")
    assert q.price == pytest.approx(385.495) and q.attributes["change_pct"] == pytest.approx(0.5585, abs=1e-4)
    assert ctx["fx"]["rate"] == pytest.approx(385.495)          # legacy FX context preserved
    assert any(c.category == "news" for c in cands)             # instrument headlines ride along


def test_flights_deals_carry_discounts():
    cands, ctx = normalize("google_flights_deals", _fx("google_flights_deals"), "destination", {})
    assert ctx["deals_origin"] == "CDG"
    assert all(c.attributes.get("discount_pct") for c in cands) and all(c.attributes["is_deal"] for c in cands)


def test_app_stores_parse_ratings_and_makers():
    gp, _ = normalize("google_play", _fx("google_play"), "app", {})
    assert gp[0].rating == pytest.approx(4.3) and gp[0].attributes["downloads"] == 500000000
    ap, _ = normalize("apple_app_store", _fx("apple_app_store"), "app", {})
    assert ap[0].rating == pytest.approx(4.69) and ap[0].reviews == 28577967
    assert ap[0].attributes["developer"] == "Instagram, Inc."


def test_images_carry_resolution():
    cands, _ = normalize("google_images", _fx("google_images"), "image", {})
    assert cands[0].attributes["megapixels"] and cands[0].url.startswith("http")


# ------------------------------------------------- 9. corroboration + dedupe
def test_same_story_two_publishers_corroborates():
    from app.agents.researcher import corroborate
    a = Candidate(title="Instant coffee sales are spiking after tests", category="news", engine="google_news", source="Yahoo")
    b = Candidate(title="Instant coffee sales spiking, best brands tested", category="news", engine="bing_news", source="BBC")
    lone = Candidate(title="Unrelated local election outcome", category="news", engine="google_news", source="AP")
    corroborate([a, b, lone], {})
    assert a.attributes["publishers"] == 2 and b.attributes["publishers"] == 2
    assert lone.attributes["publishers"] == 1


def test_same_video_twice_is_deduped_after_consensus():
    from app.agents.researcher import corroborate
    a = Candidate(title="Clip X", category="media", engine="youtube", source="ch",
                  url="https://www.youtube.com/watch?v=dup12345", attributes={"views": 100})
    b = Candidate(title="Clip X", category="media", engine="youtube_channel", source="ch",
                  url="https://www.youtube.com/watch?v=dup12345", attributes={"views": 50})
    corroborate([a, b], {})
    assert a.verified and b.verified                                   # consensus computed first
    assert sum(1 for c in (a, b) if c.attributes.get("duplicate")) == 1  # ...then collapsed to one


def test_same_app_two_stores_is_verified():
    from app.agents.researcher import corroborate
    a = Candidate(title="Calm Meditation Pro", category="app", engine="google_play", source="Google Play")
    b = Candidate(title="Calm Meditation Pro", category="app", engine="apple_app_store", source="App Store")
    solo = Candidate(title="Obscure Flashlight Plus", category="app", engine="google_play", source="Google Play")
    corroborate([a, b, solo], {})
    assert a.verified and b.verified and not solo.verified


# ------------------------------------------------- 10. analyst pools + dimensions
def test_vertical_pools_score_without_errors():
    from app.agents import analyst as A
    mk = lambda cat, **kw: Candidate(title="t", category=cat, engine="e", source="s",
                                     attributes={"relevance": 0.5, "views": 1000, "age_days": 1.0, **kw})
    cases = {
        "news_trends": [mk("news", publishers=2)], "media_video": [mk("media")],
        "finance_markets": [mk("quote", stock="AAPL", change_pct=1.2)],
        "travel_explore": [mk("destination")], "general_search": [mk("serp")],
        "media_images": [mk("image", megapixels=8.1)], "apps_store": [mk("app", downloads=5000)],
    }
    for pid, pool in cases.items():
        w = {k: v["weight"] for k, v in PLAYBOOKS[pid]["dimensions"].items()}
        got = A.decision_pool(pid, pool, {})
        assert got, pid
        ranked = A.score(pid, got, w, {})
        assert ranked[0].score is not None, pid
        ins = __import__("app.services.aggregate", fromlist=["build_insights"]).build_insights(pid, ranked, pool, {}, {})
        assert ins and ins["kind"] == "feed" and ins["items"], pid


# ------------------------------------------------- 11. end-to-end freshness (Demo Mode, 0 credits)
def test_creator_query_drills_into_channel_and_ranks_fresh_first():
    from app import graph as G
    from app.services.events import bus
    sid = "t_creator_fresh"
    asyncio.run(G.run_session(sid, "latest Techno Gamerz videos", "go", None, None, True))
    hist = bus.history(sid)
    routing = next(e for e in hist if e["type"] == "orchestrator.routing")["data"]
    assert routing["playbook_id"] == "media_video"
    assert routing["analysis"]["entity"] == "Techno Gamerz"
    assert routing["weight_override"] and routing["weight_override"]["dimension"] == "freshness"
    engines = [e["data"]["engine"] for e in hist if e["type"] == "serp.response"]
    assert "youtube_channel" in engines                                # channel drill-down fired
    assert all(e["data"].get("fresh") for e in hist if e["type"] == "serp.response"
               and e["data"]["engine"] in ("youtube", "google_videos", "google_short_videos"))
    mx = next(e for e in hist if e["type"] == "analyst.matrix")["data"]
    top = mx["matrix"]["rows"][0]
    assert (top["attributes"].get("age_days") or 99) <= 2.0            # fresh upload wins, not a viral evergreen
    assert mx["insights"]["kind"] == "feed" and mx["insights"]["channel"]["title"]


def test_news_demo_session_ranks_fresh_corroborated_first():
    from app import graph as G
    from app.services.events import bus
    sid = "t_news_fresh"
    asyncio.run(G.run_session(sid, "latest news in india", "go", None, None, True))
    hist = bus.history(sid)
    routing = next(e for e in hist if e["type"] == "orchestrator.routing")["data"]
    assert routing["playbook_id"] == "news_trends"
    assert set(routing["engines"]) >= {"google_news", "google_trends", "google", "bing_news"}
    mx = next(e for e in hist if e["type"] == "analyst.matrix")["data"]
    assert mx["insights"]["kind"] == "feed" and len(mx["insights"]["items"]) >= 3

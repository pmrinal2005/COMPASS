"""NEW functionality only: intent routing, confidence floor, dynamic API selection and the
vertical normalizers. Offline and zero-credit (embeddings use the deterministic local fallback).

Acceptance criteria come from the bug report:
  * "latest news in india"  -> news / trends playbook, never local discovery
  * "trending songs in india" -> media playbook, never local discovery
  * "flights from Delhi to NYC" -> travel playbook
  * local venue prompts ("best tacos in Austin") keep routing to local discovery
  * low confidence (< 0.50) -> GENERAL_SEARCH, not LOCAL_DISCOVERY
  * optional engines only run when the prompt asks for them, and the per-playbook call cap holds
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.agents import orchestrator as o
from app.playbooks import PLAYBOOKS
from app.services.normalize import normalize

FIX = Path(__file__).parent / "fixtures"
LOCAL_DISCOVERY = "lifeops_local"


def _classify(prompt: str):
    return asyncio.run(o.classify(prompt, "go"))


# ---------------------------------------------------------------- taxonomy
def test_every_playbook_declares_a_taxonomy_category():
    allowed = {"NEWS_AND_TRENDS", "MEDIA_AND_ENTERTAINMENT", "LOCAL_DISCOVERY", "SHOPPING_AND_PRODUCTS", "TRAVEL_AND_ACCOMMODATION",
               "FINANCE_AND_MARKETS", "GENERAL_SEARCH", "JOBS_AND_CAREERS", "RESEARCH_AND_IP", "SEO_AND_VISIBILITY"}
    for pid, pb in PLAYBOOKS.items():
        assert pb.get("intent_category") in allowed, pid


def test_new_vertical_playbooks_exist_with_expected_categories():
    expected = {"news_trends": "NEWS_AND_TRENDS", "media_video": "MEDIA_AND_ENTERTAINMENT", "finance_markets": "FINANCE_AND_MARKETS",
                "travel_explore": "TRAVEL_AND_ACCOMMODATION", "general_search": "GENERAL_SEARCH"}
    for pid, cat in expected.items():
        assert pid in PLAYBOOKS and PLAYBOOKS[pid]["intent_category"] == cat


# ------------------------------------------------------ routing acceptance
@pytest.mark.parametrize("prompt,expected", [
    ("latest news in india", "news_trends"),
    ("trending songs in india", "media_video"),
    ("flights from Delhi to NYC", "travel_explore"),
    ("Apple stock price today", "finance_markets"),
    ("Bali resorts for 2 adults", "travel_explore"),
    ("Best tacos in Austin, TX under $$ with 4.5+ rating", LOCAL_DISCOVERY),
    ("Good ramen near downtown Seattle", LOCAL_DISCOVERY),
    ("Remote senior React developer jobs", "career_jobs"),
    ("Find the best deal on Sony WH-1000XM5 headphones", "lifeops_deals"),
    ("Prior art for solid-state battery dendrite suppression", "research_ip"),
    ("Plan a 4-day Tokyo trip under $1,200, flights + hotel", "lifeops_trip"),
])
def test_routing_acceptance(prompt, expected):
    pid, scores = _classify(prompt)
    assert pid == expected, f"{prompt!r} routed to {pid} (confidence {scores[0]['confidence']})"


# ------------------------------------------------------- confidence floor
@pytest.mark.parametrize("prompt", ["what is quantum computing", "who won the last world cup", "explain inflation simply",
                                    "asdf qwerty zxcv", "hello there friend"])
def test_low_confidence_defaults_to_general_search_never_local(prompt):
    pid, scores = _classify(prompt)
    assert pid == "general_search", f"{prompt!r} routed to {pid}"
    assert pid != LOCAL_DISCOVERY
    top = scores[0]
    assert top["routed_by"] == "confidence_floor" and top["confidence"] < o.INTENT_CONFIDENCE_FLOOR
    assert "reason" in top and top["intent_category"] == "GENERAL_SEARCH"


def test_confident_routes_are_above_the_floor():
    _, scores = _classify("latest news in india")
    assert scores[0]["routed_by"] == "classifier" and scores[0]["confidence"] >= o.INTENT_CONFIDENCE_FLOOR


def test_general_search_is_a_route_not_a_ranked_competitor():
    # a confident prompt must never be won by the GENERAL_SEARCH placeholder
    _, scores = _classify("trending songs in india")
    assert scores[0]["id"] == "media_video"
    assert scores[0]["id"] != "general_search"
    # the fallback is only ever placed at the top by the confidence floor, never by score
    _, floored = _classify("what is quantum computing")
    assert floored[0]["id"] == "general_search" and floored[0]["routed_by"] == "confidence_floor"


def test_forced_playbook_bypasses_classifier():
    pid, scores = asyncio.run(o.classify("anything", "go", forced="lifeops_local"))
    assert pid == "lifeops_local" and scores[0]["routed_by"] == "forced"


# --------------------------------------------------- dynamic API selection
VARS = {"gl": "in", "geo": "IN", "topic": "india", "ticker": "AAPL", "origin_iata": "DEL", "destination_iata": "JFK",
        "outbound_date": "2026-11-01", "return_date": "2026-11-05", "outbound_date_flex": "2026-11-03",
        "return_date_flex": "2026-11-07", "adults": 2, "destination": "Bali", "origin": "Delhi", "query": "x", "market": "in",
        "destination_iata_": "DPS"}


def _engines(pid: str, prompt: str) -> list[str]:
    return [c.engine for c in o.build_calls(pid, dict(VARS), triggers=o.triggers_for(prompt))]


def test_latest_news_does_not_call_trends_or_light_sweep():
    eng = _engines("news_trends", "latest news in india")
    assert eng == ["google_news", "google"], eng            # no unnecessary Trends / light calls


def test_trending_news_adds_trends_engines_only_when_asked():
    eng = _engines("news_trends", "trending news in india")
    assert "google_trends" in eng and "google_trends_trending_now" in eng


def test_quick_news_adds_light_sweep_only_when_asked():
    assert "google_news_light" in _engines("news_trends", "quick news on AI")
    assert "google_news_light" not in _engines("news_trends", "news on AI")


def test_optional_engines_never_exceed_per_playbook_cap():
    for pid in PLAYBOOKS:
        for prompt in ("trending quick brief news", "latest trends viral popular", "x"):
            assert len(_engines(pid, prompt)) <= o.MAX_CALLS_PER_PLAYBOOK, (pid, prompt)


def test_no_playbook_fans_out_to_the_whole_catalogue():
    total = sum(len(pb["engines"]) + len(pb.get("optional_engines", [])) for pb in PLAYBOOKS.values())
    assert max(len(_engines(pid, "trending quick news")) for pid in PLAYBOOKS) < total / 2


def test_media_prompt_selects_youtube_and_short_video():
    eng = _engines("media_video", "trending songs in india")
    assert "youtube" in eng and "google_short_videos" in eng


def test_travel_prompt_selects_flights_and_explore():
    eng = _engines("travel_explore", "flights from Delhi to NYC")
    assert "google_flights" in eng and "google_travel_explore" in eng


def test_local_discovery_keeps_its_venue_engines():
    eng = _engines(LOCAL_DISCOVERY, "best tacos in Austin")
    assert {"google_maps", "tripadvisor"} <= set(eng)
    assert "google_shopping" not in eng and "amazon" not in eng


# ----------------------------------------------- new normalizers (real docs samples)
def _fx(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text())


@pytest.mark.parametrize("engine,category,minimum", [
    ("youtube", "media", 5), ("google_videos", "media", 5), ("google_short_videos", "media", 5),
    ("google_news_light", "news", 3), ("google_trends_trending_now", "trend", 5),
    ("google_finance_markets", "finance", 5), ("google_travel_explore", "destination", 5), ("google_light", "serp", 3),
])
def test_vertical_normalizer_parses_docs_sample(engine, category, minimum):
    d = _fx(engine)
    cands, _ = normalize(engine, d, category, d.get("search_parameters"))
    assert len(cands) >= minimum, f"{engine}: {len(cands)} candidates"
    assert all(c.title for c in cands)


def test_youtube_views_and_age_are_extracted():
    d = _fx("youtube")
    cands, _ = normalize("youtube", d, "media", d["search_parameters"])
    assert any(c.attributes.get("views") for c in cands) and any(c.attributes.get("published") for c in cands)


def test_google_videos_channel_and_age_from_rich_snippet():
    cands, _ = normalize("google_videos", _fx("google_videos"), "media", {})
    top = cands[0]
    assert top.source == "Ryan Shirley" and top.attributes["published"] == "1 day ago"


def test_finance_markets_change_pct_matches_docs_value():
    cands, ctx = normalize("google_finance_markets", _fx("google_finance_markets"), "finance", {})
    dow = next(c for c in cands if c.title == "Dow Jones")
    assert dow.attributes["change_pct"] == pytest.approx(0.717, abs=1e-3)      # docs: percentage already in %
    assert set(ctx["markets"][0]) >= {"region", "name", "change_pct"}


def test_trends_trending_now_extracts_volume_and_increase():
    cands, ctx = normalize("google_trends_trending_now", _fx("google_trends_trending_now"), "trend", {})
    assert cands[0].attributes["search_volume"] > 0 and cands[0].attributes["increase_pct"] > 0
    assert ctx["trending_now"]


def test_travel_explore_destinations_are_priced_and_airport_coded():
    cands, _ = normalize("google_travel_explore", _fx("google_travel_explore"), "destination", {})
    assert all(c.price for c in cands) and all(c.attributes["airport"] for c in cands)


def test_news_light_shares_the_news_shape():
    cands, _ = normalize("google_news_light", _fx("google_news_light"), "news", {})
    assert all(c.category == "news" and c.url for c in cands)


# -------------------------------------------------------- demo payloads
def test_vertical_demo_payloads_normalize_through_the_pipeline():
    from app.services.demo_extra import demo_extra
    import random
    for engine, cat in [("youtube", "media"), ("google_short_videos", "media"), ("google_news_light", "news"),
                        ("google_trends_trending_now", "trend"), ("google_finance_markets", "finance"),
                        ("google_travel_explore", "destination"), ("google_light", "serp")]:
        payload = demo_extra(engine, {"search_query": "trending songs", "q": "trending songs", "geo": "IN", "departure_id": "JFK"},
                             random.Random(3))
        assert payload is not None, engine
        cands, _ = normalize(engine, payload, cat, {})
        assert cands, engine


def test_demo_video_titles_are_unique_so_analyst_does_not_collapse_them():
    from app.services.demo_vertical import youtube
    import random
    rows = youtube({"search_query": "trending songs in india"}, random.Random(1))["video_results"]
    titles = [r["title"] for r in rows]
    assert len(set(titles)) == len(titles)

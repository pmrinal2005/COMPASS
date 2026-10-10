"""Regression tests for bugs found by the LIVE end-to-end run against serpapi.com (no network, 0 credits).
Payload shapes below are copied from real responses of the Google Hotels / Google Jobs / Google Flights APIs."""
from __future__ import annotations

from app.agents import analyst, researcher
from app.models import Candidate
from app.services.normalize import normalize


def _hotel(name: str, price: float, call: str) -> Candidate:
    return Candidate(title=name, category="hotel", engine="google_hotels", source="Google Hotels", price=price, rating=4.3, reviews=400,
                     attributes={"match_key": name.lower(), "call_id": call})


def _flight(price: float, num: str = "AA 167") -> Candidate:
    return Candidate(title="American · JFK → HND", category="flight", engine="google_flights", source="American", price=price,
                     duration_min=876, attributes={"match_key": num, "call_variant": "default", "flight_numbers": [num], "departure": "2026-11-08 09:59"})


def test_same_hotel_from_two_passes_is_one_option_and_corroborated():
    hs = [_hotel("Hotel Owl", 14, "c1"), _hotel("Hotel Owl", 14, "c2"), _hotel("Other", 30, "c1")]
    res = researcher.corroborate(hs + [_flight(1000)], {}, 2)
    assert sum(1 for h in hs if h.attributes.get("duplicate")) == 1
    kept = next(h for h in hs if h.title == "Hotel Owl" and not h.attributes.get("duplicate"))
    assert kept.verified and "google_hotels:2nd_query" in kept.corroborating_sources
    assert res["total"] == 3          # 2 distinct hotels + 1 flight - the duplicate is not counted
    bundles = analyst.build_bundles(hs + [_flight(1000)], {"nights": 4, "budget": 1200})
    assert len(bundles) == 2 and len({b.title for b in bundles}) == 2      # no repeated flight x hotel bundle


def test_hotel_name_variants_match_maps_listing():
    h = _hotel("Hotel Owl Tokyo Nippori", 14, "c1")
    p = Candidate(title="HOTEL OWL TOKYO NIPPORI by Sakura", category="place", engine="google_maps", source="Google Maps", rating=4.2, reviews=900,
                  attributes={"match_key": "hotel owl tokyo nippori by sakura"})
    researcher.corroborate([h, p], {}, 2)
    assert "google_maps" in h.corroborating_sources and h.verified


def test_bundle_exposes_flight_identity():
    b = analyst.build_bundles([_flight(1000), _hotel("A", 20, "c1")], {"nights": 4, "budget": 1500})[0]
    assert b.attributes["flight_numbers"] == ["AA 167"] and b.attributes["departure"]


def test_google_jobs_boards_collapse_and_corroborate():
    data = {"search_metadata": {"status": "Success"}, "jobs_results": [
        {"title": "Senior React Dev", "company_name": "GoIntellects Inc.", "via": "Monster", "location": "Anywhere",
         "apply_options": [{"title": "Monster", "link": "https://m"}, {"title": "Indeed", "link": "https://i"}, {"title": "Dice", "link": "https://d"}]},
        {"title": "Senior React Dev", "company_name": "GoIntellects", "via": "Mediabistro", "location": "Anywhere",
         "apply_options": [{"title": "Mediabistro", "link": "https://mb"}]},
        {"title": "Solo Role", "company_name": "Acme", "via": "Lensa", "apply_options": [{"title": "Lensa", "link": "https://l"}]}]}
    cands, _ = normalize("google_jobs", data, "job", {"q": "react"})
    assert cands[0].attributes["boards"] == ["Monster", "Indeed", "Dice"]
    researcher.corroborate(cands, {}, 2)
    live = [c for c in cands if not c.attributes.get("duplicate")]
    assert len(live) == 2
    react = next(c for c in live if c.title.startswith("Senior React"))
    assert react.verified and set(react.attributes["boards"]) >= {"Monster", "Mediabistro", "Indeed", "Dice"}
    assert not next(c for c in live if c.title.startswith("Solo")).verified


# ---- events: Google Search API stopped returning events_results for "Events in <city>" -------------------------------
LIVE_EVENTS = {"events_results": [  # shape copied from a real engine=google response for "events in Tokyo this weekend"
    {"title": "Sonar Pocket", "type": "J-pop concert", "date": "Oct 12", "time": "5:00 PM",
     "address": ["SWU Hitomi Memorial Hall", "Setagaya City, Japan"], "thumbnail": "https://serpapi.com/x.jpeg"},
    {"title": "Shomyo Chant", "type": "Buddhist vocal music", "date": "Oct 17", "address": ["Kotoku Bunka Center Hall", "Koto City, Japan"]}]}


def test_live_events_shape_with_string_date_does_not_crash():
    """`date` is a plain string live (it was a dict in the docs sample) -> used to raise AttributeError and empty the panel."""
    c, _ = normalize("google", LIVE_EVENTS, "event", {"q": "events in Tokyo this weekend"})
    assert [x.title for x in c] == ["Sonar Pocket", "Shomyo Chant"]
    assert c[0].attributes["when"] == "Oct 12 · 5:00 PM" and c[0].attributes["venue"] == "SWU Hitomi Memorial Hall"
    assert c[1].attributes["when"] == "Oct 17" and c[0].attributes["kind"] == "J-pop concert"


def test_events_fall_back_to_top_sights_when_google_shows_no_events_block():
    data = {"top_sights": {"sights": [{"title": "Barton Springs Pool", "description": "Open", "rating": 4.6, "reviews": 11000,
                                         "price": "$9.00", "link": "https://g.test/1"}]}}
    c, _ = normalize("google", data, "event", {"q": "things to do in Austin"})
    assert len(c) == 1 and c[0].category == "event" and c[0].rating == 4.6 and c[0].attributes["kind"] == "Attraction"
    assert normalize("google", {}, "event", {})[0] == []


def test_event_playbook_queries_are_the_ones_google_renders_events_for():
    from app.playbooks import PLAYBOOKS
    for pid, key in (("lifeops_trip", "destination"), ("lifeops_local", "city")):
        sp = next(s for s in PLAYBOOKS[pid]["engines"] if s["category"] == "event")
        assert sp["params"]["q"].endswith("this weekend") and "{" + key + "}" in sp["params"]["q"], sp


def test_demo_mode_serves_events_for_the_new_query_shape():
    from app.services.demo_data import demo_response
    d = demo_response("google", {"q": "events in Tokyo this weekend"})
    assert d.get("events_results") and "Tokyo" in d["events_results"][0]["title"]
    assert not demo_response("google", {"q": "google search api"}).get("events_results")

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

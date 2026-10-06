"""Tiny offline city -> IATA / currency lookup used for slot filling.
(In live mode unknown cities can be resolved through SerpApi's
google_flights_autocomplete engine.)"""
from __future__ import annotations

CITIES: dict[str, tuple[str, str]] = {
    "tokyo": ("HND", "JPY"), "osaka": ("KIX", "JPY"), "kyoto": ("KIX", "JPY"), "seoul": ("ICN", "KRW"),
    "paris": ("CDG", "EUR"), "london": ("LHR", "GBP"), "rome": ("FCO", "EUR"), "barcelona": ("BCN", "EUR"),
    "madrid": ("MAD", "EUR"), "berlin": ("BER", "EUR"), "amsterdam": ("AMS", "EUR"), "lisbon": ("LIS", "EUR"),
    "new york": ("JFK", "USD"), "nyc": ("JFK", "USD"), "los angeles": ("LAX", "USD"), "la": ("LAX", "USD"),
    "san francisco": ("SFO", "USD"), "chicago": ("ORD", "USD"), "miami": ("MIA", "USD"), "boston": ("BOS", "USD"),
    "seattle": ("SEA", "USD"), "austin": ("AUS", "USD"), "las vegas": ("LAS", "USD"), "denver": ("DEN", "USD"),
    "toronto": ("YYZ", "CAD"), "vancouver": ("YVR", "CAD"), "mexico city": ("MEX", "MXN"), "cancun": ("CUN", "MXN"),
    "bangkok": ("BKK", "THB"), "singapore": ("SIN", "SGD"), "bali": ("DPS", "IDR"), "dubai": ("DXB", "AED"),
    "sydney": ("SYD", "AUD"), "delhi": ("DEL", "INR"), "mumbai": ("BOM", "INR"), "bangalore": ("BLR", "INR"),
    "hong kong": ("HKG", "HKD"), "istanbul": ("IST", "TRY"), "reykjavik": ("KEF", "ISK"),
}


def lookup(city: str | None) -> tuple[str, str]:
    if not city:
        return ("JFK", "USD")
    c = city.strip().lower()
    if c in CITIES:
        return CITIES[c]
    for k, v in CITIES.items():
        if k in c:
            return v
    return (city.strip()[:3].upper(), "USD")

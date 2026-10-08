"""Demo Mode payloads for the engines added in the second build pass.

Every payload mirrors the *documented* SerpApi response shape of its engine
(field names verified against https://serpapi.com/<engine>-api):

  bing / duckduckgo / yahoo / yandex / baidu  -> organic_results[position,title,link,displayed_link|displayed_brand,snippet]
  naver                                       -> web_results[...]
  google_ai_mode                              -> text_blocks[], references[{title,link,snippet,source,index}]
  google_ai_overview                          -> ai_overview.{text_blocks[], references[]}
  yelp                                        -> organic_results[{title,rating,reviews,price,neighborhoods,categories,link,place_ids}]
  tripadvisor                                 -> places[{place_id,place_type,title,rating,reviews,location,link}]
  google_events                               -> events_results[{title,date{start_date,when},address[],venue{name,rating,reviews},link}]
  airbnb                                      -> organic_results[{listing_id,name,rating,reviews,extracted_price,price_qualifier,badges,link}]
  google_maps (venues)                        -> local_results[{title,place_id,rating,reviews,price,type,address}]

Venue / domain universes are seeded by the query so the *same* entities show up
across platforms/engines (with slightly different names, ratings and ranks) -
that is what makes cross-source corroboration meaningful in Demo Mode.
"""
from __future__ import annotations

import base64
import hashlib
import random
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

from .entities import page_offset

# ----------------------------------------------------------------- helpers

def seed(*parts: Any) -> random.Random:
    return random.Random(int(hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest()[:12], 16))


def _q(p: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        if p.get(k):
            return str(p[k])
    return default


# --------------------------------------------------------------- web SERPs
GENERIC_DOMAINS = [
    "wikipedia.org", "reddit.com", "youtube.com", "medium.com", "nytimes.com", "forbes.com", "techcrunch.com", "github.com",
    "stackoverflow.com", "hubspot.com", "ibm.com", "cloudflare.com", "mozilla.org", "w3schools.com", "geeksforgeeks.org",
    "quora.com", "linkedin.com", "amazon.com", "bbc.com", "theverge.com", "wired.com", "investopedia.com", "healthline.com",
]
BRAND_DOMAINS = ["serpapi.com", "scrapingbee.com", "zenserp.com", "brightdata.com", "apify.com", "oxylabs.io"]
REGIONAL = {
    "baidu": ["baike.baidu.com", "zhihu.com", "csdn.net", "jianshu.com", "bilibili.com", "36kr.com"],
    "yandex": ["dzen.ru", "habr.com", "vc.ru", "kinopoisk.ru", "ru.wikipedia.org"],
    "naver": ["blog.naver.com", "namu.wiki", "tistory.com", "terms.naver.com", "brunch.co.kr"],
}
PAGE_WORDS = ["Guide", "Overview", "Tutorial", "Pricing", "Documentation", "Review", "Comparison", "Best practices", "FAQ", "Examples"]


def _universe(q: str) -> list[tuple[str, float]]:
    """(domain, base_strength) for a keyword — shared by every engine."""
    r = seed("universe", q.lower())
    pool = r.sample(GENERIC_DOMAINS, 14)
    qs = q.lower()
    brands = list(BRAND_DOMAINS)
    if not any(w in qs for w in ("serp", "scrap", "api", "search")):
        brands = brands[:2]          # still present (the tracked brand must be findable), just weaker
    items = [(d, r.uniform(0.35, 1.0)) for d in pool] + [(b, r.uniform(0.15, 0.95)) for b in brands]
    return items


def _serp_rows(engine: str, q: str, drift_r: random.Random | None, _offset: int = 0) -> list[tuple[str, int]]:
    base = _universe(q)
    er = seed("serp", engine, q.lower())
    scored = [(d, s + er.uniform(-0.22, 0.22)) for d, s in base]
    if engine in REGIONAL:
        extra = REGIONAL[engine]
        scored = [(d, s * 0.7) for d, s in scored if er.random() < 0.65] + [(d, er.uniform(0.55, 1.0)) for d in extra[:4]]
    scored.sort(key=lambda x: -x[1])
    rows = [(d, i + 1) for i, (d, _) in enumerate(scored[:14])]
    off = _offset
    if off:                                    # pagination: the engine skips `off` results (start / first / b / pn / p)
        rows = [(d, off + i + 1) for i, (d, _) in enumerate(scored[off:off + 14])]
    if drift_r is not None:  # watch drift: tracked domain wobbles by ±1 between polls
        rows = [(d, max(1, p + (drift_r.choice([-1, 0, 0, 1]) if d == "serpapi.com" else 0))) for d, p in rows]
        rows.sort(key=lambda x: x[1])
        rows = [(d, i + 1) for i, (d, _) in enumerate(rows)]
    return rows


def _title(domain: str, q: str, r: random.Random) -> str:
    brand = domain.split(".")[0].replace("-", " ").title()
    return f"{brand}: {q.title()} — {r.choice(PAGE_WORDS)}"


def _snip(domain: str, q: str, r: random.Random) -> str:
    return f"{domain} explains {q} with practical examples, benchmarks and step-by-step instructions. " \
           f"Updated {r.randint(1, 28)} days ago."


def serp(engine: str, p: dict, drift_r: random.Random | None = None) -> dict:
    q = _q(p, "q", "p", "text", "query", default="query")
    rows = _serp_rows(engine, q, drift_r, page_offset(engine, p))
    r = seed("snip", engine, q)
    out = []
    for dom, pos in rows:
        path = f"/{r.choice(['blog', 'docs', 'learn', 'guides', 'resources'])}/{quote_plus(q.lower())[:30]}"
        link = f"https://www.{dom}{path}" if not dom.startswith(("baike", "blog", "ru.", "terms")) else f"https://{dom}{path}"
        row: dict[str, Any] = {"position": pos, "title": _title(dom, q, r), "link": link, "snippet": _snip(dom, q, r)}
        if engine in ("bing", "yahoo", "yandex"):
            row["displayed_link"] = f"https://{dom}{path}"[:60]
        if engine == "baidu":
            row["link"] = f"http://www.baidu.com/link?url={hashlib.md5((dom + q).encode()).hexdigest()}"   # redirect, like the real engine
            row["displayed_brand"] = f"{dom}/"
        if engine == "duckduckgo":
            row["favicon"] = f"https://external-content.duckduckgo.com/ip3/{dom}.ico"
        out.append(row)
    key = "web_results" if engine == "naver" else "organic_results"
    body: dict[str, Any] = {key: out, "search_information": {"organic_results_state": "Results for exact spelling", "total_results": 1_000_000 * (len(q) + 3)}}
    if engine == "google" and not page_offset(engine, p):   # real responses expose a short-lived token for the AI Overview
        tok = "demo-" + base64.urlsafe_b64encode(q.encode()).decode().rstrip("=")
        body["ai_overview"] = {"page_token": tok,
                               "serpapi_link": f"https://serpapi.com/search.json?engine=google_ai_overview&page_token={tok}"}
    if engine == "bing":
        body["related_searches"] = [{"query": f"{q} {w}"} for w in ("pricing", "alternatives", "tutorial")]
    return body


def ai_mode(p: dict) -> dict:
    q = _q(p, "q", default="query")
    r = seed("ai_mode", q.lower())
    base = sorted(_universe(q), key=lambda x: -(x[1] + r.uniform(-0.3, 0.3)))[:6]
    refs = []
    for i, (dom, _) in enumerate(base):
        refs.append({"title": _title(dom, q, r), "link": f"https://www.{dom}/{quote_plus(q.lower())[:24]}", "snippet": _snip(dom, q, r),
                     "source": dom.split(".")[0].title(), "index": i})
    blocks = [{"type": "paragraph", "snippet": f"{q.capitalize()} refers to a topic with several well-documented approaches. "
                                               f"Leading sources agree on the fundamentals and differ mainly on tooling and cost.",
               "reference_indexes": [0, 1, 2]},
              {"type": "list", "list": [{"title": f"Point {n + 1}", "snippet": f"Key consideration {n + 1} for {q}.", "reference_indexes": [n % len(refs)]}
                                        for n in range(3)]}]
    return {"quick_results": refs[:2], "text_blocks": blocks, "references": refs,
            "reconstructed_markdown": "\n\n".join(b.get("snippet", "") for b in blocks)}


def ai_overview(p: dict) -> dict:
    tok = str(p.get("page_token") or "")
    q = "query"
    if tok.startswith("demo-"):
        raw = tok[5:]
        try:
            q = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
        except Exception:
            pass
    d = ai_mode({"q": q})
    return {"ai_overview": {"text_blocks": d["text_blocks"], "references": d["references"]}}


# ------------------------------------------------------------------- venues
KIND_WORDS = {
    "taco": ("Tacos", ["Taqueria", "Cantina", "Taco House", "Tacos", "Cocina"]),
    "pizza": ("Pizza", ["Pizzeria", "Pizza Co.", "Slice House", "Pizza Bar"]),
    "coffee": ("Coffee", ["Coffee Roasters", "Cafe", "Coffee Bar", "Espresso"]),
    "ramen": ("Ramen", ["Ramen", "Noodle Bar", "Ramen House", "Izakaya"]),
    "bbq": ("BBQ", ["BBQ", "Smokehouse", "Barbecue", "Pit"]),
    "sushi": ("Sushi", ["Sushi", "Sushi Bar", "Omakase", "Maki House"]),
    "burger": ("Burgers", ["Burger Joint", "Burgers", "Grill", "Burger Co."]),
    "brunch": ("Brunch", ["Brunch House", "Cafe", "Kitchen", "Eatery"]),
}
VENUE_PRE = ["Lucky", "Casa", "Golden", "Rosita's", "Blue", "Hatch", "Juniper", "Maple", "Salt &", "Copper", "Rio", "Sunny", "Old Town",
             "Little", "Verde", "Ember", "Magnolia", "Torch", "Harvest", "Saffron"]
STREETS = ["Congress Ave", "South 1st St", "E 6th St", "Lamar Blvd", "Guadalupe St", "Rainey St", "Burnet Rd", "Manor Rd", "Barton Springs Rd"]
HOODS = ["Downtown", "East Austin", "South Congress", "Hyde Park", "Rainey Street", "Zilker", "The Domain", "Clarksville"]
FOOD_WORDS = ("taco", "pizza", "coffee", "ramen", "bbq", "sushi", "burger", "brunch", "restaurant", "food", "eat", "dinner", "lunch", "cafe",
              "bar", "thai", "indian", "vegan", "bakery", "noodle", "steak", "seafood")


def venue_kind(q: str) -> str:
    ql = q.lower()
    for k in KIND_WORDS:
        if k in ql:
            return k
    return "taco"


def is_food(q: str) -> bool:
    ql = q.lower()
    return any(w in ql for w in FOOD_WORDS)


def _venues(query: str, city: str, n: int = 9) -> list[dict]:
    """Canonical venue list for (kind, city) — same across platforms."""
    kind = venue_kind(query)
    r = seed("venues", kind, city.lower())
    word, suffixes = KIND_WORDS[kind]
    names, seen = [], set()
    while len(names) < n:
        nm = f"{r.choice(VENUE_PRE)} {r.choice(suffixes)}"
        if nm in seen:
            continue
        seen.add(nm)
        names.append({"name": nm, "base_rating": round(r.uniform(3.7, 4.8), 2), "base_reviews": int(r.paretovariate(1.3) * 160) + 60,
                      "price_level": r.choice([1, 1, 2, 2, 2, 3]), "street": f"{r.randint(100, 4800)} {r.choice(STREETS)}",
                      "hood": r.choice(HOODS), "word": word})
    return names


def _vary(name: str, platform: str, r: random.Random) -> str:
    """Platform-specific naming noise (what makes fuzzy cross-platform matching necessary)."""
    if platform == "yelp" and r.random() < 0.5:
        return name + " - " + r.choice(HOODS)
    if platform == "tripadvisor" and r.random() < 0.4:
        return name + " Restaurant"
    if platform == "google_maps" and r.random() < 0.25:
        return name.replace("&", "and")
    return name


def maps_venues(p: dict) -> dict:
    q = _q(p, "q", default="tacos in Austin, TX")
    if " in " in q:
        query, city = q.rsplit(" in ", 1)
    else:
        query, city = q, "Austin, TX"
    r = seed("gmaps", q.lower())
    vs = _venues(query.replace("best ", "").replace("top ", ""), city)
    min_rating = float(p.get("min_rating") or 0)
    out = []
    for i, v in enumerate(vs[:8]):
        rating = round(min(4.9, max(3.2, v["base_rating"] + r.uniform(-0.2, 0.25))), 1)
        if rating < min_rating:
            rating = round(min_rating + r.uniform(0.0, 0.2), 1)
        out.append({"position": i + 1, "title": _vary(v["name"], "google_maps", r), "place_id": hashlib.md5(v["name"].encode()).hexdigest()[:16],
                    "rating": rating, "reviews": int(v["base_reviews"] * r.uniform(0.8, 1.6)), "price": "$" * v["price_level"],
                    "type": v["word"] + " restaurant", "address": f"{v['street']}, {city}",
                    "gps_coordinates": {"latitude": 30.26 + r.random() / 40, "longitude": -97.74 + r.random() / 40}})
    return {"local_results": out}


def yelp(p: dict, drift_r: random.Random | None) -> dict:
    query = _q(p, "find_desc", default="tacos")
    city = _q(p, "find_loc", default="Austin, TX")
    r = seed("yelp", query.lower(), city.lower(), p.get("sortby", ""))
    vs = _venues(query, city)
    rows = []
    for i, v in enumerate(vs):
        rating = round(min(5.0, max(3.0, v["base_rating"] + r.uniform(-0.3, 0.2))), 1)
        if drift_r is not None:
            rating = round(min(5.0, max(2.5, rating + drift_r.uniform(-0.12, 0.12))), 1)
        rows.append({"position": i + 1, "place_ids": [hashlib.md5(v["name"].encode()).hexdigest()[:22], v["name"].lower().replace(" ", "-")],
                     "title": _vary(v["name"], "yelp", r), "link": f"https://www.yelp.com/biz/{v['name'].lower().replace(' ', '-').replace('&', 'and')}-austin",
                     "categories": [{"title": v["word"], "link": "https://www.yelp.com/search"}], "price": "$" * v["price_level"],
                     "rating": rating, "reviews": int(v["base_reviews"] * r.uniform(0.5, 1.2)), "neighborhoods": v["hood"],
                     "snippet": f"Great {v['word'].lower()} spot — friendly staff and fast service.", "service_options": {"takeout": True}})
    if str(p.get("sortby")) == "rating":
        rows.sort(key=lambda x: -x["rating"])
    elif str(p.get("sortby")) == "review_count":
        rows.sort(key=lambda x: -x["reviews"])
    for i, row in enumerate(rows):
        row["position"] = i + 1
    return {"organic_results": rows[:9]}


def tripadvisor(p: dict, drift_r: random.Random | None = None) -> dict:
    q = _q(p, "q", default="tacos Austin, TX")
    ssrc = str(p.get("ssrc") or "a")
    r = seed("tripadvisor", q.lower(), ssrc)
    words = q.split()
    city = " ".join(words[-2:]) if len(words) >= 2 else "Austin, TX"
    query = " ".join(words[:-2]) or q
    places: list[dict] = [{"position": 1, "title": city.split(",")[0].title(), "place_id": 1000 + r.randint(1, 999), "place_type": "GEO",
                           "link": "https://www.tripadvisor.com/Tourism-g30196-Austin_Texas-Vacations.html", "description": f"Explore {city}.",
                           "location": city}]
    if ssrc in ("r", "a"):
        for i, v in enumerate(_venues(query, city)[:7]):
            rating = round(min(5.0, max(3.0, v["base_rating"] + r.uniform(-0.25, 0.3))) * 2) / 2
            if drift_r is not None:
                rating = max(2.5, min(5.0, rating + drift_r.choice([-0.5, 0, 0, 0.5])))
            places.append({"position": len(places) + 1, "title": _vary(v["name"], "tripadvisor", r), "place_id": 13_000_000 + r.randint(1, 999_999),
                           "place_type": "RESTAURANT", "link": f"https://www.tripadvisor.com/Restaurant_Review-{r.randint(10**5, 10**6)}-Reviews.html",
                           "rating": rating, "reviews": int(v["base_reviews"] * r.uniform(0.7, 2.4)), "location": city,
                           "description": f"{v['word']} favorite on {v['street']}."})
    if ssrc == "A":
        for i in range(5):
            places.append({"position": len(places) + 1, "title": f"{r.choice(VENUE_PRE)} {r.choice(['Tour', 'Walk', 'Museum', 'Park'])}",
                           "place_id": 2_000_000 + i, "place_type": "ATTRACTION", "rating": round(r.uniform(4.0, 5.0) * 2) / 2,
                           "reviews": r.randint(100, 9000), "location": city, "link": "https://www.tripadvisor.com/Attraction_Review.html"})
    return {"places": places}


def events(p: dict, drift_r: random.Random | None = None) -> dict:
    q = _q(p, "q", default="Events in Austin")
    city = q.split(" in ")[-1].strip() or "the city"
    r = seed("events", q.lower())
    kinds = ["Live Jazz Night", "Food Truck Festival", "Comedy Showcase", "Street Art Walk", "Night Market", "Indie Film Screening",
             "Open-Air Concert", "Craft Beer Fest", "Sunrise Yoga in the Park", "Tech Meetup"]
    today = datetime.utcnow() + timedelta(days=int(p.get("_offset_days") or 30))
    out = []
    for i, k in enumerate(r.sample(kinds, 7)):
        d = today + timedelta(days=r.randint(0, 5))
        venue = f"{r.choice(VENUE_PRE)} {r.choice(['Hall', 'Garden', 'Theatre', 'Plaza', 'Club'])}"
        out.append({"title": f"{k} · {city}", "date": {"start_date": d.strftime("%b %-d"), "when": d.strftime("%a, %b %-d, 7:00 – 10:00 PM")},
                    "address": [venue, city], "link": f"https://events.example.com/{hashlib.md5((k + city).encode()).hexdigest()[:8]}",
                    "description": f"{k} featuring local artists and vendors in {city}.",
                    "ticket_info": [{"source": "Eventbrite", "link": "https://www.eventbrite.com/", "link_type": "tickets"}],
                    "venue": {"name": venue, "rating": round(r.uniform(4.0, 4.9), 1), "reviews": r.randint(40, 2400)},
                    "thumbnail": ""})
    return {"events_results": out, "search_information": {"events_results_state": "Results for exact spelling"}}


def airbnb(p: dict) -> dict:
    city = _q(p, "q", default="Tokyo")
    r = seed("airbnb", city.lower(), p.get("check_in_date", ""))
    try:
        nights = max(1, (datetime.strptime(p["check_out_date"], "%Y-%m-%d") - datetime.strptime(p["check_in_date"], "%Y-%m-%d")).days)
    except Exception:
        nights = 4
    kinds = ["Home", "Rental unit", "Loft", "Condo", "Guest suite", "Townhouse"]
    out = []
    for i in range(8):
        nightly = r.randint(55, 190)
        total = nightly * nights
        rating = round(r.uniform(4.55, 5.0), 2) if r.random() > 0.15 else round(r.uniform(3.9, 4.5), 2)
        out.append({"position": i + 1, "listing_id": str(r.randint(10**17, 10**18)), "title": f"{r.choice(kinds)} in {city}",
                    "name": f"{r.choice(['Sunny', 'Quiet', 'Modern', 'Cozy', 'Central', 'Designer'])} {r.choice(['studio', 'flat', 'loft', 'apartment'])} near "
                            f"{r.choice(['the station', 'old town', 'the river', 'the market'])}",
                    "description": "Walkable location with fast Wi-Fi and a full kitchen.",
                    "link": f"https://www.airbnb.com/rooms/{r.randint(10**8, 10**9)}?check_in={p.get('check_in_date', '')}&check_out={p.get('check_out_date', '')}",
                    "rating": rating, "reviews": r.randint(3, 420), "badges": ["Guest favorite"] if rating >= 4.85 else [],
                    "price": f"${total:,}", "extracted_price": total, "price_qualifier": f"for {nights} nights",
                    "check_in_date": p.get("check_in_date"), "check_out_date": p.get("check_out_date"),
                    "bedrooms": r.randint(1, 3), "beds": r.randint(1, 4), "bathrooms": r.choice([1, 1.5, 2]), "free_cancellation": r.random() < 0.6,
                    "gps_coordinates": {"latitude": 35.68 + r.random() / 30, "longitude": 139.7 + r.random() / 30}})
    return {"organic_results": out, "search_information": {"organic_results_state": "Results for exact spelling"}}


def demo_extra(engine: str, p: dict, drift_r: random.Random | None) -> dict | None:
    """Return a payload for an engine handled here, else None."""
    if engine in ("bing", "duckduckgo", "yahoo", "yandex", "baidu", "naver"):
        return serp(engine, p, drift_r)
    if engine == "google_ai_mode":
        return ai_mode(p)
    if engine == "google_ai_overview":
        return ai_overview(p)
    if engine == "yelp":
        return yelp(p, drift_r)
    if engine == "tripadvisor":
        return tripadvisor(p, drift_r)
    if engine == "google_events":
        return events(p, drift_r)
    if engine == "airbnb":
        return airbnb(p)
    return None

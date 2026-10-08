"""Demo Mode dataset: deterministic, *shape-faithful* SerpApi responses
(field names mirror the official docs for each engine) so the entire
pipeline — normalization, corroboration, ranking, actions — runs exactly
as it would against live SerpApi, with zero credits spent.

Responses are seeded by the request fingerprint so the same query always
returns the same payload (which also lets the cache/dedupe layer be shown
honestly). `drift` lets watch polls simulate price movement over time.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
from typing import Any

from . import demo_extra

AIRLINES = [("ANA", "NH"), ("Japan Airlines", "JL"), ("United", "UA"), ("Delta", "DL"), ("American", "AA"),
            ("Air Canada", "AC"), ("Korean Air", "KE"), ("Lufthansa", "LH"), ("Air France", "AF"), ("Emirates", "EK")]
HUBS = [("Haneda Airport", "HND"), ("San Francisco International", "SFO"), ("Seoul Incheon", "ICN"),
        ("Vancouver International", "YVR"), ("Frankfurt Airport", "FRA"), ("Chicago O'Hare", "ORD")]
HOTEL_PREFIX = ["Hotel", "The", "Grand", "Park", "Sakura", "Riverside", "Central", "Royal", "Urban", "Garden"]
HOTEL_SUFFIX = ["Plaza", "Inn", "Residence", "Suites", "Tower", "Lodge", "Hotel & Spa", "Stay", "House", "Palace"]
AMENITIES = ["Free Wi-Fi", "Breakfast", "Air conditioning", "Fitness centre", "Pool", "Spa", "Restaurant",
             "Airport shuttle", "Laundry service", "Bar"]
LONG_HAUL = {"NRT", "HND", "TYO", "ICN", "SIN", "BKK", "SYD", "DXB", "HKG", "DEL", "BOM", "PEK", "PVG"}


def _rng(engine: str, params: dict[str, Any], drift: int | None = None) -> random.Random:
    key = engine + "|" + "|".join(f"{k}={params[k]}" for k in sorted(params) if k not in {"api_key", "async", "no_cache"})
    if drift is not None:
        key += f"|d{drift}"
    return random.Random(int(hashlib.md5(key.encode()).hexdigest()[:12], 16))


def _base_rng(engine: str, params: dict[str, Any]) -> random.Random:
    return _rng(engine, params, None)


def _q(params: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        if params.get(k):
            return str(params[k])
    return default


def _meta(engine: str, params: dict) -> dict:
    sid = hashlib.md5((engine + str(sorted(params.items()))).encode()).hexdigest()[:24]
    return {
        "search_metadata": {
            "id": sid, "status": "Success",
            "json_endpoint": f"https://serpapi.com/searches/demo/{sid}.json",
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "processed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_time_taken": 1.2, "demo": True,
        },
        "search_parameters": {"engine": engine, **{k: v for k, v in params.items() if k != "api_key"}},
    }


# ---------------------------------------------------------------- travel
def _flights(p: dict, r: random.Random, drift: float) -> dict:
    dep, arr = _q(p, "departure_id", default="JFK"), _q(p, "arrival_id", default="HND")
    long_haul = arr.upper() in LONG_HAUL or dep.upper() in LONG_HAUL
    base = 640 if long_haul else 290
    out_date = _q(p, "outbound_date", default=(datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"))
    sort_price = str(p.get("sort_by")) == "2"

    def option(i: int) -> dict:
        name, code = AIRLINES[(i + r.randint(0, 9)) % len(AIRLINES)]
        stops = 0 if r.random() < 0.38 else (1 if r.random() < 0.8 else 2)
        leg_min = (780 if long_haul else 330) + r.randint(-40, 60)
        legs, lays = [], []
        cur_from = (f"{dep} International", dep)
        t = datetime.strptime(out_date + " 08:00", "%Y-%m-%d %H:%M") + timedelta(minutes=r.randint(0, 600))
        hubs = r.sample(HUBS, stops)
        for s in range(stops + 1):
            to = (hubs[s] if s < stops else (f"{arr} International", arr))
            dur = leg_min // (stops + 1) + r.randint(20, 90)
            legs.append({
                "departure_airport": {"name": cur_from[0], "id": cur_from[1], "time": t.strftime("%Y-%m-%d %H:%M")},
                "arrival_airport": {"name": to[0], "id": to[1], "time": (t + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M")},
                "duration": dur, "airplane": r.choice(["Boeing 787", "Airbus A350", "Boeing 777", "Airbus A321neo"]),
                "airline": name, "airline_logo": f"https://www.gstatic.com/flights/airline_logos/70px/{code}.png",
                "travel_class": "Economy", "flight_number": f"{code} {r.randint(10, 999)}", "legroom": f"{r.choice([30, 31, 32])} in",
            })
            if s < stops:
                lay = r.randint(55, 210)
                lays.append({"duration": lay, "name": to[0], "id": to[1]})
                t = t + timedelta(minutes=dur + lay)
            cur_from = to
        total = sum(l["duration"] for l in legs) + sum(l["duration"] for l in lays)
        price = int((base + r.randint(-120, 420) - stops * 70 + (60 if name in ("ANA", "Japan Airlines") else 0)) * drift)
        return {"flights": legs, "layovers": lays, "total_duration": total,
                "carbon_emissions": {"this_flight": 900000 + r.randint(0, 300000), "typical_for_this_route": 950000,
                                     "difference_percent": r.randint(-15, 20)},
                "price": price, "type": "Round trip", "airline_logo": legs[0]["airline_logo"],
                "departure_token": hashlib.md5(f"{dep}{arr}{i}{price}".encode()).hexdigest()}

    opts = [option(i) for i in range(9)]
    opts.sort(key=lambda o: o["price"] if sort_price else (o["price"] * 0.6 + o["total_duration"] * 0.5))
    low = min(o["price"] for o in opts)
    return {"best_flights": opts[:3], "other_flights": opts[3:],
            "price_insights": {"lowest_price": low, "price_level": r.choice(["low", "typical", "typical", "high"]),
                               "typical_price_range": [int(base * 0.85), int(base * 1.35)]}}


def _hotels(p: dict, r: random.Random, drift: float) -> dict:
    city = _q(p, "q", default="City").replace(" hotels", "").replace(" budget", "").strip()
    props = []
    seeded = _base_rng("hotelnames", {"city": city.lower()})  # same names across both hotel calls -> corroboration
    names = list({f"{seeded.choice(HOTEL_PREFIX)} {city.split()[0]} {seeded.choice(HOTEL_SUFFIX)}" for _ in range(14)})[:10]
    for i, name in enumerate(names):
        stars = r.choice([3, 3, 4, 4, 4, 5])
        nightly = int((38 + stars * 24 + seeded.randint(-20, 45) + r.randint(-8, 8)) * drift)
        props.append({
            "type": "hotel", "name": name,
            "property_token": hashlib.md5(name.encode()).hexdigest()[:20],
            "link": f"https://www.google.com/travel/hotels/entity/{hashlib.md5(name.encode()).hexdigest()[:10]}",
            "gps_coordinates": {"latitude": 35.68 + r.random() / 20, "longitude": 139.76 + r.random() / 20},
            "rate_per_night": {"lowest": f"${nightly}", "extracted_lowest": nightly},
            "total_rate": {"lowest": f"${nightly * 4}", "extracted_lowest": nightly * 4},
            "hotel_class": f"{stars}-star hotel", "extracted_hotel_class": stars,
            "overall_rating": round(min(4.9, 3.4 + stars * 0.2 + seeded.random() * 0.6), 1),
            "reviews": seeded.randint(180, 6200), "amenities": r.sample(AMENITIES, 5),
        })
    return {"properties": props}


def _maps(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="")
    if "hotel" not in q.lower() and demo_extra.is_food(q):  # venue search (LifeOps local playbook), not hotels
        return demo_extra.maps_venues(p)
    city = _q(p, "q", default="hotels in City").split(" in ")[-1]
    seeded = _base_rng("hotelnames", {"city": city.lower()})
    names = list({f"{seeded.choice(HOTEL_PREFIX)} {city.split()[0]} {seeded.choice(HOTEL_SUFFIX)}" for _ in range(14)})[:10]
    return {"local_results": [{
        "position": i + 1, "title": n, "place_id": hashlib.md5(n.encode()).hexdigest()[:16],
        "rating": round(min(4.9, 3.6 + seeded.random() * 1.2), 1), "reviews": seeded.randint(120, 5400),
        "type": "Hotel", "address": f"{r.randint(1, 9)}-{r.randint(1, 30)} {city}",
        "gps_coordinates": {"latitude": 35.68 + r.random() / 20, "longitude": 139.76 + r.random() / 20},
    } for i, n in enumerate(names[:8])]}


def _finance(p: dict, r: random.Random) -> dict:
    pair = _q(p, "q", default="USD-JPY")
    rates = {"JPY": 149.3, "EUR": 0.92, "GBP": 0.79, "INR": 83.4, "THB": 35.6, "KRW": 1345.0, "SGD": 1.35, "AUD": 1.52, "CAD": 1.37, "MXN": 17.1}
    cur = pair.split("-")[-1].upper()
    px = rates.get(cur, 1.0) * (1 + r.uniform(-0.004, 0.004))
    return {"summary": {"title": f"USD / {cur}", "stock": pair, "exchange": "Currency", "price": round(px, 4),
                        "extracted_price": round(px, 4), "currency": cur}}


# --------------------------------------------------------------- commerce
def _base_price(q: str, r: random.Random) -> float:
    ql = q.lower()
    if any(w in ql for w in ["xm5", "headphone", "airpods max", "bose"]):
        return 349
    if "monitor" in ql:
        return 299
    if "laptop" in ql or "macbook" in ql:
        return 1099
    if "earbud" in ql:
        return 28 if any(w in ql for w in ["bulk", "wholesale", "lot", "oem"]) else 79
    return 60 + r.randint(0, 140)


def _shopping(p: dict, r: random.Random, drift: float) -> dict:
    q = _q(p, "q", default="product")
    b = _base_price(q, r)
    merchants = ["Best Buy", "Walmart", "Target", "Amazon.com", "B&H Photo", "Crutchfield", "Newegg", "Costco", "eBay", "Adorama"]
    res = []
    for i, m in enumerate(r.sample(merchants, 8)):
        price = round(b * r.uniform(0.82, 1.12) * drift, 2)
        res.append({"position": i + 1, "title": f"{q} — {r.choice(['Black', 'Silver', 'Midnight', 'Standard'])}",
                    "product_id": str(r.randint(10**17, 10**18)),
                    "product_link": f"https://www.google.com/shopping/product/{r.randint(10**9, 10**10)}",
                    "source": m, "price": f"${price:,.2f}", "extracted_price": price,
                    "rating": round(r.uniform(3.9, 4.9), 1), "reviews": r.randint(40, 18000),
                    "delivery": r.choice(["Free delivery", "Free delivery by Fri", "$5.99 delivery", "Get it today"]),
                    "thumbnail": ""})
    return {"shopping_results": res}


def _amazon(p: dict, r: random.Random, drift: float) -> dict:
    q = _q(p, "k", default="product")
    b = _base_price(q, r)
    out = []
    for i in range(6):
        price = round(b * r.uniform(0.85, 1.08) * drift, 2)
        asin = "B0" + hashlib.md5(f"{q}{i}".encode()).hexdigest()[:8].upper()
        out.append({"position": i + 1, "asin": asin, "title": f"{q} {r.choice(['(Renewed)', '', 'Bundle', '2-Pack', ''])}".strip(),
                    "link_clean": f"https://www.amazon.com/dp/{asin}/", "rating": round(r.uniform(3.8, 4.8), 1),
                    "reviews": r.randint(100, 40000), "price": f"${price}", "extracted_price": price,
                    "delivery": ["FREE delivery Fri", "Or fastest delivery Tomorrow"], "sponsored": i == 0})
    return {"organic_results": out}


def _walmart(p: dict, r: random.Random, drift: float) -> dict:
    q = _q(p, "query", default="product")
    b = _base_price(q, r)
    out = []
    for i in range(5):
        price = round(b * r.uniform(0.84, 1.1) * drift, 2)
        out.append({"us_item_id": str(r.randint(10**8, 10**9)), "title": q, "rating": round(r.uniform(3.7, 4.8), 1),
                    "reviews": r.randint(20, 9000), "seller_name": r.choice(["Walmart.com", "Electronic Express", "Antonline"]),
                    "primary_offer": {"offer_price": price, "currency": "USD"},
                    "product_page_url": f"https://www.walmart.com/ip/{r.randint(10**8, 10**9)}"})
    return {"organic_results": out}


def _ebay(p: dict, r: random.Random, drift: float) -> dict:
    q = _q(p, "_nkw", default="product")
    b = _base_price(q, r)
    lot = any(w in q.lower() for w in ["wholesale", "lot", "bulk"])
    out = []
    for i in range(6):
        price = round(b * r.uniform(0.7, 1.05) * drift, 2)
        seller = f"{r.choice(['tech', 'audio', 'prime', 'shenzhen', 'global'])}_{r.choice(['depot', 'direct', 'wholesale', 'outlet'])}{r.randint(1, 99)}"
        out.append({"position": i + 1, "title": f"{q}{' — Lot of ' + str(r.choice([50, 100, 200])) if lot else ''}",
                    "link": f"https://www.ebay.com/itm/{r.randint(10**11, 10**12)}", "condition": r.choice(["Brand New", "Brand New", "Open Box", "Pre-Owned"]),
                    "price": {"raw": f"${price}", "extracted": price},
                    "seller": {"username": seller, "reviews": r.randint(50, 90000), "positive_feedback_in_percentage": round(r.uniform(95.0, 100), 1)},
                    "shipping": r.choice(["Free shipping", "+$12.00 shipping", "Free 3 day shipping"])})
    return {"organic_results": out}


SUPPLIERS = [("Shenzhen Soundwave Electronics Co.", "alibaba.com", 50), ("Dongguan AudioTech Manufacturing", "made-in-china.com", 100),
             ("Global Sources Audio OEM Ltd.", "globalsources.com", 200), ("TradeWheel Wholesale Audio", "tradewheel.com", 100),
             ("Guangzhou BlueBeat Factory", "alibaba.com", 300), ("US Wholesale Electronics Direct", "thomasnet.com", 25),
             ("Ningbo Hi-Fi Components", "dhgate.com", 20), ("Hong Kong ProAudio Supply", "globalsources.com", 500)]


def _google(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="query")
    if any(w in q.lower() for w in ["wholesale", "supplier", "oem", "factory", "manufacturer"]):
        base = _base_price(q, r)
        org = []
        for i, (name, domain, moq) in enumerate(r.sample(SUPPLIERS, 7)):
            lo = round(base * r.uniform(0.35, 0.8), 2)
            hi = round(lo * r.uniform(1.15, 1.6), 2)
            org.append({"position": i + 1, "title": f"{name} — {q.split(' wholesale')[0].split(' OEM')[0].title()}",
                        "link": f"https://www.{domain}/supplier/{hashlib.md5(name.encode()).hexdigest()[:8]}", "source": domain,
                        "snippet": f"US ${lo} - ${hi} / piece. Min. order: {moq} pieces. {r.randint(3, 15)} yrs on platform. "
                                   f"Supplier rating {round(r.uniform(4.2, 4.9), 1)}/5 ({r.randint(40, 2300)} reviews). Ships worldwide.",
                        "rich_snippet": {"top": {"detected_extensions": {"price_from": lo, "price_to": hi, "moq": moq,
                                                                         "rating": round(r.uniform(4.2, 4.9), 1), "reviews": r.randint(40, 2300)}}}})
        return {"organic_results": org}
    return {"organic_results": [{"position": i + 1, "title": f"{q.title()} — result {i + 1}", "link": f"https://example.com/{i}",
                                 "snippet": f"Information about {q}.", "source": "example.com"} for i in range(6)]}


def _news(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="topic")
    topic = q.split(" supplier")[0].split(" hiring")[0]
    heads = [f"{topic.title()} market sees record demand in Q3", f"Regulators review safety standards for {topic}",
             f"Startup raises $40M to scale {topic}", f"Supply chain shifts reshape {topic} pricing",
             f"Analysts: {topic} costs expected to fall 12% next year", f"Major recall avoided as {topic} vendor fixes defect"]
    pubs = ["Reuters", "Bloomberg", "TechCrunch", "The Verge", "Financial Times", "Nikkei Asia", "WSJ"]
    return {"news_results": [{"position": i + 1, "title": h, "link": f"https://news.example.com/{i}",
                              "source": {"name": r.choice(pubs)}, "date": f"{r.randint(1, 28)} days ago"} for i, h in enumerate(r.sample(heads, 5))]}


# ---------------------------------------------------------------- career
def _jobs(p: dict, r: random.Random) -> dict:
    role = _q(p, "q", default="Engineer")
    cos = ["Vercel", "Stripe", "Shopify", "Notion", "Linear", "Datadog", "Figma", "Airbnb", "Canva", "Supabase", "Ramp", "Plaid"]
    out = []
    for i, c in enumerate(r.sample(cos, 9)):
        lo = r.randint(120, 180)
        out.append({"title": role.replace(" remote", "").title(), "company_name": c,
                    "location": r.choice(["Anywhere", "San Francisco, CA", "New York, NY", "Remote (US)", "Austin, TX"]),
                    "via": r.choice(["LinkedIn", "Greenhouse", "Lever", "Workday", "Company site"]),
                    "description": f"{c} is hiring a {role}. You will build delightful product experiences with React, TypeScript and modern tooling.",
                    "detected_extensions": {"posted_at": f"{r.randint(1, 20)} days ago", "schedule_type": "Full-time",
                                            "salary": f"{lo}K–{lo + r.randint(20, 70)}K a year", "work_from_home": r.random() < 0.6,
                                            "health_insurance": True},
                    "apply_options": [{"title": "Apply on company site", "link": f"https://careers.{c.lower()}.com/jobs/{r.randint(1000, 9999)}"}],
                    "job_id": hashlib.md5(f"{c}{role}".encode()).hexdigest()})
    return {"jobs_results": out}


def _trends(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="react")
    v = r.randint(45, 70)
    data = []
    for w in range(52):
        v = max(10, min(100, v + r.randint(-6, 7)))
        data.append({"date": f"W{w + 1}", "values": [{"query": q, "extracted_value": v}]})
    return {"interest_over_time": {"timeline_data": data}}


# -------------------------------------------------------------- research
def _scholar(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="topic")
    authors = ["J Zhang", "M Kim", "A Gupta", "L Rossi", "S Tanaka", "K Müller", "P Okafor", "R Silva"]
    venues = ["Nature Energy", "Advanced Materials", "Joule", "ACS Nano", "Science", "Nano Letters", "Cell"]
    out = []
    min_year = int(p.get("as_ylo") or 2015)
    for i in range(8):
        yr = r.randint(min_year, 2026)
        out.append({"position": i, "title": f"{r.choice(['Mechanisms of', 'Engineering', 'Suppressing', 'Scalable', 'In-situ analysis of'])} {q} {r.choice(['via interfacial layers', 'in practical cells', 'at high current density', 'using composite electrolytes', ''])}".strip(),
                    "result_id": hashlib.md5(f"{q}{i}".encode()).hexdigest()[:12], "link": f"https://doi.org/10.1038/demo.{r.randint(1000, 9999)}",
                    "snippet": f"We report a study on {q} demonstrating significant improvements...",
                    "publication_info": {"summary": f"{', '.join(r.sample(authors, 3))} - {r.choice(venues)}, {yr}"},
                    "inline_links": {"cited_by": {"total": int(r.paretovariate(1.2) * 40)}}, "year": yr})
    return {"organic_results": out}


def _patents(p: dict, r: random.Random) -> dict:
    q = _q(p, "q", default="topic")
    assignees = ["Toyota Jidosha KK", "Samsung SDI Co Ltd", "LG Energy Solution", "QuantumScape Corp", "Panasonic IP Mgmt", "CATL", "Solid Power Inc"]
    out = []
    for i in range(7):
        pd = f"{r.randint(2014, 2025)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}"
        num = f"US{r.randint(10_000_000, 12_000_000)}B2"
        out.append({"position": i + 1, "title": f"{r.choice(['Method for', 'System and apparatus for', 'Composition for'])} {q}",
                    "patent_id": f"patent/{num}/en", "publication_number": num, "assignee": r.choice(assignees),
                    "inventor": r.choice(["Hiroshi Sato", "Jin Park", "Emily Chen", "Lars Berg"]), "priority_date": pd,
                    "publication_date": pd, "snippet": f"A {q} approach comprising a protective interlayer...",
                    "patent_link": f"https://patents.google.com/patent/{num}/en"})
    return {"organic_results": out}


def demo_response(engine: str, params: dict[str, Any], drift_bucket: int | None = None) -> dict:
    r = _rng(engine, params, drift_bucket)
    drift = 1.0 if drift_bucket is None else 1 + r.uniform(-0.06, 0.07)
    table = {
        "google_flights": lambda: _flights(params, _base_rng(engine, {k: v for k, v in params.items() if k != "sort_by"}), drift),
        "google_hotels": lambda: _hotels(params, _base_rng(engine, params), drift),
        "google_maps": lambda: _maps(params, r),
        "google_finance": lambda: _finance(params, r),
        "google_shopping": lambda: _shopping(params, _base_rng(engine, params), drift),
        "google_shopping_light": lambda: _shopping(params, _base_rng(engine, params), drift),
        "amazon": lambda: _amazon(params, _base_rng(engine, params), drift),
        "walmart": lambda: _walmart(params, _base_rng(engine, params), drift),
        "ebay": lambda: _ebay(params, _base_rng(engine, params), drift),
        "google": lambda: _google(params, r),
        "google_news": lambda: _news(params, r),
        "google_jobs": lambda: _jobs(params, r),
        "google_trends": lambda: _trends(params, r),
        "google_scholar": lambda: _scholar(params, r),
        "google_patents": lambda: _patents(params, r),
    }
    drift_r = None if drift_bucket is None else _rng(engine + ":drift", params, drift_bucket)
    extra = demo_extra.demo_extra(engine, params, drift_r)
    body = extra if extra is not None else table.get(engine, lambda: {"organic_results": []})()
    if engine == "google" and not _q(params, "q").lower().startswith("events in") and not any(w in _q(params, "q").lower() for w in ("wholesale", "supplier", "oem", "factory", "manufacturer")):
        body = demo_extra.serp("google", params, drift_r)
    return {**_meta(engine, params), **body}

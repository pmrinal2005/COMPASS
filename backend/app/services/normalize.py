"""SerpApi JSON -> normalized Candidate objects.

Field paths follow the official per-engine response docs:
  google_flights : best_flights[]/other_flights[] -> price, total_duration, flights[], layovers[], price_insights
  google_hotels  : properties[] -> name, rate_per_night.extracted_lowest, total_rate, overall_rating, reviews, extracted_hotel_class
  google_maps    : local_results[] -> title, rating, reviews, place_id
  google_shopping: shopping_results[] -> title, extracted_price, source, rating, reviews, product_link
  amazon         : organic_results[] -> asin, extracted_price, rating, reviews, link_clean
  walmart        : organic_results[] -> primary_offer.offer_price, rating, reviews, product_page_url
  ebay           : organic_results[] -> price.extracted, seller{}, condition
  google         : organic_results[] -> title, link, snippet (+rich_snippet)
  google_news    : news_results[] -> title, link, source.name, date
  google_jobs    : jobs_results[] -> title, company_name, detected_extensions, apply_options
  google_trends  : interest_over_time.timeline_data[].values[].extracted_value
  google_scholar : organic_results[] -> publication_info.summary, inline_links.cited_by.total
  google_patents : organic_results[] -> publication_number, assignee, priority_date, patent_link
  google_finance : summary.extracted_price
  bing | duckduckgo | yahoo | yandex | baidu : organic_results[] -> position, title, link, displayed_link|displayed_brand, snippet
  naver          : web_results[] -> position, title, link, displayed_link, snippet
  google_ai_mode : text_blocks[], references[] -> title, link, source, index   (+ quick_results[])
  google_ai_overview / google.ai_overview : text_blocks[], references[]  (google.ai_overview.page_token -> follow-up call)
  yelp           : organic_results[] -> title, rating, reviews, price ("$$"), neighborhoods, categories[], place_ids[]
  tripadvisor    : places[] -> place_type (RESTAURANT/HOTEL/GEO/…), title, rating, reviews, location, link
  google_events  : events_results[] -> title, date{start_date,when}, address[], venue{name,rating,reviews}, link, ticket_info[]
  airbnb         : organic_results[] -> listing_id, name, rating, reviews, extracted_price (stay total), price_qualifier, badges[]
  google_maps    : local_results[] -> title, rating, reviews, price, type, address   (category=venue -> venue candidates)
"""
from __future__ import annotations

import re
from typing import Any

from ..models import Candidate
from .entities import page_offset, price_level, serp_domain, venue_key

_MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"[\d,]+(?:\.\d+)?", str(v))
    return float(m.group().replace(",", "")) if m else None


def _days_ago(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r"(\d+)\s*(hour|day|week|month)", s)
    if not m:
        return 0.0 if "just" in s.lower() or "today" in s.lower() else None
    n, unit = int(m.group(1)), m.group(2)
    return n / 24 if unit == "hour" else n * {"day": 1, "week": 7, "month": 30}[unit]


def _venue(engine: str, platform: str, title: str, rating, reviews, price, url, **attrs) -> Candidate:
    return Candidate(title=title, category="venue", engine=engine, source=platform, url=url, rating=_num(rating),
                     reviews=int(_num(reviews) or 0),
                     attributes={"platform": platform, "price_level": price_level(price), "match_key": venue_key(title), **attrs})


def _serp_rows(engine: str, data: dict, params: dict | None) -> list[dict]:
    rows = data.get("web_results") if engine == "naver" else data.get("organic_results")
    off = page_offset(engine, params or data.get("search_parameters"))
    out = []
    for i, it in enumerate(rows or []):
        pos = it.get("position")
        pos = int(pos) if isinstance(pos, (int, float)) and pos >= 1 else i + 1
        if off and pos <= off:          # engines that restart numbering on every page
            pos += off
        out.append({"position": pos, "title": it.get("title", ""), "link": it.get("link"), "snippet": it.get("snippet", ""),
                    "domain": serp_domain(it)})
    return out


def normalize(engine: str, data: dict, category: str, params: dict | None = None) -> tuple[list[Candidate], dict]:
    """Returns (candidates, context) where context holds non-candidate signals
    (price_insights, fx rate, trend series, news, serp rows, ai text) used by the Analyst."""
    out: list[Candidate] = []
    ctx: dict[str, Any] = {}

    if engine == "google_flights":
        ctx["price_insights"] = data.get("price_insights")
        for bucket in ("best_flights", "other_flights"):
            for f in data.get(bucket, []) or []:
                legs = f.get("flights", [])
                if not legs or f.get("price") is None:
                    continue
                airlines = sorted({l.get("airline", "") for l in legs})
                route = " → ".join([legs[0]["departure_airport"]["id"]] + [l["arrival_airport"]["id"] for l in legs])
                out.append(Candidate(
                    title=f"{' / '.join(airlines)} · {route}", category="flight", engine=engine,
                    source=airlines[0] if airlines else "", price=_num(f.get("price")),
                    duration_min=_num(f.get("total_duration")),
                    url=None,
                    attributes={"stops": len(f.get("layovers", []) or []), "bucket": bucket,
                                "flight_numbers": [l.get("flight_number") for l in legs],
                                "departure": legs[0]["departure_airport"].get("time"),
                                "arrival": legs[-1]["arrival_airport"].get("time"),
                                "carbon_diff_pct": (f.get("carbon_emissions") or {}).get("difference_percent"),
                                "departure_token": f.get("departure_token"),
                                "airline_logo": f.get("airline_logo"),
                                "match_key": "|".join(l.get("flight_number", "") for l in legs)},
                ))

    elif engine == "google_hotels":
        for h in data.get("properties", []) or []:
            nightly = _num((h.get("rate_per_night") or {}).get("extracted_lowest"))
            if nightly is None:
                continue
            out.append(Candidate(
                title=h.get("name", "Hotel"), category="hotel", engine=engine, source="Google Hotels",
                url=h.get("link"), price=nightly, rating=_num(h.get("overall_rating")), reviews=int(h.get("reviews") or 0),
                attributes={"nightly": nightly, "total_rate": _num((h.get("total_rate") or {}).get("extracted_lowest")),
                            "stars": h.get("extracted_hotel_class"), "amenities": h.get("amenities", [])[:6],
                            "property_token": h.get("property_token"), "gps": h.get("gps_coordinates"),
                            "match_key": h.get("name", "").lower()},
            ))

    elif engine == "google_maps" and category == "venue":
        results = data.get("local_results") or ([data["place_results"]] if data.get("place_results") else [])
        for p in results:
            out.append(_venue(engine, "Google Maps", p.get("title", ""), p.get("rating"), p.get("reviews"), p.get("price"),
                              p.get("link") or (f"https://www.google.com/maps/place/?q=place_id:{p['place_id']}" if p.get("place_id") else None),
                              address=p.get("address"), place_id=p.get("place_id"), kind=p.get("type"), gps=p.get("gps_coordinates")))

    elif engine == "google_maps":
        results = data.get("local_results") or ([data["place_results"]] if data.get("place_results") else [])
        for p in results:
            out.append(Candidate(title=p.get("title", ""), category="place", engine=engine, source="Google Maps",
                                 rating=_num(p.get("rating")), reviews=int(p.get("reviews") or 0),
                                 attributes={"address": p.get("address"), "place_id": p.get("place_id"),
                                             "type": p.get("type"), "match_key": p.get("title", "").lower()}))

    elif engine == "google_finance":
        s = data.get("summary") or {}
        ctx["fx"] = {"pair": s.get("stock") or s.get("title"), "rate": _num(s.get("extracted_price") or s.get("price")),
                     "currency": s.get("currency")}

    elif engine in ("google_shopping", "google_shopping_light"):
        for it in (data.get("shopping_results") or []) + (data.get("inline_shopping_results") or []):
            price = _num(it.get("extracted_price") or it.get("price"))
            if price is None:
                continue
            out.append(Candidate(title=it.get("title", ""), category=category if category != "generic" else "product",
                                 engine=engine, source=it.get("source", ""), url=it.get("product_link") or it.get("link"),
                                 price=price, rating=_num(it.get("rating")), reviews=int(it.get("reviews") or 0),
                                 attributes={"delivery": it.get("delivery"), "product_id": it.get("product_id"),
                                             "thumbnail": it.get("thumbnail")}))

    elif engine == "amazon":
        for it in data.get("organic_results", []) or []:
            price = _num(it.get("extracted_price") or it.get("price"))
            if price is None:
                continue
            out.append(Candidate(title=it.get("title", ""), category="product", engine=engine, source="Amazon",
                                 url=it.get("link_clean") or it.get("link"), price=price, rating=_num(it.get("rating")),
                                 reviews=int(it.get("reviews") or 0),
                                 attributes={"asin": it.get("asin"), "sponsored": bool(it.get("sponsored")),
                                             "delivery": (it.get("delivery") or [None])[0] if isinstance(it.get("delivery"), list) else it.get("delivery")}))

    elif engine == "walmart":
        for it in data.get("organic_results", []) or []:
            price = _num((it.get("primary_offer") or {}).get("offer_price"))
            if price is None:
                continue
            out.append(Candidate(title=it.get("title", ""), category="product", engine=engine, source="Walmart",
                                 url=it.get("product_page_url"), price=price, rating=_num(it.get("rating")),
                                 reviews=int(it.get("reviews") or 0),
                                 attributes={"seller": it.get("seller_name"), "us_item_id": it.get("us_item_id")}))

    elif engine == "ebay":
        for it in data.get("organic_results", []) or []:
            pr = it.get("price") or {}
            price = _num(pr.get("extracted") if isinstance(pr, dict) else pr)
            if price is None:
                continue
            seller = it.get("seller") or {}
            fb = _num(seller.get("positive_feedback_in_percentage"))
            lot = re.search(r"lot of (\d+)", it.get("title", ""), re.I)
            out.append(Candidate(title=it.get("title", ""), category="product", engine=engine,
                                 source=f"eBay · {seller.get('username', 'seller')}", url=it.get("link"), price=price,
                                 rating=round(fb / 20, 2) if fb else None, reviews=int(seller.get("reviews") or 0),
                                 attributes={"condition": it.get("condition"), "shipping": it.get("shipping"),
                                             "lot_size": int(lot.group(1)) if lot else None}))

    elif engine == "google" and category == "serp":
        for r in _serp_rows(engine, data, params)[:20]:
            out.append(Candidate(title=r["title"], category="serp", engine=engine, source=r["domain"], url=r["link"],
                                 attributes={"position": r["position"], "domain": r["domain"], "snippet": r["snippet"]}))
        aio = data.get("ai_overview") or {}
        if aio.get("page_token") and not aio.get("text_blocks"):
            ctx["ai_overview_token"] = aio["page_token"]          # expires within 1 minute -> follow-up call right away
        for i, ref in enumerate(aio.get("references") or []):
            out.append(Candidate(title=ref.get("title", ""), category="ai_citation", engine="google_ai_overview", source=serp_domain(ref),
                                 url=ref.get("link"), attributes={"domain": serp_domain(ref), "index": ref.get("index", i), "via": "ai_overview"}))
        if aio.get("text_blocks"):
            ctx["ai_overview_text"] = " ".join(b.get("snippet", "") for b in aio["text_blocks"] if b.get("snippet"))[:600]

    elif engine in ("bing", "duckduckgo", "yahoo", "yandex", "baidu", "naver"):
        for r in _serp_rows(engine, data, params)[:20]:
            out.append(Candidate(title=r["title"], category="serp", engine=engine, source=r["domain"], url=r["link"],
                                 attributes={"position": r["position"], "domain": r["domain"], "snippet": r["snippet"]}))

    elif engine in ("google_ai_mode", "google_ai_overview"):
        block = data.get("ai_overview") if engine == "google_ai_overview" else data
        block = block or {}
        refs = block.get("references") or []
        for i, ref in enumerate(refs):
            out.append(Candidate(title=ref.get("title", ""), category="ai_citation", engine=engine, source=serp_domain(ref), url=ref.get("link"),
                                 attributes={"domain": serp_domain(ref), "index": ref.get("index", i), "via": engine,
                                             "snippet": ref.get("snippet", "")}))
        txt = block.get("reconstructed_markdown") or " ".join(b.get("snippet", "") for b in (block.get("text_blocks") or []) if b.get("snippet"))
        if txt:
            ctx.setdefault("ai_text", {})[engine] = txt[:600]

    elif engine == "yelp":
        for it in data.get("organic_results", []) or []:
            out.append(_venue(engine, "Yelp", it.get("title", ""), it.get("rating"), it.get("reviews"), it.get("price"), it.get("link"),
                              neighborhood=it.get("neighborhoods"), categories=[c.get("title") for c in it.get("categories", [])],
                              snippet=it.get("snippet", ""), place_ids=it.get("place_ids")))

    elif engine == "tripadvisor":
        for it in data.get("places", []) or []:
            ptype = (it.get("place_type") or "").upper()
            if ptype in ("GEO",) or not it.get("title"):
                continue                      # destinations are context, not candidates
            if category == "venue" and ptype not in ("RESTAURANT", ""):
                continue
            out.append(_venue(engine, "Tripadvisor", it.get("title", ""), it.get("rating"), it.get("reviews"), None, it.get("link"),
                              location=it.get("location"), place_type=ptype, description=(it.get("description") or "")[:240]))

    elif engine == "google_events":
        for it in data.get("events_results", []) or []:
            date = it.get("date") or {}
            venue = it.get("venue") or {}
            out.append(Candidate(title=it.get("title", ""), category="event", engine=engine, source=venue.get("name") or ", ".join(it.get("address") or []),
                                 url=it.get("link"), rating=_num(venue.get("rating")), reviews=int(_num(venue.get("reviews")) or 0),
                                 attributes={"when": date.get("when"), "start": date.get("start_date"), "address": it.get("address"),
                                             "venue": venue.get("name"), "description": (it.get("description") or "")[:240],
                                             "tickets": [t.get("source") for t in it.get("ticket_info", [])][:3],
                                             "match_key": venue_key(venue.get("name") or it.get("title", ""))}))

    elif engine == "airbnb":
        for it in data.get("organic_results", []) or []:
            total = _num(it.get("extracted_price"))
            if total is None:
                continue
            out.append(Candidate(title=it.get("name") or it.get("title", "Airbnb stay"), category="stay", engine=engine, source="Airbnb",
                                 url=it.get("link"), price=total, rating=_num(it.get("rating")), reviews=int(_num(it.get("reviews")) or 0),
                                 attributes={"listing_id": it.get("listing_id"), "qualifier": it.get("price_qualifier"),
                                             "badges": it.get("badges", []), "bedrooms": it.get("bedrooms"), "beds": it.get("beds"),
                                             "free_cancellation": it.get("free_cancellation"), "gps": it.get("gps_coordinates"),
                                             "match_key": "airbnb:" + str(it.get("listing_id"))}))

    elif engine == "google":
        for it in data.get("organic_results", []) or []:
            ext = (((it.get("rich_snippet") or {}).get("top") or {}).get("detected_extensions") or {})
            snip = it.get("snippet", "")
            moq = ext.get("moq") or _num((re.search(r"Min\. order:\s*([\d,]+)", snip) or [None, None])[1])
            price_from = ext.get("price_from") or _num((_MONEY.search(snip) or [None, None])[1])
            rating = ext.get("rating") or _num((re.search(r"rating\s*([\d.]+)", snip) or [None, None])[1])
            reviews = ext.get("reviews") or _num((re.search(r"\(([\d,]+) reviews\)", snip) or [None, None])[1])
            out.append(Candidate(title=it.get("title", ""), category=category, engine=engine,
                                 source=it.get("source") or (it.get("displayed_link") or ""), url=it.get("link"),
                                 price=_num(price_from), rating=_num(rating), reviews=int(reviews or 0),
                                 attributes={"snippet": snip, "moq": _num(moq), "price_to": _num(ext.get("price_to"))}))

    elif engine == "google_news":
        ctx["news"] = [{"title": n.get("title"), "source": (n.get("source") or {}).get("name") if isinstance(n.get("source"), dict) else n.get("source"),
                        "link": n.get("link"), "date": n.get("date")} for n in (data.get("news_results") or [])[:8]]
        for n in ctx["news"]:
            out.append(Candidate(title=n["title"] or "", category="news", engine=engine, source=n["source"] or "", url=n["link"],
                                 attributes={"date": n["date"], "age_days": _days_ago(n["date"])}))

    elif engine == "google_jobs":
        for j in data.get("jobs_results", []) or []:
            ext = j.get("detected_extensions") or {}
            sal = ext.get("salary")
            nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*K", sal or "")]
            out.append(Candidate(title=f"{j.get('title')} · {j.get('company_name')}", category="job", engine=engine,
                                 source=j.get("via", ""), url=((j.get("apply_options") or [{}])[0]).get("link"),
                                 price=(sum(nums) / len(nums) * 1000) if nums else None,
                                 attributes={"company": j.get("company_name"), "location": j.get("location"),
                                             "salary": sal, "posted": ext.get("posted_at"), "age_days": _days_ago(ext.get("posted_at")),
                                             "remote": bool(ext.get("work_from_home")), "schedule": ext.get("schedule_type"),
                                             "description": (j.get("description") or "")[:400], "job_id": j.get("job_id")}))

    elif engine == "google_trends":
        series = []
        for pt in ((data.get("interest_over_time") or {}).get("timeline_data") or []):
            vals = pt.get("values") or [{}]
            series.append(_num(vals[0].get("extracted_value")) or 0)
        ctx["trend"] = series

    elif engine == "google_scholar":
        for it in data.get("organic_results", []) or []:
            summ = (it.get("publication_info") or {}).get("summary", "")
            yr = it.get("year") or _num((re.search(r"(19|20)\d{2}", summ) or [None])[0] if re.search(r"(19|20)\d{2}", summ) else None)
            out.append(Candidate(title=it.get("title", ""), category="paper", engine=engine, source=summ.split(" - ")[-1] if summ else "Scholar",
                                 url=it.get("link"),
                                 attributes={"cited_by": int(((it.get("inline_links") or {}).get("cited_by") or {}).get("total") or 0),
                                             "year": int(yr) if yr else None, "authors": summ.split(" - ")[0] if summ else "",
                                             "snippet": it.get("snippet", "")}))

    elif engine == "google_patents":
        for it in data.get("organic_results", []) or []:
            pd = it.get("priority_date") or it.get("publication_date") or ""
            out.append(Candidate(title=it.get("title", ""), category="patent", engine=engine, source=it.get("assignee", ""),
                                 url=it.get("patent_link") or f"https://patents.google.com/{it.get('patent_id', '')}",
                                 attributes={"number": it.get("publication_number"), "priority_date": pd,
                                             "year": int(pd[:4]) if pd[:4].isdigit() else None,
                                             "inventor": it.get("inventor"), "snippet": it.get("snippet", "")}))

    return out, ctx

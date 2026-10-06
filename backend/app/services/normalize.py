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
"""
from __future__ import annotations

import re
from typing import Any

from ..models import Candidate

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


def normalize(engine: str, data: dict, category: str) -> tuple[list[Candidate], dict]:
    """Returns (candidates, context) where context holds non-candidate signals
    (price_insights, fx rate, trend series, news) used by the Analyst."""
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

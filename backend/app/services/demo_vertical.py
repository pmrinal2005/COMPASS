"""Demo Mode payloads for the vertical engines added for dynamic intent routing.

Each payload mirrors the documented SerpApi response shape of its engine (field names verified
against the official docs samples in tests/fixtures/ and the live API):

  youtube                       -> video_results[{title,link,video_id,channel{name,verified},views,length,published_date}]
  google_videos                 -> video_results[{title,link,duration,rich_snippet.top.extensions[channel,age]}]
  google_short_videos           -> short_video_results[{title,link,channel,duration,source}]
  google_news_light             -> news_results[{title,link,source,date}]
  google_trends_trending_now    -> trending_searches[{query,search_volume,increase_percentage,categories[],active}]
  google_finance_markets        -> markets{us|europe|asia|crypto|...: [{name,stock,price,price_movement{percentage,value,movement}}]}
  google_travel_explore         -> destinations[{name,destination_airport{code},flight_price,hotel_price,flight_duration,number_of_stops,airline}]
  google_light                  -> organic_results[{position,title,link,displayed_link,snippet}]

Payloads are seeded by the query so the same topic yields the same universe across calls (stable
corroboration in Demo Mode), with small drift for re-plans.
"""
from __future__ import annotations

import random
from typing import Any

from .demo_data import _q, _rng

_TOPIC_HEADS = [
    "Official {t} video", "{t} explained in 10 minutes", "Top 10 {t} moments", "{t} live performance",
    "Why everyone is talking about {t}", "{t} review", "The best of {t}", "{t} behind the scenes",
]
_ANGLES = ["Official video", "explained in 10 minutes", "top 10 moments", "live performance", "the full story",
           "review", "best of", "behind the scenes", "reaction", "first listen", "remix", "lyrics breakdown"]
_CHANNELS = ["Music Hub", "Daily Culture", "Global Beats", "Chart Check", "Screen Dive", "Night Session", "Trend Lab", "Studio Mix"]
_PUBLISHERS = ["Reuters", "Bloomberg", "The Verge", "Financial Times", "Nikkei Asia", "Al Jazeera", "BBC News", "Associated Press"]


def _topic(p: dict, default: str = "trending topic") -> str:
    return (_q(p, "search_query", "q", default=default) or default).strip()


def youtube(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    rows = []
    for i, ang in enumerate(r.sample(_ANGLES, 8)):
        head = f"{t.title()}: {ang}"
        rows.append({"position_on_page": i + 1, "title": head, "link": f"https://www.youtube.com/watch?v=demo{i:03d}",
                     "video_id": f"demo{i:03d}", "channel": {"name": r.choice(_CHANNELS), "verified": r.random() < 0.5},
                     "published_date": r.choice(["2 days ago", "1 week ago", "3 weeks ago", "1 month ago"]),
                     "views": r.randint(20_000, 9_000_000), "length": f"{r.randint(2, 14)}:{r.randint(10, 59)}"})
    return {"search_information": {"total_results": 128000, "video_results_state": "Results for exact spelling"}, "video_results": rows}


def google_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    rows = []
    for i, ang in enumerate(r.sample(_ANGLES, 8)):
        rows.append({"position": i + 1, "title": f"{t.title()}: {ang}", "link": f"https://www.youtube.com/watch?v=gv{i:03d}",
                     "duration": f"{r.randint(2, 14)}:{r.randint(10, 59)}",
                     "rich_snippet": {"top": {"extensions": ["YouTube", r.choice(_CHANNELS), r.choice(["2 days ago", "1 week ago"])]}},
                     "snippet": f"Watch the latest on {t}."})
    return {"search_information": {"organic_results_state": "Results for exact spelling"}, "video_results": rows}


def google_short_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    rows = []
    for i, ang in enumerate(r.sample(_ANGLES, 10)):
        rows.append({"position": i + 1, "title": f"{t.title()} {ang} #shorts", "link": f"https://www.youtube.com/shorts/sh{i:03d}",
                     "channel": r.choice(_CHANNELS), "duration": f"0:{r.randint(15, 59)}", "source": "YouTube"})
    return {"search_information": {"organic_results_state": "Results for exact spelling"}, "short_video_results": rows}


def google_news_light(p: dict, r: random.Random) -> dict:
    t = _topic(p, "world news")
    heads = [f"{t.title()} draws fresh attention as officials respond", f"Analysts weigh in on {t} outlook",
             f"New data points to shifts in {t}", f"Coverage of {t} widens across regions"]
    return {"news_results": [{"position": i + 1, "title": h, "link": f"https://news.example.com/light/{i}",
                              "source": r.choice(_PUBLISHERS), "date": f"{r.randint(1, 20)} hours ago"}
                             for i, h in enumerate(r.sample(heads, len(heads)))]}


def google_trends_trending_now(p: dict, r: random.Random) -> dict:
    geo = str(p.get("geo") or "US").upper()
    seeds = ["cricket world cup", "budget 2026", "new smartphone launch", "monsoon forecast", "stock market today",
             "film release", "election results", "ai chatbot", "space mission", "football transfer news"]
    rows = []
    for i, term in enumerate(r.sample(seeds, 8)):
        rows.append({"query": term, "active": i < 5, "search_volume": r.randint(20_000, 2_000_000),
                     "increase_percentage": r.choice([150, 300, 500, 1000, 2000]),
                     "categories": [{"id": 3, "name": r.choice(["News", "Sports", "Finance", "Entertainment"])}],
                     "trend_breakdown": [f"{term} news", f"{term} today"],
                     "serpapi_google_trends_link": f"https://trends.google.com/trends/explore?q={term.replace(' ', '+')}&geo={geo}"})
    return {"search_parameters": {"engine": "google_trends_trending_now", "geo": geo}, "trending_searches": rows}


def google_finance_markets(p: dict, r: random.Random) -> dict:
    def row(name: str, stock: str, base: float) -> dict:
        ch = round(r.uniform(-1.6, 1.6), 3)
        price = round(base * (1 + ch / 100), 2)
        return {"name": name, "stock": stock, "link": f"https://www.google.com/finance/quote/{stock}",
                "price": price, "price_movement": {"percentage": ch, "value": round(price - base, 2), "movement": "Up" if ch >= 0 else "Down"}}
    return {"markets": {
        "us": [row("Dow Jones", ".DJI:INDEXDJX", 51000), row("S&P 500", ".INX:INDEXSP", 7580), row("Nasdaq", ".IXIC:INDEXNASDAQ", 26970)],
        "europe": [row("FTSE 100", "UKX:INDEXFTSE", 9600), row("DAX", "DAX:INDEXDB", 24000)],
        "asia": [row("Nikkei 225", "NI225:INDEXNIKKEI", 49000), row("Nifty 50", "NIFTY_50:INDEXNSE", 26400)],
        "crypto": [row("Bitcoin", "BTC-USD", 97000)],
    }, "search_parameters": {"engine": "google_finance_markets", "trend": p.get("trend", "indexes")}}


def google_travel_explore(p: dict, r: random.Random) -> dict:
    dests = [("Los Angeles", "LAX", "Frontier", "F9", "United States"), ("Miami", "MIA", "Spirit", "NK", "United States"),
             ("Santa Barbara", "SBA", "Frontier", "F9", "United States"), ("Las Vegas", "LAS", "Southwest", "WN", "United States"),
             ("Cancun", "CUN", "Viva Aerobus", "VB", "Mexico"), ("Denver", "DEN", "Spirit", "NK", "United States")]
    rows = []
    for name, code, airline, acode, country in dests:
        fp = r.randint(60, 420)
        rows.append({"destination_id": f"/m/{code.lower()}", "name": name, "country": country,
                     "destination_airport": {"code": code}, "start_date": "2026-12-06", "end_date": "2026-12-13",
                     "flight_price": fp, "hotel_price": r.randint(110, 320), "flight_duration": r.randint(120, 480),
                     "number_of_stops": r.choice([0, 0, 1]), "airline": airline, "airline_code": acode,
                     "link": "https://www.google.com/travel/explore", "gps_coordinates": {"latitude": 34.0, "longitude": -118.2}})
    return {"search_parameters": {"engine": "google_travel_explore", "departure_id": p.get("departure_id"), "currency": "USD"}, "destinations": rows}


def google_light(p: dict, r: random.Random) -> dict:
    t = _topic(p, "web search")
    doms = ["wikipedia.org", "britannica.com", "nytimes.com", "reuters.com", "bbc.com", "github.com"]
    return {"organic_results": [{"position": i + 1, "title": f"{t.title()} - {d.split('.')[0].title()}", "link": f"https://www.{d}/{t.replace(' ', '-')}",
                                 "displayed_link": f"https://www.{d}", "snippet": f"Overview of {t} from {d}."}
                                for i, d in enumerate(r.sample(doms, 5))]}


TABLE = {
    "youtube": youtube,
    "google_videos": google_videos,
    "google_short_videos": google_short_videos,
    "google_news_light": google_news_light,
    "google_trends_trending_now": google_trends_trending_now,
    "google_finance_markets": google_finance_markets,
    "google_travel_explore": google_travel_explore,
    "google_light": google_light,
}


def vertical_demo(engine: str, p: dict[str, Any], drift_r: random.Random | None) -> dict | None:
    """Return a demo payload for a vertical engine, else None (handled by the caller)."""
    fn = TABLE.get(engine)
    if fn is None:
        return None
    r = drift_r or _rng(engine, p)
    return fn(p, r)

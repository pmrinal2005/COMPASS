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

import hashlib
import random
import re
from typing import Any

from .demo_data import _q, _rng

_RECENCY_WORDS = re.compile(r"\b(latest|newest|recent|breaking|today|this\s+week|just\s+out|trending)\b", re.I)
_CREATOR_Q = re.compile(r"\b(?i:(?:latest|new|recent|all)?)\s*([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\s+(?i:(videos?|songs?|shorts|channel|uploads?|streams?|music))\b")


def _fresh_dates(r: random.Random, topic: str, n: int) -> list[str]:
    """Freshness-aware publish dates: recency-flagged queries surface hours-old uploads first,
    plain queries the usual weeks-old mix — mirroring live YouTube ordering."""
    if _RECENCY_WORDS.search(topic):
        pool = ["3 hours ago", "9 hours ago", "1 day ago", "2 days ago", "4 days ago", "1 week ago"]
    else:
        pool = ["2 days ago", "1 week ago", "3 weeks ago", "1 month ago"]
    return [pool[0]] + [r.choice(pool) for _ in range(n - 1)] if n else []


def _creator(topic: str) -> str | None:
    m = _CREATOR_Q.search(topic)
    return m.group(1).strip() if m else None

_TOPIC_HEADS = [
    "Official {t} video", "{t} explained in 10 minutes", "Top 10 {t} moments", "{t} live performance",
    "Why everyone is talking about {t}", "{t} review", "The best of {t}", "{t} behind the scenes",
]
_ANGLES = ["Official video", "explained in 10 minutes", "top 10 moments", "live performance", "the full story",
           "review", "best of", "behind the scenes", "reaction", "first listen", "remix", "lyrics breakdown"]
def _shared_angles(topic: str) -> list[str]:
    """Deterministic per-topic angle order so the same videos recur across engines (like live YouTube / Google Videos)."""
    return random.Random(topic).sample(_ANGLES, len(_ANGLES))


_CHANNELS = ["Music Hub", "Daily Culture", "Global Beats", "Chart Check", "Screen Dive", "Night Session", "Trend Lab", "Studio Mix"]
_PUBLISHERS = ["Reuters", "Bloomberg", "The Verge", "Financial Times", "Nikkei Asia", "Al Jazeera", "BBC News", "Associated Press"]


def _topic(p: dict, default: str = "trending topic") -> str:
    return (_q(p, "search_query", "q", default=default) or default).strip()


def youtube(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    dates = _fresh_dates(r, t, 8)
    rows = []
    for i, ang in enumerate(_shared_angles(t)[:8]):
        head = f"{t.title()}: {ang}"
        rows.append({"position_on_page": i + 1, "title": head, "link": f"https://www.youtube.com/watch?v=demo{i:03d}",
                     "video_id": f"demo{i:03d}", "channel": {"name": r.choice(_CHANNELS), "verified": r.random() < 0.5},
                     "published_date": dates[i], "views": r.randint(20_000, 9_000_000),
                     "length": f"{r.randint(2, 14)}:{r.randint(10, 59)}"})
    body: dict[str, Any] = {"search_information": {"total_results": 128000, "video_results_state": "Results for exact spelling"},
                            "video_results": rows}
    creator = _creator(t)
    if creator:  # live YouTube search returns channel_results[] for creator queries -> drives the channel follow-up
        handle = creator.replace(" ", "")
        body["channel_results"] = [{"position_on_page": 1, "title": creator, "link": f"https://www.youtube.com/@{handle}",
                                    "verified": True, "handle": f"@{handle}", "subscribers": r.randint(5_000_000, 90_000_000),
                                    "description": f"The official {creator} channel."}]
    return body


def google_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    dates = _fresh_dates(r, t, 8)
    rows = []
    for i, ang in enumerate(_shared_angles(t)[:8]):
        rows.append({"position": i + 1, "title": f"{t.title()}: {ang}", "link": f"https://www.youtube.com/watch?v=gv{i:03d}",
                     "duration": f"{r.randint(2, 14)}:{r.randint(10, 59)}",
                     "rich_snippet": {"top": {"extensions": ["YouTube", r.choice(_CHANNELS), dates[i]]}},
                     "snippet": f"Watch the latest on {t}."})
    return {"search_information": {"organic_results_state": "Results for exact spelling"}, "video_results": rows}


def google_short_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    rows = []
    for i, ang in enumerate(_shared_angles(t)[:10]):
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


def youtube_channel(p: dict, r: random.Random) -> dict:
    handle = str(p.get("channel_id") or "DemoCreator").lstrip("@")
    title = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", handle).replace("_", " ").title()
    dates = _fresh_dates(r, "latest uploads", 8)
    vids = []
    for i in range(8):
        vids.append({"position_on_page": i + 1, "title": f"{title} — new upload #{i + 1}",
                     "link": f"https://www.youtube.com/watch?v=ch{hashlib.md5(handle.encode()).hexdigest()[:4]}{i:02d}",
                     "video_id": f"ch{hashlib.md5(handle.encode()).hexdigest()[:4]}{i:02d}",
                     "channel": {"name": title, "verified": True}, "published_date": dates[i],
                     "views": r.randint(50_000, 12_000_000), "length": f"{r.randint(3, 22)}:{r.randint(10, 59)}"})
    return {"channel_results": {"title": title, "handle": f"@{handle}", "link": f"https://www.youtube.com/@{handle}",
                                "subscribers": r.randint(5_000_000, 90_000_000), "video_count": r.randint(400, 4000),
                                "description": f"The official {title} channel."},
            "videos_results": vids}


def bing_news(p: dict, r: random.Random) -> dict:
    t = _topic(p, "world news")
    heads = [f"{t.title()}: officials confirm new developments", f"What the latest {t} data means",
             f"{t.title()} coverage widens as analysts react", f"Explainer: the {t} story so far",
             f"Markets respond to {t} headlines"]
    return {"organic_results": [{"title": h, "link": f"https://news.example.com/bing/{i}", "source": r.choice(_PUBLISHERS),
                                 "date": f"{r.randint(1, 20)}h", "snippet": f"Latest on {t}: {h.lower()}."}
                                for i, h in enumerate(r.sample(heads, 5))]}


def duckduckgo_news(p: dict, r: random.Random) -> dict:
    t = _topic(p, "world news")
    heads = [f"{t.title()} draws fresh attention as officials respond", f"New data points to shifts in {t}",
             f"Analysts weigh in on {t} outlook", f"Coverage of {t} widens across regions",
             f"{t.title()}: what changed this week"]
    return {"news_results": [{"position": i + 1, "title": h, "link": f"https://news.example.com/ddg/{i}",
                              "source": r.choice(_PUBLISHERS), "date": f"{r.randint(1, 30)} hours ago",
                              "snippet": f"Full story: {h.lower()}."} for i, h in enumerate(r.sample(heads, 5))]}


def google_images(p: dict, r: random.Random) -> dict:
    t = _topic(p, "sunset landscape")
    srcs = ["Unsplash", "Pexels", "Wikimedia Commons", "Flickr", "Getty Images", "Pixabay"]
    rows = []
    for i in range(10):
        w, h = r.choice([(1920, 1080), (3840, 2160), (1080, 1350), (2500, 1600), (1200, 800)])
        rows.append({"position": i + 1, "title": f"{t.title()} — photo {i + 1}", "source": r.choice(srcs),
                     "link": f"https://images.example.com/{t.replace(' ', '-')}/{i}",
                     "original": f"https://images.example.com/{t.replace(' ', '-')}/{i}.jpg",
                     "original_width": w, "original_height": h, "is_product": False,
                     "thumbnail": f"https://images.example.com/{t.replace(' ', '-')}/{i}_thumb.jpg"})
    return {"search_information": {"organic_results_state": "Results for exact spelling"}, "images_results": rows}


def bing_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    dates = _fresh_dates(r, t, 6)
    rows = []
    for i, ang in enumerate(_shared_angles(t)[:6]):
        rows.append({"position": i + 1, "title": f"{t.title()}: {ang}", "link": f"https://www.youtube.com/watch?v=bv{i:03d}",
                     "source": r.choice(_CHANNELS), "duration": f"{r.randint(2, 14)}:{r.randint(10, 59)}",
                     "views": f"{r.randint(20, 9000)}K views", "extracted_views": r.randint(20_000, 9_000_000),
                     "published_date": dates[i]})
    return {"video_results": rows}


def yahoo_videos(p: dict, r: random.Random) -> dict:
    t = _topic(p, "trending songs")
    rows = []
    for i, ang in enumerate(_shared_angles(t)[:6]):
        rows.append({"position": i + 1, "title": f"{t.title()}: {ang}", "link": f"https://www.youtube.com/watch?v=yv{i:03d}",
                     "source": r.choice(_CHANNELS), "duration": f"{r.randint(2, 14)}:{r.randint(10, 59)}",
                     "views": f"{r.randint(10, 5000)}K views", "extracted_views": r.randint(10_000, 5_000_000)})
    return {"videos_results": rows}


def google_flights_deals(p: dict, r: random.Random) -> dict:
    origin = str(p.get("departure_id") or "JFK")
    dests = [("Lisbon", "LIS", "Portugal", "TAP Air Portugal", "TP"), ("Barcelona", "BCN", "Spain", "Iberia", "IB"),
             ("Tokyo", "HND", "Japan", "ANA", "NH"), ("Cancun", "CUN", "Mexico", "JetBlue", "B6"),
             ("London", "LHR", "United Kingdom", "Virgin Atlantic", "VS"), ("Bali", "DPS", "Indonesia", "Singapore Airlines", "SQ")]
    rows = []
    for name, code, country, airline, acode in r.sample(dests, 5):
        price = r.randint(180, 720)
        rows.append({"name": name, "country": country, "price": price, "average_price": int(price * r.uniform(1.3, 2.1)),
                     "discount_percentage": r.randint(25, 55),
                     "flight_link": f"https://www.google.com/travel/flights?q={origin}-{code}", "thumbnail": "",
                     "start_date": "2026-12-06", "end_date": "2026-12-13", "departure_airport_code": origin,
                     "arrival_airport_code": code, "flight_duration": r.randint(180, 780), "stops": r.choice([0, 0, 1]),
                     "airline": airline, "airline_code": acode})
    return {"departure_informations": {"airport_code": origin}, "deals": rows}


_APP_MAKERS = ["Calm Studio", "Pixel Labs", "Northwind Apps", "Bright Mobile", "Indie Forge", "Osmo Interactive"]


def google_play(p: dict, r: random.Random) -> dict:
    t = _topic(p, "meditation")
    items = []
    for i in range(8):
        dl = r.choice(["10,000,000+", "5,000,000+", "1,000,000+", "500,000+", "100,000+"])
        items.append({"title": f"{t.title()} {r.choice(['Pro', 'Plus', 'Go', 'Daily', 'Studio', 'Max', 'Lite', 'Hub'])}",
                      "link": f"https://play.google.com/store/apps/details?id=com.demo.{t.replace(' ', '')}{i}",
                      "product_id": f"com.demo.{t.replace(' ', '')}{i}", "rating": round(r.uniform(3.9, 4.9), 1),
                      "author": r.choice(_APP_MAKERS), "category": r.choice(["Health & Fitness", "Productivity", "Lifestyle"]),
                      "downloads": dl, "thumbnail": "", "description": f"A top-rated {t} app with guided sessions."})
    return {"organic_results": [{"items": items}]}


def apple_app_store(p: dict, r: random.Random) -> dict:
    t = str(p.get("term") or "meditation")
    rows = []
    for i in range(7):
        rows.append({"position": i + 1, "title": f"{t.title()} {r.choice(['Pro', 'Plus', 'Go', 'Daily', 'Studio', 'Max', 'Lite'])}",
                     "bundle_id": f"com.demo.{t.replace(' ', '')}{i}", "version": f"{r.randint(1, 9)}.{r.randint(0, 9)}.0",
                     "link": f"https://apps.apple.com/us/app/id100000{i}", "price": {"type": "Free"},
                     "rating": [{"type": "All Times", "rating": round(r.uniform(3.9, 4.9), 2), "count": r.randint(2000, 900000)}],
                     "genres": [{"name": r.choice(["Health & Fitness", "Productivity", "Lifestyle"]), "primary": True}],
                     "developer": {"name": r.choice(_APP_MAKERS)}, "age_rating": "4+",
                     "description": f"A top-rated {t} app with guided sessions."})
    return {"organic_results": rows}


TABLE = {
    "youtube": youtube,
    "youtube_channel": youtube_channel,
    "google_videos": google_videos,
    "google_short_videos": google_short_videos,
    "bing_videos": bing_videos,
    "yahoo_videos": yahoo_videos,
    "google_news_light": google_news_light,
    "bing_news": bing_news,
    "duckduckgo_news": duckduckgo_news,
    "google_images": google_images,
    "google_trends_trending_now": google_trends_trending_now,
    "google_finance_markets": google_finance_markets,
    "google_travel_explore": google_travel_explore,
    "google_flights_deals": google_flights_deals,
    "google_play": google_play,
    "apple_app_store": apple_app_store,
    "google_light": google_light,
}


def vertical_demo(engine: str, p: dict[str, Any], drift_r: random.Random | None) -> dict | None:
    """Return a demo payload for a vertical engine, else None (handled by the caller)."""
    fn = TABLE.get(engine)
    if fn is None:
        return None
    r = drift_r or _rng(engine, p)
    return fn(p, r)

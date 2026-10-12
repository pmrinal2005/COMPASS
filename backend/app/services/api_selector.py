"""API Selector — sends every user prompt to Groq (Gemini fallback) to
select the minimal set of SerpApi engines from the available catalogue
BEFORE playbook classification runs. This fixes the keyword-bias bug
where "ticket fares for trip to Odisha ... best deals" was misclassified
as shopping because "deals" triggered the Deal Hunter playbook.

The selector can return engines from MULTIPLE categories (e.g. flights +
hotels + maps for a travel query, or news + finance for a markets query).
Returned engines are strictly validated against KNOWN_ENGINES so the LLM
can never hallucinate an engine id.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..config import get_settings
from .llm import llm


# ---------------------------------------------------------------- catalogue
# Mirrors the COMPASS Available API Catalog from the product spec. Presented
# to the LLM so it can pick engines by vertical — not by keyword proximity.
API_CATALOG = [
    # Search & General Information
    {"engines": ["google", "google_light", "google_ai_mode", "bing", "duckduckgo", "yahoo"],
     "category": "Search & General Information",
     "use_for": "general web pages, facts, documentation, cross-checking, background research"},
    # News, Trends & Viral Content
    {"engines": ["google_news", "google_news_light", "google_trends", "google_trends_trending_now",
                 "bing_news", "duckduckgo_news"],
     "category": "News, Trends & Viral Content",
     "use_for": "current articles, headlines, trending topics, what is viral now"},
    # Media, Videos & Entertainment
    {"engines": ["youtube", "youtube_channel", "google_videos", "google_short_videos",
                 "bing_videos", "yahoo_videos"],
     "category": "Media, Videos & Entertainment",
     "use_for": "videos, songs, movies, shorts, reels, YouTube channels, movie trailers"},
    {"engines": ["google_images"],
     "category": "Images",
     "use_for": "pictures, photos, wallpapers, posters, image search"},
    # Maps, Local & Hospitality
    {"engines": ["google_maps", "yelp", "tripadvisor"],
     "category": "Maps, Local & Hospitality",
     "use_for": "places near me, restaurants, local businesses, venues, reviews, directions"},
    # Travel, Flights & Hotels — THE CATEGORY THE BUG REPORT CARES ABOUT
    {"engines": ["google_flights", "google_flights_deals", "google_hotels",
                 "google_travel_explore", "airbnb"],
     "category": "Travel, Flights & Hotels",
     "use_for": "flight tickets, airfare, train fares, bus fares, hotel rooms, resorts, "
                "trip planning, vacation destinations, cheap getaways, travel to a place"},
    # E-Commerce & Shopping
    {"engines": ["google_shopping", "google_shopping_light", "amazon", "walmart", "ebay",
                 "home_depot"],
     "category": "E-Commerce & Shopping",
     "use_for": "physical products to buy online (headphones, laptops, electronics, household goods). "
                "NOT for travel tickets, NOT for events — only tangible merchandise."},
    # Finance & Stocks
    {"engines": ["google_finance", "google_finance_markets"],
     "category": "Finance & Stocks",
     "use_for": "stock prices, shares, market indices, crypto, forex, earnings, IPOs"},
    # Apps, Books & Media Outlets
    {"engines": ["google_play", "apple_app_store", "google_scholar", "google_patents"],
     "category": "Apps, Scholar & Patents",
     "use_for": "mobile apps, academic papers, patents, prior art"},
    # Jobs & Events
    {"engines": ["google_jobs", "google_events"],
     "category": "Jobs & Events",
     "use_for": "job openings, career listings, local events (concerts, sports)"},
]

KNOWN_ENGINES: set[str] = {e for grp in API_CATALOG for e in grp["engines"]}


SELECTOR_SYSTEM = """You are a precise API router for a decision engine. Given a user prompt, select the SerpApi engines BEST suited to answer it.

Rules:
1. Read the user's intent carefully. Disambiguate ambiguous words using domain context:
   - "ticket" with flight/fly/airfare/train/bus/trip/travel/journey/airport/to <city>/from <city>/destination/fare → TRAVEL engines (google_flights, google_hotels, google_travel_explore), NEVER shopping engines.
   - "deals" / "budget" / "cheap" with travel words (trip, travel, fare, flight, hotel, visit, destination city names) → TRAVEL deal engines (google_flights_deals), NOT e-commerce.
   - "deals" / "cheap" / "buy" with product words (headphones, laptop, shoes, phone, electronics) → SHOPPING engines.
   - Event tickets (concert, sports, match, game) → google_events, not google_flights.
2. Pick 1 to 6 engines TOTAL from the catalog below. Prefer vertical-specific engines (flights, hotels, youtube) over generic web search when a vertical fits.
3. You may pick engines from MULTIPLE categories if the query spans them (e.g. a trip query gets flights + hotels + travel_explore + maps).
4. NEVER invent engine names. Use ONLY engine ids listed in the catalogue.

Reply with ONLY this JSON shape (no extra text):
{
  "primary_category": "<category name from catalogue>",
  "engines": ["<engine_id>", ...],
  "confidence": <0.0..1.0>,
  "reason": "<one short sentence explaining the disambiguation>"
}
"""


def _catalog_text() -> str:
    lines = []
    for grp in API_CATALOG:
        lines.append(f"[{grp['category']}] engines: {', '.join(grp['engines'])}")
        lines.append(f"    use_for: {grp['use_for']}")
    return "\n".join(lines)


@dataclass
class ApiSelection:
    """Validated output of the LLM API selector."""
    primary_category: str = "Search & General Information"
    engines: list[str] = field(default_factory=lambda: ["google_light"])
    confidence: float = 0.0
    reason: str = ""
    routed_by: str = "fallback"      # "llm" | "fallback" | "keyword_override"

    def as_dict(self) -> dict[str, Any]:
        return {"primary_category": self.primary_category, "engines": list(self.engines),
                "confidence": self.confidence, "reason": self.reason, "routed_by": self.routed_by}


def _validate(raw: Any) -> ApiSelection | None:
    if not isinstance(raw, dict):
        return None
    cat = str(raw.get("primary_category") or "Search & General Information")
    conf = raw.get("confidence")
    if not isinstance(conf, (int, float)):
        conf = 0.5
    conf = max(0.0, min(1.0, float(conf)))
    engines = [e for e in (raw.get("engines") or []) if isinstance(e, str) and e in KNOWN_ENGINES]
    engines = list(dict.fromkeys(engines))[:6]     # de-dupe, cap
    if not engines:
        return None
    return ApiSelection(primary_category=cat, engines=engines, confidence=conf,
                        reason=str(raw.get("reason") or "")[:200], routed_by="llm")


# ---------------------------------------------------------------- deterministic fast-path
# Even when the LLM call fails or no key is configured, apply the same disambiguation
# rules locally so the bug never resurfaces in offline/Demo Mode.

TRAVEL_CONTEXT_RE = re.compile(
    r"\b(flight|flights|fly|flying|airfare|airline|airlines|airport|airports|"
    r"hotel|hotels|resort|resorts|airbnb|stay|stays|destination|destinations|"
    r"trip|trips|travel|travelling|traveling|journey|vacation|holiday|getaway|getaways|"
    r"fare|fares|train|trains|railway|rail|bus|buses|coach|transit|transport|"
    r"itinerary|round\s*-?\s*trip|one\s*-?\s*way|layover|stopover|nonstop|non-stop|"
    r"depart|departure|arriv(e|al)|booking|book\s+(a\s+)?(flight|train|bus|hotel|room))\b", re.I)

# Place/city destination hints ONLY when preceded by a travel-motion verb or
# possessive (trip to X, travel to X, visit X, going to X, flying to X, for X trip).
# We explicitly AVOID plain "in <country>" because that is a market signal ("news in india").
_TO_DEST_RE = re.compile(
    r"\b(?:trip|travel(?:ling|ing)?|journey|fly(?:ing)?|go(?:ing)?|headed|heading|visit(?:ing)?|tour(?:ing)?|way)\s+(?:to\s+)?"
    r"(?:the\s+)?([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})"
    r"|\bto\s+(?:the\s+)?([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})"
    r"(?=\s*(?:$|[,.!?]|\s+(?:on|at|by|for|from|in|with|under|budget|trip|travel|fare|ticket|hotel)))", re.I)

PRODUCT_CONTEXT_RE = re.compile(
    r"\b(buy|order|purchase|laptop|headphones?|phone|tv|camera|shoes|shirt|dress|"
    r"electronics|amazon\.com|walmart\.com|ebay\.com|shipping|deliver(?:y|ed)|"
    r"refurbished|new\s+(?:in\s+)?box|bluetooth|usb|hdmi|ssd|ram|gpu|cpu)\b", re.I)

EVENT_CONTEXT_RE = re.compile(
    r"\b(concert|match|game|sports?|festival|show\s+ticket|theater|theatre|circus|"
    r"movie\s+ticket|cinema)\b", re.I)

NEWS_CONTEXT_RE = re.compile(
    r"\b(news|headlines?|breaking|latest\s+news|top\s+stories|happening\s+now|current\s+events|"
    r"trending\s+news|update|bulletin|press)\b", re.I)
MEDIA_VIDEO_RE = re.compile(
    r"\b(video|videos|youtube|song|songs|music|shorts|reels|tiktok|movie|movies|trailer|trailers|"
    r"playlist|channel|watch\b|clip|clips|viral\s+video|trending\s+songs?)\b", re.I)
MEDIA_IMAGE_RE = re.compile(
    r"\b(image|images|picture|pictures|photo|photos|pic|pics|wallpaper|poster|gallery|"
    r"photography|logo|thumbnails?)\b", re.I)
FINANCE_CONTEXT_RE = re.compile(
    r"\b(stock|stocks|share\s*price|ticker|nasdaq|nyse|nifty|sensex|crypto|bitcoin|forex|"
    r"earnings|ipo|market\s+index|etf|exchange\s+rate)\b", re.I)
LOCAL_CONTEXT_RE = re.compile(
    r"\b(restaurant|restaurants?|food\s+near|best\s+\w+\s+(?:in|near)|tacos|pizza|ramen|sushi|"
    r"brunch|coffee\s+shop|cafe|dinner|lunch|bar\s+(?:in|near)|yelp|tripadvisor|near\s+me|"
    r"reservation|book\s+a\s+table)\b", re.I)
APP_CONTEXT_RE = re.compile(
    r"\b(app|apps|play\s*store|app\s*store|apk|ios\s+app|android\s+app|mobile\s+app|"
    r"download\s+app)\b", re.I)
JOB_CONTEXT_RE = re.compile(r"\b(job|jobs|hiring|career|openings?|recruiter|salary)\b", re.I)
SCHOLAR_CONTEXT_RE = re.compile(r"\b(patent|patents|prior\s+art|scholar|research\s+paper|academic\s+paper)\b", re.I)


def deterministic_select(prompt: str) -> ApiSelection:
    """Hard-coded disambiguation that always runs (zero network, zero credits).

    Implements the same domain-context rules the LLM uses, so the offline
    path is also correct for the bug-report cases. Returns the minimal engine
    set from the right vertical; generic fallback only when nothing matches.
    """
    pl = prompt.lower()
    has_travel = bool(TRAVEL_CONTEXT_RE.search(prompt)) or bool(_TO_DEST_RE.search(prompt))
    has_product = bool(PRODUCT_CONTEXT_RE.search(prompt))
    has_event = bool(EVENT_CONTEXT_RE.search(prompt))
    has_news = bool(NEWS_CONTEXT_RE.search(prompt))
    has_video = bool(MEDIA_VIDEO_RE.search(prompt))
    has_image = bool(MEDIA_IMAGE_RE.search(prompt))
    has_finance = bool(FINANCE_CONTEXT_RE.search(prompt))
    has_local = bool(LOCAL_CONTEXT_RE.search(prompt))
    has_app = bool(APP_CONTEXT_RE.search(prompt))
    has_job = bool(JOB_CONTEXT_RE.search(prompt))
    has_scholar = bool(SCHOLAR_CONTEXT_RE.search(prompt))

    # Resolve "ticket" / "fares" / "deals" by domain context — the core of the bug fix
    if has_travel and not has_product:
        engines = ["google_flights", "google_travel_explore", "google_hotels"]
        if re.search(r"\b(cheap|budget|deals?|minimal|lowest|cheapest|affordable)\b", pl):
            engines.append("google_flights_deals")
        return ApiSelection(primary_category="Travel, Flights & Hotels",
                            engines=engines[:5], confidence=0.85,
                            reason="travel context words detected; flights+hotels selected",
                            routed_by="keyword_override")
    if has_product and not has_travel:
        engines = ["google_shopping", "amazon", "walmart", "ebay"]
        return ApiSelection(primary_category="E-Commerce & Shopping",
                            engines=engines, confidence=0.8,
                            reason="product keywords detected; shopping engines selected",
                            routed_by="keyword_override")
    if has_finance:
        return ApiSelection(primary_category="Finance & Stocks",
                            engines=["google_finance", "google_finance_markets", "google_news"],
                            confidence=0.8, reason="finance keywords detected",
                            routed_by="keyword_override")
    if has_news:
        engines = ["google_news", "google_trends", "google"]
        if re.search(r"\b(trending|viral)\b", pl):
            engines.append("google_trends_trending_now")
        return ApiSelection(primary_category="News, Trends & Viral Content",
                            engines=engines[:4], confidence=0.8,
                            reason="news keywords detected",
                            routed_by="keyword_override")
    if has_video:
        engines = ["youtube", "google_videos"]
        if re.search(r"\b(shorts|reels|tiktok)\b", pl):
            engines.append("google_short_videos")
        return ApiSelection(primary_category="Media, Videos & Entertainment",
                            engines=engines[:3], confidence=0.8,
                            reason="video/music keywords detected",
                            routed_by="keyword_override")
    if has_image:
        return ApiSelection(primary_category="Images",
                            engines=["google_images"], confidence=0.85,
                            reason="image keywords detected",
                            routed_by="keyword_override")
    if has_local:
        return ApiSelection(primary_category="Maps, Local & Hospitality",
                            engines=["google_maps", "yelp", "tripadvisor"], confidence=0.75,
                            reason="local venue keywords detected",
                            routed_by="keyword_override")
    if has_app:
        return ApiSelection(primary_category="Apps & Software",
                            engines=["google_play", "apple_app_store"], confidence=0.75,
                            reason="app keywords detected",
                            routed_by="keyword_override")
    if has_job:
        return ApiSelection(primary_category="Jobs & Careers",
                            engines=["google_jobs", "google"], confidence=0.7,
                            reason="job keywords detected",
                            routed_by="keyword_override")
    if has_scholar:
        return ApiSelection(primary_category="Scholar & Patents",
                            engines=["google_scholar", "google_patents"], confidence=0.7,
                            reason="scholar/patent keywords detected",
                            routed_by="keyword_override")
    if has_event:
        return ApiSelection(primary_category="Jobs & Events",
                            engines=["google_events", "google"], confidence=0.7,
                            reason="event keywords detected",
                            routed_by="keyword_override")
    # No strong vertical → return empty list (do NOT inject generic web engines;
    # the playbook's own engines are already correct for its category). This keeps
    # per-playbook call caps intact (test_trending_songs_demo_session needs ≤4 calls).
    return ApiSelection(primary_category="Search & General Information",
                        engines=[], confidence=0.0,
                        reason="no strong vertical signal; defer to playbook engines",
                        routed_by="playbook_default")


# ---------------------------------------------------------------- public entry point
async def select_apis(prompt: str, session_id: str = "") -> ApiSelection:
    """Ask Groq/Gemini which engines serve this prompt. Validate strictly.
    Falls back to the deterministic selector on any error."""
    s = get_settings()

    # Always run deterministic selection first — it sets a correct baseline
    # and is used as validation anchor for the LLM verdict.
    base = deterministic_select(prompt)

    # Skip LLM when router is disabled or no key configured
    if not s.groq_router_enabled or llm.provider == "heuristic":
        return base

    user = (f"User prompt: {prompt}\n\n"
            f"Deterministic hint (ignore if contradicted by prompt): "
            f"category={base.primary_category}, engines={base.engines}\n\n"
            f"Available SerpApi catalogue:\n{_catalog_text()}\n\n"
            f"Select engines now. Remember: 'ticket fare trip to <place>' is always TRAVEL, never shopping.")

    try:
        raw = await llm.complete_json(SELECTOR_SYSTEM, user, session_id=session_id,
                                       name="api_selector")
    except Exception:
        return base

    verdict = _validate(raw) if raw else None
    if verdict is None:
        return base

    # Safety net: if LLM returned shopping engines but deterministic saw strong travel
    # context (and no product words), override with the travel selection. This is the
    # last line of defence against the exact bug from the report.
    travel_engines = {"google_flights", "google_flights_deals", "google_hotels",
                      "google_travel_explore", "airbnb"}
    shopping_engines = {"google_shopping", "google_shopping_light", "amazon", "walmart",
                        "ebay", "home_depot"}
    verdict_travel = bool(set(verdict.engines) & travel_engines)
    verdict_shopping = bool(set(verdict.engines) & shopping_engines)
    has_travel = bool(TRAVEL_CONTEXT_RE.search(prompt)) or bool(_TO_DEST_RE.search(prompt))
    has_product = bool(PRODUCT_CONTEXT_RE.search(prompt))
    if verdict_shopping and not verdict_travel and has_travel and not has_product:
        # LLM made the exact bug we are fixing — override
        return base

    return verdict

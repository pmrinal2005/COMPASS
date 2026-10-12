"""Prompt analysis + LLM intent router.

PromptAnalysis extracts the *vertical* signals every downstream agent needs from the raw
prompt, with zero network calls:
  * recency      — does the user demand freshness? ("latest", "newest", "today", ...)
  * market       — country scoping ("in india" -> "in", "US stocks" -> "us")
  * entity       — the named subject of the query (creator, ticker, app, place, topic)
  * media_kind   — what the user wants back (video, music, image, app, news, ...)

route_with_llm() asks Groq (free tier) which playbook + engines best serve the prompt and
VALIDATES the answer against the local playbook catalogue — an unknown playbook id, an
unknown engine, or an out-of-range confidence is rejected and the caller falls back to the
deterministic classifier. The LLM therefore refines routing; it can never break it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..playbooks import PLAYBOOKS
from .llm import llm

# ------------------------------------------------------------------ recency
RECENCY_RE = re.compile(
    r"\b(latest|newest|recent|fresh|just\s+(out|released|dropped)|breaking|"
    r"today'?s?|tonight|this\s+(week|month|morning|evening)|right\s+now|"
    r"trending|viral|now\s+playing|new\s+releases?|this\s+just\s+in)\b", re.I)
STRONG_FRESH_RE = re.compile(r"\b(latest|newest|breaking|today|just\s+out|right\s+now)\b", re.I)

# ------------------------------------------------------------------ markets
MARKET_MAP = {
    "india": "in", "indian": "in", "bharat": "in",
    "united states": "us", "usa": "us", "u.s.": "us", "america": "us", "american": "us",
    "united kingdom": "gb", "uk": "gb", "britain": "gb", "british": "gb", "england": "gb",
    "canada": "ca", "canadian": "ca", "australia": "au", "australian": "au",
    "germany": "de", "german": "de", "france": "fr", "french": "fr",
    "japan": "jp", "japanese": "jp", "china": "cn", "chinese": "cn", "korea": "kr", "korean": "kr",
    "brazil": "br", "mexico": "mx", "spain": "es", "italy": "it", "netherlands": "nl", "dutch": "nl",
    "singapore": "sg", "uae": "ae", "dubai": "ae", "saudi": "sa",
}
_MARKET_RE = re.compile(r"\b(in|for|from|across|within)\s+([a-z][a-z .]{1,24}?)(?=\s+(news|today|trending|market|markets|flights|hotels|songs|videos|stocks)\b|\s*[,.!?]?\s*$)", re.I)

# ------------------------------------------------------------------ entities / media kinds
_CREATOR_RE = re.compile(r"\b(?i:(?:latest|new|recent|all)?)\s*([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\s+(?i:(videos?|songs?|shorts|channel|uploads?|streams?|music))\b")
_TICKER_RE = re.compile(r"\b([A-Z]{1,5})(?::(NASDAQ|NYSE|NSE|BSE|LSE))?\b")
_APP_RE = re.compile(r"(?i)\b(?:app|apps)\s+(?:like|for|called|named)?\s*([A-Za-z][A-Za-z0-9 .&'-]{1,40}?)(?:\s+(?:app|on|for|vs|versus|comparison|compare|review)\b|\s*[?.!]*\s*$)")
MUSIC_RE = re.compile(r"\b(song|songs|music|track|tracks|playlist|album|albums|artist|singer|rapper|band|lyrics|spotify|remix)\b", re.I)
VIDEO_RE = re.compile(r"\b(video|videos|youtube|clip|clips|shorts|reels|tiktok|vlog|trailer|trailers|movie|movies|show|series|episode|watch|stream|streaming|channel|creator|uploads?)\b", re.I)
IMAGE_RE = re.compile(r"\b(image|images|picture|pictures|photo|photos|pic|pics|wallpaper|wallpapers|poster|logo|thumbnail|photography|gallery)\b", re.I)
APP_RE_KIND = re.compile(r"\b(apps?|play\s*store|app\s*store|apk|ios|android|download)\b", re.I)
NEWS_RE_KIND = re.compile(r"\b(news|headlines?|breaking|update|updates|happening|report|reports|story|stories|bulletin|press)\b", re.I)

# --- domain disambiguation (fixes the "ticket fares for trip" -> shopping bug) ---
TRAVEL_WORDS_RE = re.compile(
    r"\b(flight|flights|fly|flying|airfare|airline|airlines|airport|airports|"
    r"hotel|hotels|resort|resorts|airbnb|stay\b|destination|destinations|"
    r"trip|trips|travel|travelling|traveling|journey|vacation|holiday|getaway|getaways|"
    r"fare|fares|train|trains|railway|rail|bus|buses|coach|transit|transport|"
    r"itinerary|layover|stopover|nonstop|non-stop|departure|arrival|booking)\b", re.I)
PRODUCT_WORDS_RE = re.compile(
    r"\b(buy|order|purchase|laptop|headphones?|phone|tv|camera|shoes|shirt|dress|"
    r"electronics|refurbished|bluetooth|usb|hdmi|ssd|gpu|cpu|shipping|deliver(?:y|ed))\b", re.I)
# Destination hint — requires a travel-motion word nearby. Plain "in <country>"
# (market context like "news in india") must NOT match as a travel destination.
TO_DEST_RE = re.compile(
    r"\b(?:trip|travel(?:ling|ing)?|journey|fly(?:ing)?|go(?:ing)?|headed|heading|visit(?:ing)?|tour(?:ing)?|way)\s+(?:to\s+)?"
    r"(?:the\s+)?([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})"
    r"|\bto\s+(?:the\s+)?([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,2})"
    r"(?=\s*(?:$|[,.!?]|\s+(?:on|at|by|for|from|in|with|under|budget|trip|travel|fare|ticket|hotel)))", re.I)


@dataclass
class PromptAnalysis:
    recency: bool = False
    fresh_strong: bool = False          # "latest/breaking/today" -> bypass cache AND re-weight freshness
    market: str | None = None           # "in" | "us" | ... (None = playbook default)
    market_text: str | None = None      # the matched span ("india")
    entity: str | None = None           # named subject ("Techno Gamerz", "AAPL", "Instagram")
    entity_kind: str | None = None      # creator | ticker | app | topic
    media_kind: str | None = None       # music | video | image | app | news
    wants_broad: bool = False           # "compare/across/everywhere" -> enable broad-coverage optional engines
    wants_light: bool = False           # "quick/fast/brief" -> lightweight sweeps
    wants_trending: bool = False        # "trending/viral" -> momentum engines
    wants_shorts: bool = False          # shorts/reels/tiktok -> short-form video
    wants_deals: bool = False           # cheap/deals/discount -> deals engines
    wants_images: bool = False          # image/picture/photo -> image engines
    travel_origin: str | None = None    # explicit trip origin ("from NYC", "JFK to LHR")
    is_travel_context: bool = False     # true when travel words dominate (deals -> flights_deals, not shopping)
    is_product_context: bool = False    # true when product words dominate

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


_BARE_CODE_RE = re.compile(r"\b(US|USA|UK|GB|UAE)\b")   # case-sensitive: bare "us" in prose is not America

TICKER_MAP = {
    "apple": "AAPL:NASDAQ", "tesla": "TSLA:NASDAQ", "google": "GOOGL:NASDAQ", "alphabet": "GOOGL:NASDAQ",
    "microsoft": "MSFT:NASDAQ", "amazon": "AMZN:NASDAQ", "nvidia": "NVDA:NASDAQ", "meta": "META:NASDAQ",
    "netflix": "NFLX:NASDAQ", "amd": "AMD:NASDAQ", "intel": "INTC:NASDAQ", "reliance": "RELIANCE:NSE",
    "tcs": "TCS:NSE", "infosys": "INFY:NSE", "hdfc": "HDFCBANK:NSE", "icici": "ICICIBANK:NSE",
    "sensex": "SENSEX:INDEXBOM", "nifty": "NIFTY_50:INDEXNSE", "nasdaq": ".IXIC:INDEXNASDAQ",
    "dow": ".DJI:INDEXDJX", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
}


def extract_market(prompt: str) -> tuple[str | None, str | None]:
    pl = f" {prompt.lower()} "
    m = _MARKET_RE.search(prompt)
    if m:
        name = m.group(2).strip().lower().rstrip(".")
        if name in MARKET_MAP:
            return MARKET_MAP[name], m.group(2).strip()
    m = _BARE_CODE_RE.search(prompt)
    if m:
        return m.group(1).lower(), m.group(1)
    for name, code in sorted(MARKET_MAP.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(name)}\b", pl):
            return code, name
    return None, None


def extract_entity(prompt: str, playbook_id: str | None = None) -> tuple[str | None, str | None]:
    m = _CREATOR_RE.search(prompt)
    if m:
        return m.group(1).strip(), "creator"
    m = _APP_RE.search(prompt)
    if m and len(m.group(1).strip()) >= 2:
        return m.group(1).strip(), "app"
    m = re.search(r"(?i)\b(?:best|top|good|free|new)?\s*([A-Za-z][A-Za-z0-9 .&'-]{2,30}?)\s+apps?\b", prompt)
    if m and m.group(1).strip().lower() not in ("the", "an", "a", "my", "this"):
        return m.group(1).strip(), "app"
    # bare @handle ("videos by @mkbhd")
    m = re.search(r"@([A-Za-z0-9_.-]{2,40})", prompt)
    if m:
        return m.group(1), "creator"
    # company-name tickers ("Tesla shares", "Apple stock") — only with finance context
    pl = prompt.lower()
    if re.search(r"\b(stock|stocks|shares?|price|quote|earnings|market|markets|invest|nasdaq|nyse|nse|etf|crypto)\b", pl):
        for name, sym in sorted(TICKER_MAP.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{re.escape(name)}\b", pl):
                return sym, "ticker"
    # literal tickers ("AAPL stock", "RELIANCE:NSE")
    for m in _TICKER_RE.finditer(prompt):
        tok = m.group(1)
        if len(tok) >= 2 and tok not in {"I", "A", "TV", "AI", "US", "UK", "GO", "IN", "ON", "IT"}:
            if m.group(2) or re.search(rf"(?i)\b{tok}\b\s*(stock|stocks|shares?|price|quote|earnings)\b", prompt):
                return f"{tok}:{m.group(2) or 'NASDAQ'}" if m.group(2) or len(tok) <= 5 else tok, "ticker"
    return None, None


_ROUTE_RE = re.compile(r"\b([A-Z]{3})\s*(?:to|→|->)\s*([A-Z]{3})\b")
_FROM_RE = re.compile(r"\bfrom\s+([A-Z]{3}|[A-Z][A-Za-z]+(?:\s+[A-Z][a-z]+){0,2})")


def extract_travel_origin(prompt: str) -> str | None:
    """Explicit trip origin: an IATA route ("JFK to LHR") or "from <Place>". Case-sensitive so
    prose ("from scratch") never matches."""
    m = _ROUTE_RE.search(prompt)
    if m:
        return m.group(1)
    m = _FROM_RE.search(prompt)
    return m.group(1) if m else None


def classify_media_kind(prompt: str) -> str | None:
    if MUSIC_RE.search(prompt):
        return "music"
    if IMAGE_RE.search(prompt):
        return "image"
    if APP_RE_KIND.search(prompt):
        return "app"
    if VIDEO_RE.search(prompt):
        return "video"
    if NEWS_RE_KIND.search(prompt):
        return "news"
    return None


def analyze_prompt(prompt: str, playbook_id: str | None = None) -> PromptAnalysis:
    """Deterministic, zero-network prompt analysis (always available, even offline)."""
    pl = prompt.lower()
    market, market_text = extract_market(prompt)
    entity, entity_kind = extract_entity(prompt, playbook_id)
    # Domain context — resolves "ticket fares trip to X at minimal budget, best deals"
    is_travel = bool(TRAVEL_WORDS_RE.search(prompt)) or bool(TO_DEST_RE.search(prompt))
    is_product = bool(PRODUCT_WORDS_RE.search(prompt))
    # "deals/budget/cheap" is context-sensitive: in travel it means flight_deals (good),
    # NOT shopping — so suppress shopping interpretation when travel words co-occur.
    deal_words_present = bool(re.search(r"\b(cheap|cheapest|deal|deals|discount|discounts|sale|offer|offers|budget|minimal|lowest|affordable)\b", pl))
    a = PromptAnalysis(
        recency=bool(RECENCY_RE.search(prompt)),
        fresh_strong=bool(STRONG_FRESH_RE.search(prompt)),
        market=market, market_text=market_text,
        entity=entity, entity_kind=entity_kind,
        media_kind=classify_media_kind(prompt),
        wants_broad=bool(re.search(r"\b(compare|comparison|across|everywhere|all\s+(over|platforms|engines|sources)|side[\s-]?by[\s-]?side)\b", pl)),
        wants_light=bool(re.search(r"\b(quick|fast|light|brief|summary|overview|tl;dr)\b", pl)),
        wants_trending=bool(re.search(r"\b(trend|trends|trending|viral|popular|buzz|momentum|interest)\b", pl)),
        wants_shorts=bool(re.search(r"\b(shorts|reels?|tiktok|short[\s-]?form|short\s+videos?)\b", pl)),
        wants_deals=deal_words_present,
        wants_images=bool(IMAGE_RE.search(prompt)),
        travel_origin=extract_travel_origin(prompt),
        is_travel_context=is_travel and not (is_product and not is_travel),
        is_product_context=is_product and not is_travel,
    )
    return a


# ------------------------------------------------------------------ Groq LLM router
ROUTER_SYSTEM = """You route a user prompt to ONE playbook of the COMPASS decision engine and pick the minimal SerpApi engines needed. Reply ONLY with JSON:
{"playbook_id": "<id>", "confidence": <0..1>, "reason": "<=20 words>", "engines": ["<engine>", ...]}
Rules: confidence is your certainty the playbook fits (generic prompts -> low). engines must be 1-4 items from the playbook's engine list. Never invent ids."""

KNOWN_ENGINES = {
    "google", "google_light", "google_news", "google_news_light", "google_trends", "google_trends_trending_now",
    "google_images", "google_videos", "google_short_videos", "youtube", "youtube_channel",
    "bing", "bing_news", "bing_videos", "duckduckgo", "duckduckgo_news", "yahoo", "yahoo_videos", "yandex", "baidu", "naver",
    "google_maps", "yelp", "tripadvisor", "google_events", "airbnb",
    "google_flights", "google_flights_deals", "google_flights_autocomplete", "google_travel_explore", "google_hotels",
    "google_shopping", "google_shopping_light", "amazon", "walmart", "ebay",
    "google_finance", "google_finance_markets", "google_jobs", "google_scholar", "google_patents",
    "google_play", "apple_app_store", "google_ai_mode", "google_ai_overview",
}


def validate_router_verdict(v: Any) -> dict | None:
    """Accept only well-formed verdicts that reference real playbooks/engines."""
    if not isinstance(v, dict):
        return None
    pid = v.get("playbook_id")
    conf = v.get("confidence")
    if pid not in PLAYBOOKS or not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
        return None
    allowed = {sp["engine"] for sp in PLAYBOOKS[pid].get("engines", [])} | \
              {sp["engine"] for sp in PLAYBOOKS[pid].get("optional_engines", [])} | \
              {sp["engine"] for sp in PLAYBOOKS[pid].get("fallback_engines", [])}
    engines = [e for e in (v.get("engines") or []) if e in allowed and e in KNOWN_ENGINES][:4]
    return {"playbook_id": pid, "confidence": round(float(conf), 3),
            "reason": str(v.get("reason") or "")[:160], "engines": engines}


async def route_with_llm(prompt: str, lens: str, analysis: PromptAnalysis, session_id: str = "") -> dict | None:
    """Ask Groq (free tier) for the best playbook; return a VALIDATED verdict or None.

    Returns None when the router is disabled, no LLM key is configured, the call fails,
    or the verdict references anything outside the local catalogue — the deterministic
    classifier then decides alone."""
    from ..config import get_settings
    s = get_settings()
    if not s.groq_router_enabled or llm.provider == "heuristic":
        return None
    catalog = "\n".join(
        f"- {pid} [{pb.get('intent_category')}]: {pb['name']} — {pb['description'][:140]} "
        f"(engines: {', '.join(sorted({sp['engine'] for sp in pb.get('engines', [])}))})"
        for pid, pb in sorted(PLAYBOOKS.items()))
    user = (f"Lens: {lens}\nPrompt: {prompt}\nSignals: recency={analysis.recency} market={analysis.market} "
            f"entity={analysis.entity} media_kind={analysis.media_kind}\nCatalogue:\n{catalog}")
    try:
        raw = await llm.complete_json(ROUTER_SYSTEM, user, session_id=session_id, name="intent.llm_router")
    except Exception:
        return None
    verdict = validate_router_verdict(raw)
    if verdict and session_id:
        from .tracing import tracer
        tracer.span(session_id, "intent:llm_router", {"prompt": prompt[:200]}, verdict)
    return verdict

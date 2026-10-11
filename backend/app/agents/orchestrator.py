"""ORCHESTRATOR / PLANNER
 1. embeds the prompt and matches it against the Playbook library
    (cosine similarity + keyword prior, LLM tie-break when available)
 2. fills playbook slots (LLM JSON extraction -> regex heuristics fallback)
 3. emits a typed Decision Graph: entities, comparison dimensions,
    constraints, required data sources (SerpApi calls), candidate actions
 4. on re-plan, adds the playbook's targeted fallback engines (bounded)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from ..models import DecisionGraph, DecisionNode, EngineCall
from ..playbooks import PLAYBOOKS, playbook_text
from ..services.events import bus
from ..services.geo import YELP_COUNTRIES, country_for, resolve
from ..services.intent import TICKER_MAP, PromptAnalysis, analyze_prompt, route_with_llm
from ..services.llm import embedder, llm
from ..services.serpapi import CreditMeter
from ..services.store import store

_PB_VECS: dict[str, list[float]] = {}
_PB_SYNCED = {"ok": False}


async def _pb_vectors() -> dict[str, list[float]]:
    if not _PB_VECS:
        ids = list(PLAYBOOKS)
        vecs = await embedder.embed([playbook_text(PLAYBOOKS[i]) for i in ids])
        _PB_VECS.update(dict(zip(ids, vecs)))
    if not _PB_SYNCED["ok"] and store.backend == "supabase-pgvector":
        _PB_SYNCED["ok"] = await store.sync_playbooks(PLAYBOOKS, _PB_VECS)
    return _PB_VECS


# ---------------------------------------------------------------- intent routing
# Intent confidence below this value never routes to a specialised (e.g. local-discovery) playbook:
# the prompt is handled by GENERAL_SEARCH instead (Google Search + Google News).
INTENT_CONFIDENCE_FLOOR = 0.50
GENERAL_FALLBACK = "general_search"
COSINE_FLOOR, COSINE_CEIL = 0.15, 0.50       # cosine below the floor carries no semantic evidence


def intent_category(pid: str) -> str:
    """Taxonomy bucket of a playbook (NEWS_AND_TRENDS, MEDIA_AND_ENTERTAINMENT, LOCAL_DISCOVERY, ...)."""
    return PLAYBOOKS[pid].get("intent_category", "GENERAL_SEARCH")


def _kw_hits(terms: list[str], words: set[str], pl: str) -> int:
    return sum(1 for k in terms if (k in words if " " not in k else k in pl))


def _intent_confidence(top: dict, runner_up: dict | None, analysis: PromptAnalysis | None = None) -> float:
    """Normalized confidence in [0, 1] that the TOP playbook really matches the prompt.

    Built from *evidence*, not from the blended ranking score: one STRONG keyword hit
    (an unambiguous intent marker like "flights", "prior art", "youtube") is conclusive;
    weak (topical) hits need corroboration, and cosine above the noise floor is a third,
    weaker signal. A prompt with no strong hit, one weak hit and weak cosine
    (e.g. "latest news in india" matching local discovery at 0.14) scores near 0."""
    strong = top.get("strong_hits", 0)
    weak = top.get("keyword_hits", 0)
    if strong >= 1:
        kw = 1.0
    elif weak >= 2:
        kw = 0.85
    elif weak == 1:
        kw = 0.55
    else:
        kw = 0.0
    # an explicit trip origin ("from NYC", "JFK to LHR") corroborates flight intent
    # even when the wording is vague ("cheap trips from NYC")
    if analysis is not None and top.get("id") == "travel_explore" and analysis.travel_origin:
        kw = max(kw, 0.85)
    sem = max(0.0, min(1.0, (top["cosine"] - COSINE_FLOOR) / (COSINE_CEIL - COSINE_FLOOR)))
    gap = top["score"] - (runner_up["score"] if runner_up else 0.0)
    margin = max(0.0, min(1.0, gap / 0.25))
    return round(0.6 * kw + 0.25 * sem + 0.15 * margin, 4)


# Priors: per-playbook score adjustments applied BEFORE the confidence floor.
# LOCAL_DISCOVERY is the historical misroute magnet (the bug report's "Latest Recipe" match):
# without an explicit venue/food marker it is penalized so generic prompts fall through to
# GENERAL_SEARCH instead of guessing a restaurant route.
def _prior(pid: str, strong_hits: int, analysis: PromptAnalysis) -> float:
    if pid == "lifeops_local" and strong_hits == 0:
        return -0.20
    # an explicit trip origin ("from NYC", "JFK to LHR") is flight intent even when the
    # wording is vague ("cheap weekend getaways from NYC") — boost past the confidence floor
    if pid == "travel_explore" and analysis.travel_origin:
        return 0.15
    return 0.0


async def classify(prompt: str, lens: str, forced: str | None = None) -> tuple[str, list[dict]]:
    analysis = analyze_prompt(prompt)
    if forced and forced in PLAYBOOKS:
        return forced, [{"id": forced, "score": 1.0, "name": PLAYBOOKS[forced]["name"],
                         "intent_category": intent_category(forced), "confidence": 1.0, "routed_by": "forced",
                         "analysis": analysis.as_dict(), "llm_router": None}]
    qv = (await embedder.embed([prompt], task="RETRIEVAL_QUERY"))[0]
    vecs = await _pb_vectors()
    # Supabase pgvector similarity (match_playbooks RPC) when available, else in-process cosine
    remote = await store.match_playbooks(qv, k=len(PLAYBOOKS)) if _PB_SYNCED["ok"] else None
    pl = prompt.lower()
    words = set(re.findall(r"[a-z0-9]+", pl))
    scores = []
    for pid, pb in PLAYBOOKS.items():
        cos = remote[pid] if remote and pid in remote else sum(a * b for a, b in zip(qv, vecs[pid]))
        strong = _kw_hits(pb.get("strong_keywords", []), words, pl)
        weak = _kw_hits(pb.get("keywords", []), words, pl)
        lens_bias = 0.08 if pb["lens"] == lens else 0.0
        prior = _prior(pid, strong, analysis)
        score = (cos * 0.5 + (0.55 if strong >= 1 else 0.0) + min(weak, 5) * 0.16 + lens_bias + prior)
        scores.append({"id": pid, "name": pb["name"], "score": round(score, 4),
                       "cosine": round(cos, 4), "keyword_hits": weak, "strong_hits": strong,
                       "vector_backend": "pgvector" if remote else "local",
                       "intent_category": intent_category(pid)})
    # The GENERAL_SEARCH fallback is a route, not a competitor: it is excluded from the ranking
    # so it can never be mis-ranked above a real playbook.
    scores = [s for s in scores if s["id"] != GENERAL_FALLBACK] + [s for s in scores if s["id"] == GENERAL_FALLBACK]
    ranked = sorted([s for s in scores if s["id"] != GENERAL_FALLBACK], key=lambda x: -x["score"])
    top = ranked[0]
    conf = _intent_confidence(top, ranked[1] if len(ranked) > 1 else None, analysis)

    # Groq LLM router (validated): a high-confidence verdict overrides a weak classifier top,
    # and agreement with the top boosts confidence. Offline / keyless -> None (no-op).
    llm_verdict = await route_with_llm(prompt, lens, analysis)
    if llm_verdict and llm_verdict["playbook_id"] != GENERAL_FALLBACK:
        cand = next((s for s in ranked if s["id"] == llm_verdict["playbook_id"]), None)
        if cand is not None:
            if llm_verdict["confidence"] >= 0.70 and (cand is not top or conf < INTENT_CONFIDENCE_FLOOR):
                top = cand
                conf = max(conf, round(0.5 * conf + 0.5 * llm_verdict["confidence"], 4))
                top["llm_boost"] = True
            elif cand is top:
                conf = min(1.0, round(conf + 0.10 * llm_verdict["confidence"], 4))

    for s in ranked:
        s["confidence"] = conf if s is top else round(_intent_confidence(s, None), 4)
    for s in ranked:
        s["analysis"] = analysis.as_dict()
        s["llm_router"] = llm_verdict
    if conf < INTENT_CONFIDENCE_FLOOR:
        # low confidence -> GENERAL_SEARCH, never a guessed local-discovery route
        gen = next(s for s in scores if s["id"] == GENERAL_FALLBACK)
        gen.update({"score": 0.0, "confidence": conf, "routed_by": "confidence_floor",
                    "reason": f"confidence {conf:.2f} < {INTENT_CONFIDENCE_FLOOR:.2f}; closest playbook was {top['id']}",
                    "analysis": analysis.as_dict(), "llm_router": llm_verdict})
        return GENERAL_FALLBACK, [gen] + ranked
    top["routed_by"] = "llm_router" if top.get("llm_boost") else "classifier"
    return top["id"], ranked


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "a week": 7, "weekend": 3}


_Q_STRIP = re.compile(r"(?i)\b(?:find|get|show|give|recommend|suggest|look(?:ing)?\s+for|me|the|an?|some|good|great|nice|best|top[- ]rated|highly[- ]rated|"
                      r"well[- ]rated|top|cheap|spot|spots|place|places|for|to|eat|at|any|please|i|want|need|where|can|go|would|like|tonight|"
                      r"today|tomorrow|saturday|sunday|friday|weekend|dinner|lunch)\b")
_CITY_RE = re.compile(r"\b(?:in|near|around|nearby)\s+((?:[A-Za-z][A-Za-z.'-]*)(?:\s+[A-Za-z][A-Za-z.'-]*){0,3}?(?:,\s*[A-Za-z]{2}\b)?)"
                      r"(?=\s+(?i:under|with|for|that|rated|open|on|at|and|before|after|below|over|from|to)\b|\s*[.!?]?\s*$|\s*,)")


def _local_slots(p: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pl = p.lower()
    m = _CITY_RE.search(p)
    before = p
    if m:
        city = re.sub(r"(?i)^(?:downtown|central|old|midtown|uptown|the)\s+", "", m.group(1)).strip(" ,.")
        if city:
            out["city"] = city
        before = p[: m.start()]
    q = _Q_STRIP.sub(" ", before)
    q = re.sub(r"[^A-Za-z0-9&' -]+", " ", q)
    q = " ".join(w for w in q.replace(" - ", " ").split() if w not in ("-",)).strip(" -.")
    q = re.sub(r"(?i)\b(restaurants?|spot|place)s?\b", "", q).strip() or ("restaurants" if re.search(r"(?i)restaurant", p) else "")
    if q:
        out["query"] = q.lower()
    r = re.search(r"(\d(?:\.\d)?)\s*(?:\+|stars?\b|-star)", pl) or re.search(r"rated\s+(?:at least\s+|over\s+|above\s+)?(\d(?:\.\d)?)", pl) \
        or re.search(r"(?:rating|stars?)\s*(?:of|>=|≥|over|above)?\s*(\d(?:\.\d)?)", pl)
    if r and 1 <= float(r.group(1)) <= 5:
        out["min_rating"] = float(r.group(1))
    pc = re.search(r"(?:under|below|max|up to|<=?)\s*(\${1,4})(?!\d)", pl)
    if pc:
        out["price_cap"] = len(pc.group(1))
    elif re.search(r"\b(cheap|budget|inexpensive)\b", pl):
        out["price_cap"] = 2
    return out


_DOMAIN_RE = re.compile(r"(?<![@\w/.-])((?:[a-z0-9][a-z0-9-]*\.)+(?:com|org|net|io|co|ai|dev|app|edu|gov|uk|de|fr|jp|cn|ru|kr|in|ca|au|us|info|tech|xyz))\b", re.I)


def _seo_slots(p: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    p = re.sub(r"(?i)\bhttps?://(?:www\.)?", "", p)                 # accept pasted URLs
    p = re.sub(r"(?i)(?<![\w.-])www\.(?=[a-z0-9-]+\.)", "", p)
    d = _DOMAIN_RE.search(p)
    rest = p
    if d:
        out["domain"] = d.group(1).lower()
        rest = p.replace(d.group(0), " ", 1).replace("/", " ")
    q = re.search(r"[\"“”‘’']([^\"“”‘’']{2,80})[\"“”‘’']", rest)
    if q:
        out["keyword"] = q.group(1).strip()
    else:
        k = re.search(r"(?i)\b(?:for|keyword|query|on)\s+(?:the\s+)?(?:keyword\s+)?([a-z0-9][a-z0-9 +&-]{2,60}?)(?=\s+(?:across|on|in|and|with|using|from|vs|against)\b|[.?!]?\s*$)", rest)
        if k:
            out["keyword"] = k.group(1).strip()
    mk = re.search(r"(?i)\b(?:in|for|market)\s+(?:the\s+)?(us|usa|uk|united kingdom|germany|france|japan|india|canada|australia)\b", p)
    if mk:
        out["market"] = {"usa": "us", "uk": "gb", "united kingdom": "gb", "germany": "de", "france": "fr", "japan": "jp", "india": "in",
                         "canada": "ca", "australia": "au"}.get(mk.group(1).lower(), mk.group(1).lower())
    return out


_TICKER_MAP = {**TICKER_MAP, "s&p": ".INX:INDEXSP"}
_LEAD_STRIP = re.compile(r"(?i)^\s*(?:latest|newest|most\s+recent|recent|breaking|today'?s?|this\s+week'?s?)\s+")
_MARKET_STRIP_FMT = r"\s*\b(?:in|for|from|across)\s+{m}\b\s*"


def _topic_text(prompt: str, analysis: PromptAnalysis | None) -> str:
    """Topic/query text for the vertical playbooks: the raw prompt minus the market span
    ("trending songs in india" -> "trending songs") and leading recency adjectives."""
    t = prompt.strip().rstrip(".?!")
    if analysis and analysis.market_text:
        t = re.sub(_MARKET_STRIP_FMT.format(m=re.escape(analysis.market_text)), " ", t, flags=re.I)
    t = _LEAD_STRIP.sub("", t).strip()
    t = re.sub(r"\s{2,}", " ", t).strip(" -,.?")
    return t or prompt.strip()


def _ticker_text(prompt: str, analysis: PromptAnalysis | None) -> str | None:
    if analysis and analysis.entity_kind == "ticker" and analysis.entity:
        ent = analysis.entity
        return ent if ":" in ent else f"{ent}:NASDAQ"
    pl = prompt.lower()
    for name, sym in sorted(_TICKER_MAP.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(name)}\b", pl):
            return sym
    m = re.search(r"\b([A-Z]{2,5})(?::(NASDAQ|NYSE|NSE|BSE|LSE))?\b", prompt)
    if m and m.group(1) not in {"NEWS", "TODAY", "LATEST", "TRENDING"}:
        return f"{m.group(1)}:{m.group(2) or 'NASDAQ'}"
    return None


def _heuristic_slots(pid: str, prompt: str, analysis: PromptAnalysis | None = None) -> dict[str, Any]:
    p = prompt.strip()
    pl = p.lower()
    slots: dict[str, Any] = {}
    money = re.search(r"(?:under|below|max|budget|<|less than|up to)?\s*\$\s?([\d,]+(?:\.\d+)?)\s*(k)?", pl)
    if money:
        v = float(money.group(1).replace(",", ""))
        slots["budget"] = v * 1000 if money.group(2) else v
    if pid == "lifeops_trip":
        d = re.search(r"(\d+)[\s-]*(?:day|night)", pl)
        if d:
            slots["days"] = int(d.group(1))
        else:
            for w, n in _NUM_WORDS.items():
                if re.search(rf"\b{w}[\s-]*(?:day|night)", pl) or (w == "weekend" and "weekend" in pl) or (w == "a week" and "a week" in pl):
                    slots["days"] = n
                    break
        frm = re.search(r"\bfrom\s+([a-z][a-z .]+?)(?:\s+(?:to|under|for|in|on|with|,)|$)", pl)
        to = re.search(r"\b(?:to|in|visit|trip to)\s+([a-z][a-z .]+?)(?:\s+(?:from|under|for|on|with|trip|,)|[,.]|$)", pl)
        dest_hint = re.search(r"(?:\d+[\s-]*day\s+)([a-z][a-z ]+?)\s+trip", pl)
        if frm:
            slots["origin"] = frm.group(1).strip().title()
        if dest_hint:
            slots["destination"] = dest_hint.group(1).strip().title()
        elif to:
            slots["destination"] = to.group(1).strip().title()
        a = re.search(r"(\d+)\s*(?:adults|people|travel+ers|persons)", pl)
        if a:
            slots["adults"] = int(a.group(1))
    elif pid in ("lifeops_deals", "pro_supplier"):
        cleaned = re.sub(r"(?i)\b(find|get|the|me|best|deal|deals|on|for|cheapest|source|sourcing|reliable|suppliers?|vendors?|"
                         r"compare|price|prices|moq|reviews?|bulk|wholesale|with|good|under|a|an|of|and|\d+|\$[\d,.]+k?)\b", " ", p)
        cleaned = re.sub(r"[/,]+", " ", cleaned)
        prod = " ".join(cleaned.split()).strip(" .")
        if prod:
            slots["product"] = prod
        c = re.search(r"\b(\d+|three|two|five|four)\s+(?:reliable\s+)?(?:suppliers|vendors)", pl)
        if c:
            slots["count"] = int(c.group(1)) if c.group(1).isdigit() else _NUM_WORDS.get(c.group(1), 3)
        q = re.search(r"([\d,]+)\s*(?:units|pcs|pieces)", pl)
        if q:
            slots["quantity"] = int(q.group(1).replace(",", ""))
    elif pid == "lifeops_local":
        slots.update(_local_slots(p))
        slots.pop("budget", None)          # "$$" is a Yelp price level here, never a dollar budget
    elif pid == "research_seo":
        slots.update(_seo_slots(p))
        slots.pop("budget", None)
    elif pid == "career_jobs":
        loc = re.search(r"\b(?:in|near|at)\s+([A-Za-z][A-Za-z ,]+)$", p)
        role = re.sub(r"(?i)\b(jobs?|openings?|positions?|roles?|find|me|hiring|for)\b", " ", p)
        if loc:
            slots["location"] = loc.group(1).strip()
            role = role.replace(loc.group(0), " ")
        role = " ".join(role.split()).strip(" .")
        if role:
            slots["role"] = role
    elif pid == "research_ip":
        topic = re.sub(r"(?i)^(prior art|research landscape|landscape|research|brief|papers|patents)\s*(for|on|about|of)?\s*", "", p)
        slots["topic"] = topic.strip(" .") or p
    elif pid in ("news_trends", "media_video"):
        t = _topic_text(p, analysis)
        if t:
            slots["topic"] = t
        if analysis and analysis.market:
            slots["market"] = analysis.market
    elif pid == "finance_markets":
        tick = _ticker_text(p, analysis)
        if tick:
            slots["ticker"] = tick
        if analysis and analysis.market:
            slots["market"] = analysis.market
    elif pid in ("general_search", "media_images", "apps_store"):
        t = _topic_text(p, analysis)
        if t:
            slots["query"] = t
        if analysis and analysis.market:
            slots["market"] = analysis.market
    return slots


async def fill_slots(pid: str, prompt: str, session_id: str, analysis: PromptAnalysis | None = None) -> dict[str, Any]:
    pb = PLAYBOOKS[pid]
    slots = {k: v.get("default") for k, v in pb["slots"].items()}
    slots.update({k: v for k, v in _heuristic_slots(pid, prompt, analysis).items() if v not in (None, "")})
    extracted = await llm.complete_json(
        "You extract structured slots for a decision engine. Reply ONLY with JSON containing exactly these keys "
        f"(use null if unknown): {list(pb['slots'].keys())}. Money as a plain number in USD. Cities as plain city names.",
        f"Request: {prompt}", session_id=session_id, name="orchestrator.slot_fill")
    if isinstance(extracted, dict):
        for k, v in extracted.items():
            if k in slots and v not in (None, "", 0):
                slots[k] = v
    return slots


async def _derive(pid: str, slots: dict[str, Any], session_id: str = "", meter: CreditMeter | None = None) -> dict[str, Any]:
    d = dict(slots)
    today = datetime.utcnow().date()
    if pid in ("lifeops_trip", "travel_explore"):
        # offline table first; unknown cities resolved via SerpApi google_flights_autocomplete (live mode)
        d["origin_iata"], _ = await resolve(slots.get("origin"), session_id, meter)
        d["destination_iata"], d["currency_code"] = await resolve(slots.get("destination"), session_id, meter)
        days = int(slots.get("days") or 4)
        out = today + timedelta(days=int(slots.get("lead_days") or 30))
        d["outbound_date"] = out.isoformat()
        d["return_date"] = (out + timedelta(days=days)).isoformat()
        d["outbound_date_flex"] = (out + timedelta(days=2)).isoformat()
        d["return_date_flex"] = (out + timedelta(days=days + 2)).isoformat()
        d["nights"] = days
    if pid in ("news_trends", "media_video", "finance_markets", "general_search", "media_images", "apps_store"):
        # market-scoped vertical playbooks: country from the slot (default us), with the Trends geo code
        # plus the Bing (mkt) and DuckDuckGo (kl) locale codes their news/video engines need
        mk = str(slots.get("market") or "us").lower()
        d["gl"], d["hl"] = mk, "en"
        d["geo"] = mk.upper()
        d["kl"] = f"{'uk' if mk == 'gb' else mk}-en"
        d["mkt"] = f"en-{mk.upper()}"
    if pid in ("lifeops_local", "research_seo"):
        gl = country_for(slots.get("city")) if pid == "lifeops_local" else str(slots.get("market") or "us").lower()
        d["gl"], d["hl"] = gl, "en"
        d["kl"] = f"{'uk' if gl == 'gb' else gl}-en"            # DuckDuckGo region code (us-en, uk-en, fr-fr …)
        d["mkt"] = f"en-{gl.upper()}"                             # Bing market (en-US, en-GB …)
        d["yelp_supported"] = gl in YELP_COUNTRIES
        if pid == "lifeops_local":
            d["min_rating"] = float(slots.get("min_rating") or 0)
            d["price_cap"] = int(slots.get("price_cap") or 4)
    if pid == "career_jobs":
        d["role_keyword"] = " ".join(str(slots.get("role", "")).split()[-2:]) or "developer"
    if pid == "research_ip":
        d["recent_year"] = today.year - 3
    return d


def _render(params: dict[str, Any], vars_: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in params.items():
        if isinstance(v, str):
            for m in re.findall(r"\{(\w+)\}", v):
                v = v.replace("{" + m + "}", str(vars_.get(m, "")))
        out[k] = v
    return out


# Dynamic API selection -------------------------------------------------------
# Optional engines only run when the prompt asks for them (trigger flags derived from the prompt),
# and every playbook is capped so a single prompt can never fan out to the whole catalogue.
MAX_CALLS_PER_PLAYBOOK = 4


def triggers_for(prompt: str, analysis: PromptAnalysis | None = None) -> dict[str, bool]:
    """Boolean intent flags read from the raw prompt (used by optional_engines[].when).

    Single source of truth is intent.PromptAnalysis, so the flags the UI shows in the routing
    panel are exactly the flags the engine selection used."""
    a = analysis or analyze_prompt(prompt or "")
    return {"wants_trending": a.wants_trending, "wants_light": a.wants_light, "wants_broad": a.wants_broad,
            "wants_shorts": a.wants_shorts, "wants_deals": a.wants_deals, "wants_images": a.wants_images}


def call_cap(pid: str) -> int:
    """Per-session SerpApi call cap: default 4; a playbook whose purpose is wide fan-out (multi-leg trip,
    7-engine SEO rank grid) declares its own `max_calls` so the cap never truncates its core engines."""
    return int(PLAYBOOKS[pid].get("max_calls", MAX_CALLS_PER_PLAYBOOK))


# Engines whose results decay within hours: a recency-flagged prompt marks their calls fresh
# (cache bypass + no_cache) even when the weaker recency wording ("recent", "this week") is used.
FRESH_SENSITIVE_ENGINES = {
    "google_news", "google_news_light", "bing_news", "duckduckgo_news", "youtube", "youtube_channel",
    "google_videos", "google_short_videos", "bing_videos", "yahoo_videos",
    "google_trends", "google_trends_trending_now", "google_finance", "google_finance_markets",
    "google_flights", "google_flights_deals",
}


def build_calls(pid: str, vars_: dict[str, Any], fallback_round: int = 0, triggers: dict[str, bool] | None = None,
                analysis: PromptAnalysis | None = None) -> list[EngineCall]:
    pb = PLAYBOOKS[pid]
    specs = pb["engines"] if fallback_round == 0 else pb.get("fallback_engines", [])
    if fallback_round > 1:  # second re-plan widens to all fallbacks + essentials again (fresh)
        specs = pb.get("fallback_engines", [])[::-1]
    specs = [sp for sp in specs if not sp.get("when") or vars_.get(sp["when"])]   # e.g. Yelp only where it operates
    if fallback_round == 0 and pb.get("optional_engines"):
        # optional engines are added only when the prompt's triggers ask for them (dynamic selection)
        flags = {**(triggers or {}), **{k: v for k, v in vars_.items() if isinstance(v, bool)}}
        extra = [sp for sp in pb["optional_engines"] if flags.get(sp.get("when", ""), False)]
        specs = specs + extra
    specs = specs[:call_cap(pid)] if fallback_round == 0 else specs
    a = analysis
    out = []
    for sp in specs:
        # freshness: re-polls are always live; "latest/breaking/today" makes every call live;
        # weaker recency wording only forces the freshness-sensitive engines live.
        fresh = fallback_round > 0 or (bool(a and a.fresh_strong) if a else False) or \
            (bool(a and a.recency) and sp["engine"] in FRESH_SENSITIVE_ENGINES if a else False)
        out.append(EngineCall(engine=sp["engine"], params=_render(sp["params"], vars_), purpose=sp.get("purpose", ""),
                              category=sp.get("category", "generic"), essential=sp.get("essential", True),
                              fresh=fresh, follow=sp.get("follow")))
    return out


def apply_recency_weights(pid: str, weights: dict[str, float], analysis: PromptAnalysis | None) -> tuple[dict[str, float], dict | None]:
    """Recency weight override (the "Top Hits 2026" fix): when the prompt demands freshness,
    the freshness dimension is raised to 0.45 (strong: latest/breaking/today) or 0.35 (weak),
    taking the delta proportionally from the other dimensions. Returns (weights, override|None)."""
    if not analysis or not analysis.recency or "freshness" not in weights:
        return weights, None
    target = 0.45 if analysis.fresh_strong else 0.35
    if weights["freshness"] >= target:
        return weights, None
    diff = target - weights["freshness"]
    rest = {k: v for k, v in weights.items() if k != "freshness"}
    tot = sum(rest.values()) or 1.0
    new_w = {"freshness": target}
    for k, v in rest.items():
        new_w[k] = round(max(0.01, v - diff * v / tot), 4)
    s = sum(new_w.values()) or 1.0
    new_w = {k: round(v / s, 4) for k, v in new_w.items()}
    return new_w, {"dimension": "freshness", "from": weights["freshness"], "to": new_w["freshness"],
                   "reason": "recency override (fresh_strong)" if analysis.fresh_strong else "recency override"}


async def plan(prompt: str, lens: str, session_id: str, forced: str | None = None,
               priorities: dict[str, float] | None = None, meter: CreditMeter | None = None) -> DecisionGraph:
    bus.publish(session_id, "agent.start", {"agent": "orchestrator", "label": "Classifying intent"}, agent="orchestrator")
    pid, scores = await classify(prompt, lens, forced)
    bus.publish(session_id, "orchestrator.intent", {"playbook_id": pid, "playbook": PLAYBOOKS[pid]["name"],
                                                     "scores": scores[:5]}, agent="orchestrator")
    top = scores[0] or {}
    analysis = PromptAnalysis(**(top.get("analysis") or {})) if top.get("analysis") else analyze_prompt(prompt)
    slots = await fill_slots(pid, prompt, session_id, analysis)
    vars_ = await _derive(pid, slots, session_id, meter)
    pb = PLAYBOOKS[pid]
    weights = {k: v["weight"] for k, v in pb["dimensions"].items()}
    weights, recency_override = apply_recency_weights(pid, weights, analysis)
    if priorities:
        for k, v in priorities.items():
            if k in weights:
                weights[k] = max(0.0, float(v))
        tot = sum(weights.values()) or 1
        weights = {k: round(v / tot, 4) for k, v in weights.items()}
    triggers = triggers_for(prompt, analysis)
    calls = build_calls(pid, vars_, triggers=triggers, analysis=analysis)
    skipped = [sp["engine"] for sp in pb.get("optional_engines", [])
               if not triggers.get(sp.get("when", ""), False)]
    bus.publish(session_id, "orchestrator.routing", {
        "intent_category": PLAYBOOKS[pid].get("intent_category", "GENERAL_SEARCH"), "playbook_id": pid,
        "playbook": pb["name"], "routed_by": top.get("routed_by"), "reason": top.get("reason"),
        "confidence": top.get("confidence"), "strong_hits": top.get("strong_hits"), "weak_hits": top.get("keyword_hits"),
        "llm_router": top.get("llm_router"), "analysis": analysis.as_dict(),
        "triggers": triggers, "engines": [c.engine for c in calls],
        "fresh": [c.engine for c in calls if c.fresh], "skipped_optional": skipped,
        "weight_override": recency_override, "weights": weights,
        "calls": len(calls), "max_calls": call_cap(pid)}, agent="orchestrator")

    nodes: list[DecisionNode] = []
    for k, v in slots.items():
        if v not in (None, ""):
            nodes.append(DecisionNode(id=f"ent_{k}", kind="entity", label=f"{k}: {v}"))
    for k, v in pb["dimensions"].items():
        nodes.append(DecisionNode(id=f"dim_{k}", kind="dimension", label=v["label"], meta={"weight": weights[k], "direction": v["direction"]}))
    if slots.get("budget"):
        nodes.append(DecisionNode(id="con_budget", kind="constraint", label=f"Total ≤ ${float(slots['budget']):,.0f}"))
    nodes.append(DecisionNode(id="con_verify", kind="constraint", label="Facts need ≥2 independent sources"))
    for c in calls:
        nodes.append(DecisionNode(id=c.id, kind="source", label=c.engine, meta={"purpose": c.purpose, "params": c.params}))
    for a in pb["actions"]:
        nodes.append(DecisionNode(id=f"act_{a}", kind="action", label=a))

    graph = DecisionGraph(playbook_id=pid, intent=pb["description"], lens=lens, slots=vars_, nodes=nodes, calls=calls, weights=weights)
    bus.publish(session_id, "orchestrator.graph", {"graph": graph.model_dump()}, agent="orchestrator")
    return graph

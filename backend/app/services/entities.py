"""Small entity helpers shared by the Researcher (corroboration), the Analyst
(cross-platform clustering) and the disruption injector: domain extraction,
fuzzy venue-name matching and `$`-price-level parsing."""
from __future__ import annotations

import math
import re
from urllib.parse import urlparse

_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}
_VENUE_STOP = {"the", "a", "and", "of", "at", "restaurant", "restaurants", "cafe", "bar", "grill", "kitchen", "austin", "tx", "bistro",
               "eatery", "house", "shop", "in", "on", "by", "co"}


def registrable_domain(host: str | None) -> str:
    """'en.wikipedia.org' -> 'wikipedia.org', 'www.bbc.co.uk' -> 'bbc.co.uk'."""
    if not host:
        return ""
    h = host.lower().strip().split("/")[0].split("›")[0].split(":")[0].strip(". ")
    h = re.sub(r"^www\d?\.", "", h)
    parts = [p for p in h.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    if len(parts[-1]) == 2 and parts[-2] in _SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def domain_of(url: str | None) -> str:
    if not url:
        return ""
    u = url if "://" in url else "//" + url
    try:
        return registrable_domain(urlparse(u).netloc)
    except Exception:
        return ""


def serp_domain(item: dict) -> str:
    """Domain of a SERP result. Handles redirect links (Baidu /link?url=, Bing /ck/a)
    by falling back to the displayed link / brand fields that SerpApi returns."""
    link = item.get("link") or ""
    host = domain_of(link)
    redirect = host.endswith("baidu.com") and "/link" in link or host.endswith("bing.com") and "/ck/" in link
    if not host or redirect:
        for k in ("displayed_brand", "displayed_link", "source"):
            v = item.get(k)
            if isinstance(v, str) and v:
                d = registrable_domain(re.sub(r"^https?://", "", v))
                if d and "." in d:
                    return d
    return host


def tokens(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in _VENUE_STOP and len(w) > 1}


def venue_key(name: str) -> str:
    return " ".join(sorted(tokens(name))) or (name or "").lower()


def same_entity(a: str, b: str, threshold: float = 0.6) -> bool:
    """Fuzzy match two venue names (token Jaccard, containment-friendly)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return (a or "").strip().lower() == (b or "").strip().lower()
    inter = len(ta & tb)
    if inter == 0:
        return False
    return inter / len(ta | tb) >= threshold or inter / min(len(ta), len(tb)) >= 0.99 and min(len(ta), len(tb)) >= 2


def price_level(v: str | int | float | None) -> int | None:
    """'$$' -> 2, '$$$$' -> 4. Ranges ('$$-$$$') -> upper bound. Numeric 1-4 passthrough."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v) if 1 <= v <= 4 else None
    m = re.findall(r"\${1,4}", str(v))
    return max(len(x) for x in m) if m else None


# ---------------------------------------------------------------- SEO model
# Share-of-voice weights per search engine (sum ≈ 1) and an organic CTR curve
# (≈ published position-CTR studies) used for the CTR-weighted visibility score.
ENGINE_WEIGHT = {"google": 0.40, "bing": 0.15, "duckduckgo": 0.08, "yahoo": 0.07, "yandex": 0.08, "baidu": 0.10, "naver": 0.05}
SERP_ENGINES = tuple(ENGINE_WEIGHT)
AI_ENGINES = ("google_ai_mode", "google_ai_overview")


def ctr(position: int | float | None) -> float:
    if not position or position < 1 or position > 30:
        return 0.0
    return 0.32 * math.pow(float(position), -0.95)


def page_offset(engine: str, params: dict | None) -> int:
    """How many results the engine skipped (pagination) according to its documented parameter."""
    p = params or {}
    try:
        if engine == "google" or engine == "duckduckgo":
            return int(p.get("start") or 0)
        if engine == "bing":
            return max(0, int(p.get("first") or 1) - 1)
        if engine == "yahoo":
            return max(0, int(p.get("b") or 1) - 1)
        if engine == "baidu":
            return int(p.get("pn") or 0)
        if engine == "yandex":
            return int(p.get("p") or 0) * 10
    except (TypeError, ValueError):
        return 0
    return 0


# ---------------------------------------------------------------- clustering
def cluster_venues(venues: list) -> dict[str, list]:
    """Union-find over fuzzy name matches so 'Casa Taqueria', 'Casa Taqueria - East Austin'
    and 'Casa Taqueria Restaurant' (Maps / Yelp / Tripadvisor) become ONE entity.
    Returns {cluster_id: [candidates]} and stamps ``attributes['cluster']`` on every member."""
    parent = list(range(len(venues)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(venues)):
        for j in range(i + 1, len(venues)):
            if venues[i].engine == venues[j].engine:
                continue                        # same platform never merges two listings
            if same_entity(venues[i].title, venues[j].title):
                parent[find(j)] = find(i)
    groups: dict[str, list] = {}
    for i, v in enumerate(venues):
        root = find(i)
        cid = venue_key(venues[root].title)
        groups.setdefault(cid, []).append(v)
    for cid, ms in groups.items():
        for m in ms:
            m.attributes["cluster"] = cid
    return groups


ENGINE_LABEL = {"google": "Google", "bing": "Bing", "duckduckgo": "DuckDuckGo", "yahoo": "Yahoo!", "yandex": "Yandex",
                "baidu": "Baidu", "naver": "Naver", "google_ai_mode": "Google AI Mode", "google_ai_overview": "AI Overview"}

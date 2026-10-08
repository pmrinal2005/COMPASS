"""Live SerpApi verification against https://serpapi.com (real HTTP, real data).

  python scripts/live_check.py                  # KEYLESS: free endpoints + documented error codes + keyless doc-example engines
  SERPAPI_KEY=xxxx python scripts/live_check.py # KEYED  : + Account API, one search per playbook engine (async -> Search Archive), normalised
  SERPAPI_KEY=xxxx python scripts/live_check.py --full   # + a complete COMPASS session per playbook (spends credits; see budget printed first)

Exit code 0 only when every executed check passed. Nothing here is mocked.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEMO_MODE", "false")

from app.playbooks import PLAYBOOKS  # noqa: E402
from app.services.normalize import normalize  # noqa: E402

BASE = "https://serpapi.com"
KEY = os.environ.get("SERPAPI_KEY", "")
FULL = "--full" in sys.argv
RESULTS: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name:58s} {detail}")


async def j(c: httpx.AsyncClient, path: str, **params) -> tuple[int, dict | list]:
    r = await c.get(path, params=params)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:120]}


# Doc-example queries (the ones serpapi.com itself answers without a key) per normalizer category.
CAT = {"google_maps": "venue", "yelp": "venue", "tripadvisor": "venue", "google": "serp", "bing": "serp", "duckduckgo": "serp", "yahoo": "serp",
       "yandex": "serp", "baidu": "serp", "naver": "serp", "google_ai_mode": "ai_citation"}
KEYLESS = {
    "bing": {"q": "Coffee"}, "duckduckgo": {"q": "Coffee"}, "yahoo": {"p": "Coffee"}, "yandex": {"text": "Coffee"}, "baidu": {"q": "Coffee"},
    "naver": {"query": "Coffee", "where": "web"}, "google": {"q": "Coffee"}, "yelp": {"find_desc": "Coffee", "find_loc": "Austin, Texas, United States"},
    "google_maps": {"q": "Coffee", "type": "search", "ll": "@40.7455096,-74.0083012,14z"}, "google_ai_mode": {"q": "Coffee"},
    "google_shopping": {"q": "Coffee"}, "google_shopping_light": {"q": "Coffee"}, "google_news": {"q": "Coffee"}, "google_scholar": {"q": "Coffee"},
    "google_patents": {"q": "coffee"}, "walmart": {"query": "coffee"}, "amazon": {"k": "Coffee"}, "ebay": {"_nkw": "Coffee"},
    "google_finance": {"q": "GOOGL:NASDAQ"}, "google_trends": {"q": "Coffee"}, "google_flights_autocomplete": {"q": "New"},
    "google_hotels": {"q": "Bali Resorts", "check_in_date": "2026-11-07", "check_out_date": "2026-11-11"},
}


def real_params(engine: str) -> dict:
    """One representative real query per engine, built from the playbook's own first call for that engine."""
    for pb in PLAYBOOKS.values():
        for sp in pb["engines"]:
            if sp["engine"] == engine:
                out = {}
                fill = {"query": "wireless earbuds", "city": "Austin, TX", "destination": "Tokyo", "gl": "us", "hl": "en", "kl": "us-en", "mkt": "en-US",
                        "keyword": "google search api", "domain": "serpapi.com", "currency_code": "JPY", "origin": "JFK", "dest": "HND",
                        "depart": str(date.today() + timedelta(days=45)), "return": str(date.today() + timedelta(days=49)), "topic": "solid-state battery",
                        "role": "react developer", "location": "United States", "product": "Sony WH-1000XM5"}
                for k, v in sp["params"].items():
                    if isinstance(v, str) and "{" in v:
                        for a, b in fill.items():
                            v = v.replace("{" + a + "}", b)
                        if "{" in v:
                            v = "coffee"
                    out[k] = v
                if engine == "google_flights":
                    out.update(departure_id="JFK", arrival_id="HND", outbound_date=fill["depart"], return_date=fill["return"], currency="USD", hl="en")
                if engine == "google_hotels":
                    out.update(q="Tokyo hotels", check_in_date=fill["depart"], check_out_date=fill["return"])
                return out
    return {"q": "coffee"}


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=90, headers={"User-Agent": "compass-live-check"}) as c:
        print(f"== COMPASS live check · mode={'KEYED' if KEY else 'KEYLESS'} · {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")

        # ---- free endpoints
        st, loc = await j(c, "/locations.json", q="Austin", limit=3)
        rec("Locations API (free, no key)", st == 200 and isinstance(loc, list) and loc and "canonical_name" in loc[0], f"{loc[0]['canonical_name']}" if st == 200 and loc else str(st))

        # ---- documented error contract, against the real service
        for name, path, extra in (("search  bad key -> 401", "/search.json", {"engine": "bing", "q": "x"}),
                                  ("archive bad key -> 401", "/searches/abc.json", {}),
                                  ("account bad key -> 401", "/account.json", {})):
            st, body = await j(c, path, api_key="invalid-key", **extra)
            rec(f"Error contract: {name}", st == 401 and "Invalid API key" in json.dumps(body), f"HTTP {st}")
        st, body = await j(c, "/search.json", engine="google_events", q="Events in Austin", api_key="invalid-key")
        rec("google_events: deprecated upstream (HTTP 400/401, never 200)", st in (400, 401), f"HTTP {st} {str(body)[:60]}")

        # ---- keyless engines: real HTTP -> our normalizers (data is whatever SerpApi serves keyless)
        ok = 0
        for engine, params in KEYLESS.items():
            st, d = await j(c, "/search.json", engine=engine, **params)
            if st != 200 or not isinstance(d, dict) or (d.get("search_metadata") or {}).get("status") != "Success":
                rec(f"keyless {engine}", False, f"HTTP {st} {str(d)[:70]}")
                continue
            cands, ctx = normalize(engine, d, CAT.get(engine, "generic"), params)
            has_signal = bool(cands or ctx or d.get("suggestions"))           # autocomplete answers with suggestions[]
            ok += has_signal
            rec(f"keyless {engine} -> normalized", has_signal, f"{len(cands)} candidates, ctx={list(ctx)}")
        # ---- async + archive (documented flow) - works keyless for the demo queries too
        st, sub = await j(c, "/search.json", engine="bing", q="Coffee", **{"async": "true"})   # keyless access is limited to serpapi.com's own demo query
        if st == 200 and isinstance(sub, dict) and sub.get("search_metadata", {}).get("status") in ("Queued", "Processing", "Success"):
            ep = sub["search_metadata"].get("json_endpoint")
            final = None
            for _ in range(15):
                await asyncio.sleep(1.5)
                r = await httpx.AsyncClient(timeout=30).get(ep) if ep else None
                if r is not None and r.status_code == 200 and r.json().get("search_metadata", {}).get("status") == "Success":
                    final = r.json()
                    break
            rec("async=true -> poll json_endpoint -> Success", final is not None and bool(final.get("organic_results")),
                f"id={sub['search_metadata']['id'][:10]}…")
        else:
            rec("async=true submit", False, f"HTTP {st} {str(sub)[:80]}")

        # ---- keyed section
        if KEY:
            st, acc = await j(c, "/account.json", api_key=KEY)
            rec("Account API (keyed)", st == 200 and "total_searches_left" in acc, f"{acc.get('plan_name')} · {acc.get('total_searches_left')} searches left" if st == 200 else str(acc))
            left = int(acc.get("total_searches_left") or 0) if st == 200 else 0
            engines = sorted({sp["engine"] for pb in PLAYBOOKS.values() for sp in pb["engines"]})
            print(f"   keyed sweep: {len(engines)} engines (1 credit each, cached results are free) — {left} credits left")
            if left >= len(engines) + 5:
                for engine in engines:
                    params = real_params(engine)
                    st, sub = await j(c, "/search.json", engine=engine, api_key=KEY, output="json", **{"async": "true"}, **params)
                    if st != 200 or not isinstance(sub, dict):
                        rec(f"live {engine}", False, f"HTTP {st} {str(sub)[:90]}")
                        continue
                    sid, data = (sub.get("search_metadata") or {}).get("id"), sub
                    for _ in range(25):
                        if (data.get("search_metadata") or {}).get("status") in ("Success", "Error"):
                            break
                        await asyncio.sleep(1.5)
                        st, data = await j(c, f"/searches/{sid}.json", api_key=KEY)
                    okk = (data.get("search_metadata") or {}).get("status") == "Success"
                    cat = next((sp["category"] for pb in PLAYBOOKS.values() for sp in pb["engines"] if sp["engine"] == engine), "generic")
                    cands, ctx = normalize(engine, data, cat, params) if okk else ([], {})
                    note = data.get("error", "") if isinstance(data, dict) else ""
                    rec(f"live {engine} (async→archive) -> normalized", okk and bool(cands or ctx or "hasn't returned any results" in note),
                        f"{len(cands)} candidates ctx={list(ctx)} {note[:50]}")
            else:
                rec("keyed sweep", False, f"need >= {len(engines) + 5} credits, have {left}")
            if FULL:
                os.environ["SERPAPI_KEY"] = KEY
                from app import graph as G
                from app.config import get_settings
                get_settings.cache_clear()
                prompts = {"lifeops_trip": ("Plan a 4-day Tokyo trip under $1,200, flights + hotel", "go"), "lifeops_local": ("Best tacos in Austin, TX", "go"),
                           "research_seo": ('Track SEO visibility of serpapi.com for "google search api"', "pro")}
                for pid, (prompt, lens) in prompts.items():
                    t0 = time.time()
                    stt = await G.run_session(f"live_{pid}", prompt, lens, None, None, True)
                    rows = ((stt.get("analysis") or {}).get("matrix") or {}).get("rows") or []
                    rec(f"FULL session {pid}", bool(rows), f"{len(rows)} ranked · conf={stt.get('confidence')} · {time.time() - t0:.0f}s · credits={G.rt(f'live_{pid}').meter.as_dict()}")
        else:
            print("   (no SERPAPI_KEY: keyed sweep skipped — set SERPAPI_KEY to verify Flights/Hotels/Maps/Yelp/Tripadvisor/Jobs/Airbnb with your account)")

    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

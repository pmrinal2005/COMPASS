"""Snapshot the *documented* SerpApi parameters straight from serpapi.com so playbooks can be validated against the real docs.

  python scripts/docs_sync.py            # fetch every engine page used by the playbooks -> app/playbooks/serpapi_params.json
  python scripts/docs_sync.py --offline  # just print what the committed snapshot contains

The doc pages render each parameter as ``<div class="param-item">`` with a ``param-name`` and a ``param-req`` (Required|Optional) node.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "app" / "docs" / "serpapi_params.json"
PAGES = {
    "google": "search-api", "google_maps": "google-maps-api", "google_flights": "google-flights-api", "google_hotels": "google-hotels-api",
    "google_flights_autocomplete": "google-flights-autocomplete-api", "google_jobs": "google-jobs-api", "google_finance": "google-finance-api",
    "google_shopping": "google-shopping-api", "google_shopping_light": "google-shopping-light-api", "google_events": "google-events-api",
    "google_ai_mode": "google-ai-mode-api", "google_ai_overview": "google-ai-overview-api", "google_trends": "google-trends-api",
    "google_scholar": "google-scholar-api", "google_patents": "google-patents-api", "google_news": "google-news-api",
    "yelp": "yelp-search-api", "tripadvisor": "tripadvisor-search-api", "airbnb": "airbnb-search-api", "amazon": "amazon-search-api",
    "walmart": "walmart-search-api", "ebay": "ebay-search-api", "bing": "bing-search-api", "duckduckgo": "duckduckgo-search-api",
    "yahoo": "yahoo-search-api", "yandex": "yandex-search-api", "baidu": "baidu-search-api", "naver": "naver-search-api",
}
ITEM = re.compile(r'<p class="param-name"><span class="parameter-highlight">([^<]+)</span></p>\s*<p class="param-req([^"]*)">([^<]+)</p>')


def parse(page_html: str) -> dict[str, bool]:
    """-> {param_name: required}"""
    out: dict[str, bool] = {}
    for name, _cls, req in ITEM.findall(page_html):
        for n in html.unescape(name).split("/"):          # e.g. "q / query"
            out[n.strip()] = req.strip().lower() == "required"
    return out


def main() -> None:
    if "--offline" in sys.argv:
        snap = json.loads(OUT.read_text())
        for e, p in snap["engines"].items():
            print(f"{e:30s} {len(p):3d} params  required={[k for k, v in p.items() if v]}")
        return
    snap = {"source": "https://serpapi.com/<engine>-api", "engines": {}}
    with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
        for engine, page in PAGES.items():
            r = c.get(f"https://serpapi.com/{page}")
            r.raise_for_status()
            params = parse(r.text)
            assert params, f"no parameters parsed for {engine} ({page})"
            snap["engines"][engine] = params
            print(f"{engine:30s} {len(params):3d} params  required={[k for k, v in params.items() if v]}")
    OUT.write_text(json.dumps(snap, indent=1, sort_keys=True))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

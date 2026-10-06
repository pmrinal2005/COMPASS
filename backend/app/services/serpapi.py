"""SerpApi Researcher transport.

Implements the documented SerpApi contract:
  * GET https://serpapi.com/search.json?engine=...&api_key=...  (Search API)
  * async=true  -> returns immediately with search_metadata.id + status
                   "Queued"/"Processing"; results are fetched from the
                   Search Archive API GET /searches/{id}.json until status
                   becomes "Success" or "Error".
  * HTTP 429 (throughput / out of searches) and 5xx -> exponential backoff.
  * HTTP 400/401/403/404/410 -> non-retryable; top-level "error" key surfaced.
  * Empty results still have status "Success" (not treated as failures).

Concurrency is bounded by a per-session asyncio.Semaphore; identical calls
are deduplicated through the Redis/memory cache before any credit is spent.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from ..config import get_settings
from .cache import cache, call_fingerprint
from .demo_data import demo_response
from .events import bus
from .tracing import tracer

RETRYABLE = {429, 500, 502, 503, 504}


class SerpApiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class CreditMeter:
    """Visible per-session credit budget (1 live SerpApi search = 1 credit)."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.spent = 0
        self.cached = 0

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.spent)

    def as_dict(self) -> dict:
        return {"budget": self.budget, "spent": self.spent, "remaining": self.remaining, "cached": self.cached}


class SerpApiClient:
    def __init__(self) -> None:
        self.s = get_settings()
        self._client: httpx.AsyncClient | None = None
        self.total_live_calls = 0

    async def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.s.serpapi_base, timeout=httpx.Timeout(30, connect=10))
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------ live
    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        c = await self.client()
        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(self.s.serp_max_retries + 1):
            try:
                r = await c.get(path, params=params)
            except httpx.TransportError as e:  # network blip -> retry
                last_err = e
            else:
                if r.status_code == 200:
                    return r.json()
                try:
                    msg = r.json().get("error", r.text[:200])
                except Exception:
                    msg = r.text[:200]
                if r.status_code not in RETRYABLE:
                    raise SerpApiError(msg, r.status_code)
                last_err = SerpApiError(msg, r.status_code)
            if attempt < self.s.serp_max_retries:
                await asyncio.sleep(delay + random.random() * 0.4)
                delay *= 2
        raise last_err or SerpApiError("unknown SerpApi failure")

    async def _search_async(self, engine: str, params: dict[str, Any], fresh: bool) -> dict:
        q = {**params, "engine": engine, "api_key": self.s.serpapi_key, "async": "true", "output": "json"}
        if fresh:
            q["no_cache"] = "true"
        first = await self._get("/search.json", q)
        meta = first.get("search_metadata", {})
        status = meta.get("status")
        if status == "Success":
            return first
        sid = meta.get("id")
        if not sid:
            raise SerpApiError(first.get("error", "no search id returned"))
        deadline = time.monotonic() + self.s.serp_poll_timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(self.s.serp_poll_interval)
            res = await self._get(f"/searches/{sid}.json", {"api_key": self.s.serpapi_key})
            st = res.get("search_metadata", {}).get("status")
            if st == "Success":
                return res
            if st == "Error":
                raise SerpApiError(res.get("error", "search error"))
        raise SerpApiError(f"async search {sid} timed out")

    # --------------------------------------------------------------- public
    async def search(
        self,
        engine: str,
        params: dict[str, Any],
        *,
        session_id: str,
        call_id: str,
        sem: asyncio.Semaphore,
        meter: CreditMeter,
        purpose: str = "",
        fresh: bool = False,
    ) -> dict:
        """Returns {"data": <serpapi json>, "cached": bool, "ms": int, "mode": live|demo}."""
        key = call_fingerprint(engine, params)
        if not fresh:
            hit = await cache.get(key)
            if hit is not None:
                meter.cached += 1
                bus.publish(session_id, "serp.cached", {"call_id": call_id, "engine": engine, "params": params,
                                                        "purpose": purpose, "key": key[-10:], "credits": meter.as_dict()},
                            agent="researcher")
                tracer.span(session_id, f"serpapi:{engine}", {"params": params, "cached": True}, {"cache_key": key})
                return {"data": hit, "cached": True, "ms": 0, "mode": "cache"}

        if meter.remaining <= 0:
            raise SerpApiError("session credit budget exhausted", 402)

        bus.publish(session_id, "serp.request", {"call_id": call_id, "engine": engine, "params": params,
                                                 "purpose": purpose, "async": True}, agent="researcher")
        t0 = time.perf_counter()
        async with sem:
            if self.s.is_demo:
                await asyncio.sleep(0.35 + random.random() * 0.9)  # realistic async latency
                data = demo_response(engine, params)
                mode = "demo"
            else:
                data = await self._search_async(engine, params, fresh)
                self.total_live_calls += 1
                mode = "live"
        ms = int((time.perf_counter() - t0) * 1000)
        meter.spent += 1
        await cache.set(key, data)
        tracer.span(session_id, f"serpapi:{engine}", {"params": params, "cached": False},
                    {"status": data.get("search_metadata", {}).get("status"), "ms": ms})
        return {"data": data, "cached": False, "ms": ms, "mode": mode}


serp = SerpApiClient()

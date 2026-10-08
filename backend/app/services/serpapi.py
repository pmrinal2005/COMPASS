"""SerpApi Researcher transport — implemented against the official docs
(https://serpapi.com/search-api, /search-archive-api, /account-api,
/api-status-and-error-codes).

Documented contract honoured here
  * GET https://serpapi.com/search.json?engine=...&api_key=...&output=json
  * ``async=true``  -> the search is only *submitted*; the response carries
    search_metadata.id and status Queued/Processing. Results are fetched from
    the Search Archive API ``GET /searches/{id}.json`` until the status flips to
    ``Success`` or ``Error`` (flow: Queued -> Processing -> Success || Error).
  * ``async`` and ``no_cache`` MUST NOT be combined. A *fresh* poll therefore
    runs as a blocking search with ``no_cache=true`` (never async); a normal
    search runs async and may be served from SerpApi's 1-hour cache for free.
  * ``async`` must not be used on accounts with Ludicrous Speed, and ZeroTrace
    (Enterprise, ``zero_trace=true``) stores no search files, so the archive
    cannot serve them -> both force blocking mode. If an async submission is
    rejected for an async-related reason we transparently fall back to sync.
  * HTTP codes: 200 ok · 400 bad request · 401 bad key · 403 forbidden ·
    404 not found · 410 Gone (archive entry expired/deleted) · 429 (hourly
    throughput limit OR "run out of searches") · 500/503 server error.
    Only 429-throughput and 5xx are retried (exponential backoff + jitter);
    "run out of searches", 4xx and 410 are surfaced immediately.
  * A search can be ``Success`` yet contain a top-level ``error`` (e.g. Google
    returned no results). That is an *empty* result, not a failure.
  * Account API (free, not counted) -> remaining credits / hourly throughput.
Identical calls are deduplicated through Redis/memory before any credit is spent.
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

RETRYABLE = {500, 502, 503, 504}


class SerpApiError(Exception):
    def __init__(self, message: str, status: int | None = None, *, retryable: bool = False, kind: str = "error") -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.kind = kind  # error | out_of_searches | throttled | gone | auth | bad_request


def classify_error(status: int, message: str) -> SerpApiError:
    """Map a documented HTTP status + message to a typed error."""
    m = (message or "").lower()
    if status == 429:
        if "run out of searches" in m or "out of searches" in m or "no searches left" in m:
            return SerpApiError(message, 429, retryable=False, kind="out_of_searches")
        return SerpApiError(message, 429, retryable=True, kind="throttled")  # hourly throughput limit
    if status == 410:
        return SerpApiError(message or "search expired and was deleted from the archive", 410, kind="gone")
    if status in (401, 403):
        return SerpApiError(message, status, kind="auth")
    if status in RETRYABLE:
        return SerpApiError(message, status, retryable=True)
    return SerpApiError(message, status, kind="bad_request" if status == 400 else "error")


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
        self.async_calls = 0
        self.sync_calls = 0
        self._async_ok = True               # flips to False if the account rejects async
        self._account: tuple[float, dict] | None = None

    # ------------------------------------------------------------------ http
    async def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.s.serpapi_base,
                                             timeout=httpx.Timeout(self.s.serp_sync_timeout, connect=10))
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @property
    def use_async(self) -> bool:
        return bool(self.s.serp_async and self._async_ok and not self.s.serpapi_zero_trace)

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        c = await self.client()
        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(self.s.serp_max_retries + 1):
            try:
                r = await c.get(path, params=params)
            except httpx.TransportError as e:  # network blip / timeout -> retry
                last_err = SerpApiError(f"transport error: {e!r}"[:200], None, retryable=True)
            else:
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception as e:
                        raise SerpApiError(f"invalid JSON from SerpApi: {e!r}"[:160], 200)
                try:
                    body = r.json()
                    msg = body.get("error", r.text[:200]) if isinstance(body, dict) else r.text[:200]
                except Exception:
                    msg = r.text[:200]
                err = classify_error(r.status_code, msg)
                if not err.retryable:
                    raise err
                last_err = err
            if attempt < self.s.serp_max_retries:
                await asyncio.sleep(delay + random.random() * 0.4)
                delay *= 2
        raise last_err or SerpApiError("unknown SerpApi failure")

    # --------------------------------------------------------------- queries
    def build_query(self, engine: str, params: dict[str, Any], *, fresh: bool, use_async: bool) -> dict[str, Any]:
        """Documented query string. ``async`` XOR ``no_cache`` is enforced here."""
        q = {k: v for k, v in params.items() if v not in (None, "")}
        q.update({"engine": engine, "api_key": self.s.serpapi_key, "output": "json"})
        if self.s.serpapi_zero_trace:
            q["zero_trace"] = "true"
        if fresh:
            q["no_cache"] = "true"          # fresh => blocking search, never async
        elif use_async:
            q["async"] = "true"
        return q

    async def _search_sync(self, engine: str, params: dict[str, Any], fresh: bool) -> dict:
        q = self.build_query(engine, params, fresh=fresh, use_async=False)
        res = await self._get("/search.json", q)
        self.sync_calls += 1
        return self._finalize(res)

    async def _search_async(self, engine: str, params: dict[str, Any]) -> dict:
        q = self.build_query(engine, params, fresh=False, use_async=True)
        first = await self._get("/search.json", q)
        self.async_calls += 1
        meta = first.get("search_metadata") or {}
        status = meta.get("status")
        if status == "Success":
            return self._finalize(first)
        if status == "Error":
            raise SerpApiError(first.get("error", "search error"), 503)
        sid = meta.get("id")
        if not sid:
            raise SerpApiError(first.get("error", "no search id returned for async search"))
        deadline = time.monotonic() + self.s.serp_poll_timeout
        interval = self.s.serp_poll_interval
        while time.monotonic() < deadline:
            await asyncio.sleep(interval)
            interval = min(interval * 1.25, 4.0)
            # Search Archive API: GET /searches/{search_id}.json?api_key=...
            res = await self._get(f"/searches/{sid}.json", {"api_key": self.s.serpapi_key})
            st = (res.get("search_metadata") or {}).get("status")
            if st == "Success":
                return self._finalize(res)
            if st == "Error":
                raise SerpApiError(res.get("error", "search error"), 503)
            # Queued / Processing -> keep polling
        raise SerpApiError(f"async search {sid} still not finished after {self.s.serp_poll_timeout:.0f}s", 504, retryable=False)

    @staticmethod
    def _finalize(data: dict) -> dict:
        st = (data.get("search_metadata") or {}).get("status")
        if st == "Error":
            raise SerpApiError(data.get("error", "search error"), 503)
        # status Success (+ possibly an `error` key meaning 'no results') is a valid empty result
        return data

    async def _live(self, engine: str, params: dict[str, Any], fresh: bool) -> tuple[dict, str]:
        if fresh or not self.use_async:
            return await self._search_sync(engine, params, fresh), "sync"
        try:
            return await self._search_async(engine, params), "async"
        except SerpApiError as e:
            msg = str(e).lower()
            if e.status in (400, 403) and "async" in msg:   # e.g. Ludicrous Speed accounts
                self._async_ok = False
                return await self._search_sync(engine, params, False), "sync"
            if e.status == 410 or e.kind == "gone":           # archive entry vanished -> run again blocking
                return await self._search_sync(engine, params, False), "sync"
            raise

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
        """Returns {"data": <serpapi json>, "cached": bool, "ms": int, "mode": live|demo|cache, "transport": async|sync|demo}."""
        key = call_fingerprint(engine, params)
        if not fresh:
            hit = await cache.get(key)
            if hit is not None:
                meter.cached += 1
                bus.publish(session_id, "serp.cached", {"call_id": call_id, "engine": engine, "params": params,
                                                        "purpose": purpose, "key": key[-10:], "credits": meter.as_dict()},
                            agent="researcher")
                tracer.span(session_id, f"serpapi:{engine}", {"params": params, "cached": True}, {"cache_key": key})
                return {"data": hit, "cached": True, "ms": 0, "mode": "cache", "transport": "cache"}

        if meter.remaining <= 0:
            raise SerpApiError("session credit budget exhausted", 402, kind="budget")

        transport = "demo" if self.s.is_demo else ("sync" if (fresh or not self.use_async) else "async")
        bus.publish(session_id, "serp.request", {"call_id": call_id, "engine": engine, "params": params, "purpose": purpose,
                                                 "async": transport == "async", "transport": transport, "fresh": fresh},
                    agent="researcher")
        t0 = time.perf_counter()
        async with sem:
            if self.s.is_demo:
                await asyncio.sleep(0.35 + random.random() * 0.9)  # realistic async latency
                data = demo_response(engine, params)
                mode = "demo"
            else:
                data, transport = await self._live(engine, params, fresh)
                self.total_live_calls += 1
                mode = "live"
        ms = int((time.perf_counter() - t0) * 1000)
        meter.spent += 1
        await cache.set(key, data)
        tracer.span(session_id, f"serpapi:{engine}", {"params": params, "cached": False, "transport": transport},
                    {"status": (data.get("search_metadata") or {}).get("status"), "ms": ms})
        return {"data": data, "cached": False, "ms": ms, "mode": mode, "transport": transport}

    # -------------------------------------------------------------- account
    async def account(self, force: bool = False) -> dict:
        """SerpApi Account API (free, not counted toward the quota).
        Sensitive fields (api_key, e-mail, account id) are never returned."""
        now = time.time()
        if not force and self._account and now - self._account[0] < self.s.account_cache_seconds:
            return self._account[1]
        if self.s.is_demo:
            out = {"demo": True, "account_status": "Demo Mode", "plan_name": "Demo (no SERPAPI_KEY)", "searches_per_month": 0,
                   "plan_searches_left": 0, "extra_credits": 0, "total_searches_left": 0, "this_month_usage": 0,
                   "this_hour_searches": 0, "last_hour_searches": 0, "account_rate_limit_per_hour": 0, "plan_renewal_date": None}
        else:
            raw = await self._get("/account.json", {"api_key": self.s.serpapi_key})
            keep = ("account_status", "plan_name", "plan_monthly_price", "plan_renewal_date", "searches_per_month", "plan_searches_left",
                    "extra_credits", "total_searches_left", "this_month_usage", "this_hour_searches", "last_hour_searches",
                    "account_rate_limit_per_hour")
            out = {k: raw.get(k) for k in keep}
            out["demo"] = False
        out["fetched_at"] = now
        self._account = (now, out)
        return out


serp = SerpApiClient()

"""Short-TTL dedupe cache. Upstash Redis (REST API, serverless) when
configured; otherwise an in-process TTL dict so local dev needs nothing."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from ..config import get_settings


def call_fingerprint(engine: str, params: dict[str, Any]) -> str:
    """Hash of normalized engine + params (api_key / async flags excluded)."""
    skip = {"api_key", "async", "no_cache", "output"}
    norm = {k: str(v).strip().lower() for k, v in sorted(params.items()) if k not in skip and v not in (None, "")}
    raw = json.dumps({"engine": engine, "params": norm}, sort_keys=True)
    return "serp:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


class Cache:
    def __init__(self) -> None:
        self.s = get_settings()
        self._mem: dict[str, tuple[float, str]] = {}
        self.hits = 0
        self.misses = 0

    @property
    def backend(self) -> str:
        return "upstash" if self.s.has_redis else "memory"

    async def _redis(self, *cmd: Any) -> Any:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.post(
                self.s.upstash_redis_rest_url,
                headers={"Authorization": f"Bearer {self.s.upstash_redis_rest_token}"},
                json=[str(x) for x in cmd],
            )
            r.raise_for_status()
            return r.json().get("result")

    async def get(self, key: str) -> Any | None:
        val: str | None = None
        if self.s.has_redis:
            try:
                val = await self._redis("GET", key)
            except Exception:
                val = None
        if val is None:
            item = self._mem.get(key)
            if item and item[0] > time.time():
                val = item[1]
            elif item:
                self._mem.pop(key, None)
        if val is None:
            self.misses += 1
            return None
        self.hits += 1
        try:
            return json.loads(val)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or self.s.cache_ttl_seconds
        payload = json.dumps(value, default=str)
        self._mem[key] = (time.time() + ttl, payload)
        if len(self._mem) > 1500:  # bound memory on 512MB hosts
            for k in sorted(self._mem, key=lambda k: self._mem[k][0])[:300]:
                self._mem.pop(k, None)
        if self.s.has_redis:
            try:
                await self._redis("SET", key, payload, "EX", ttl)
            except Exception:
                pass

    async def delete(self, key: str) -> None:
        self._mem.pop(key, None)
        if self.s.has_redis:
            try:
                await self._redis("DEL", key)
            except Exception:
                pass

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {"backend": self.backend, "hits": self.hits, "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0}


cache = Cache()

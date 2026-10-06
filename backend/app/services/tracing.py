"""Langfuse Cloud tracing via its public ingestion REST API (no SDK, no
self-hosting). Spans are buffered in-process and flushed in the
background; the same spans are kept locally so the Command Center's
raw-calls tab works even without a Langfuse key."""
from __future__ import annotations

import asyncio
import base64
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import get_settings


def _iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), tz=timezone.utc).isoformat().replace("+00:00", "Z")


class Tracer:
    def __init__(self) -> None:
        self.s = get_settings()
        self._buffer: list[dict] = []
        self.local: dict[str, list[dict]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _auth(self) -> str:
        tok = f"{self.s.langfuse_public_key}:{self.s.langfuse_secret_key}".encode()
        return "Basic " + base64.b64encode(tok).decode()

    def trace(self, session_id: str, name: str, input_: Any = None, metadata: dict | None = None) -> None:
        self._buffer.append({
            "id": str(uuid.uuid4()), "timestamp": _iso(), "type": "trace-create",
            "body": {"id": session_id, "name": name, "input": input_, "metadata": metadata or {},
                     "tags": ["compass"], "timestamp": _iso()},
        })

    def span(self, session_id: str, name: str, input_: Any = None, output: Any = None, start: float | None = None) -> None:
        now = time.time()
        span = {"id": str(uuid.uuid4()), "traceId": session_id, "name": name, "input": input_, "output": output,
                "startTime": _iso(start or now), "endTime": _iso(now)}
        self.local[session_id].append({**span, "ts": now})
        if len(self.local[session_id]) > 500:
            self.local[session_id] = self.local[session_id][-500:]
        self._buffer.append({"id": str(uuid.uuid4()), "timestamp": _iso(), "type": "span-create", "body": span})

    def generation(self, session_id: str, name: str, model: str, input_: Any, output: Any) -> None:
        body = {"id": str(uuid.uuid4()), "traceId": session_id, "name": name, "model": model,
                "input": input_, "output": output, "startTime": _iso(), "endTime": _iso()}
        self.local[session_id].append({**body, "ts": time.time(), "kind": "generation"})
        self._buffer.append({"id": str(uuid.uuid4()), "timestamp": _iso(), "type": "generation-create", "body": body})

    async def flush(self) -> int:
        if not self.s.has_langfuse or not self._buffer:
            self._buffer.clear() if not self.s.has_langfuse else None
            return 0
        async with self._lock:
            batch, self._buffer = self._buffer[:200], self._buffer[200:]
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(f"{self.s.langfuse_host}/api/public/ingestion",
                                 headers={"Authorization": self._auth()}, json={"batch": batch})
            except Exception:
                pass
            return len(batch)

    async def fetch_remote(self, session_id: str) -> dict | None:
        """Read the trace back from Langfuse Cloud (powers the raw-calls tab)."""
        if not self.s.has_langfuse:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{self.s.langfuse_host}/api/public/traces/{session_id}",
                                headers={"Authorization": self._auth()})
                if r.status_code == 200:
                    return r.json()
        except Exception:
            return None
        return None

    def trace_url(self, session_id: str) -> str | None:
        return f"{self.s.langfuse_host}/trace/{session_id}" if self.s.has_langfuse else None

    async def run_flusher(self) -> None:
        while True:
            await asyncio.sleep(3)
            try:
                await self.flush()
            except Exception:
                pass


tracer = Tracer()

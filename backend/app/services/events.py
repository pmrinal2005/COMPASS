"""Per-session event bus. Agents publish typed events; the SSE endpoint
streams them to the Command Center. Every event is also retained so a
late-joining client (or a page refresh) replays the full thought-tree."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any


class EventBus:
    def __init__(self, max_history: int = 2000) -> None:
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._seq: dict[str, int] = defaultdict(int)
        self._max = max_history

    def publish(self, session_id: str, type_: str, data: dict[str, Any] | None = None, agent: str | None = None) -> dict:
        self._seq[session_id] += 1
        evt = {
            "seq": self._seq[session_id],
            "ts": time.time(),
            "type": type_,
            "agent": agent,
            "data": data or {},
        }
        hist = self._history[session_id]
        hist.append(evt)
        if len(hist) > self._max:
            del hist[: len(hist) - self._max]
        for q in list(self._subs[session_id]):
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:  # pragma: no cover - slow client
                pass
        return evt

    def history(self, session_id: str, after: int = 0) -> list[dict]:
        return [e for e in self._history.get(session_id, []) if e["seq"] > after]

    def has(self, session_id: str) -> bool:
        return bool(self._history.get(session_id))

    def load(self, session_id: str, events: list[dict]) -> None:
        """Rehydrate a session's event history (e.g. after a Render restart) so late SSE clients can replay it."""
        self._history[session_id] = list(events)[-self._max:]
        self._seq[session_id] = max((e.get("seq", 0) for e in events), default=0)

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._subs[session_id].append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        if q in self._subs.get(session_id, []):
            self._subs[session_id].remove(q)


bus = EventBus()

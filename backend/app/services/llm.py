"""Hosted LLM + embedding calls (Groq free tier primary, Gemini free tier
fallback). Nothing is loaded locally. When no key is configured a
deterministic heuristic path keeps every agent functional."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

import httpx

from ..config import get_settings
from .tracing import tracer


class LLM:
    def __init__(self) -> None:
        self.s = get_settings()

    @property
    def provider(self) -> str:
        if self.s.groq_api_key:
            return "groq"
        if self.s.gemini_api_key:
            return "gemini"
        return "heuristic"

    async def _groq(self, system: str, user: str, json_mode: bool) -> str:
        body: dict[str, Any] = {"model": self.s.groq_model, "temperature": 0.2,
                                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                             headers={"Authorization": f"Bearer {self.s.groq_api_key}"}, json=body)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _gemini(self, system: str, user: str, json_mode: bool) -> str:
        body: dict[str, Any] = {"systemInstruction": {"parts": [{"text": system}]},
                                "contents": [{"role": "user", "parts": [{"text": user}]}],
                                "generationConfig": {"temperature": 0.2}}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent"
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, params={"key": self.s.gemini_api_key}, json=body)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    async def complete(self, system: str, user: str, *, json_mode: bool = False, session_id: str | None = None,
                       name: str = "llm") -> str | None:
        out: str | None = None
        used = None
        for prov in (["groq"] if self.s.groq_api_key else []) + (["gemini"] if self.s.gemini_api_key else []):
            try:
                out = await (self._groq if prov == "groq" else self._gemini)(system, user, json_mode)
                used = prov
                break
            except Exception:
                continue
        if session_id and out is not None:
            tracer.generation(session_id, name, used or "none", {"system": system[:400], "user": user[:1500]}, out[:2000])
        return out

    async def complete_json(self, system: str, user: str, **kw: Any) -> dict | None:
        raw = await self.complete(system, user, json_mode=True, **kw)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    return None
        return None


class Embedder:
    """Gemini embedding API (free tier). Fallback: deterministic hashed
    bag-of-words + char-trigram vector (same dimension, L2-normalized) so
    cosine retrieval still behaves sensibly in Demo Mode."""

    def __init__(self) -> None:
        self.s = get_settings()

    @property
    def provider(self) -> str:
        return "gemini" if self.s.gemini_api_key else "hashed-local"

    def _local(self, text: str) -> list[float]:
        dim = self.s.embed_dim
        v = [0.0] * dim
        t = text.lower()
        toks = re.findall(r"[a-z0-9]+", t)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])] + [t[i:i + 3] for i in range(0, max(0, len(t) - 2), 2)]
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            v[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    async def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        if not texts:
            return []
        if self.s.gemini_api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_embed_model}:batchEmbedContents"
                reqs = [{"model": f"models/{self.s.gemini_embed_model}", "content": {"parts": [{"text": t[:2000]}]},
                         "taskType": task, "outputDimensionality": self.s.embed_dim} for t in texts[:100]]
                async with httpx.AsyncClient(timeout=30) as c:
                    r = await c.post(url, params={"key": self.s.gemini_api_key}, json={"requests": reqs})
                    r.raise_for_status()
                    vecs = [e["values"] for e in r.json()["embeddings"]]
                out = []
                for v in vecs:
                    n = math.sqrt(sum(x * x for x in v)) or 1.0
                    out.append([x / n for x in v])
                if len(texts) > 100:
                    out += await self.embed(texts[100:], task)
                return out
            except Exception:
                pass
        return [self._local(t) for t in texts]


llm = LLM()
embedder = Embedder()

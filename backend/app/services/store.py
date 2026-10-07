"""Persistence + hybrid retrieval.

Supabase (PostgREST over HTTPS — no driver, no local DB) when configured:
  * documents table with pgvector `embedding` + tsvector `fts`
  * RPC `hybrid_search(query_text, query_embedding, match_count, ...)` that
    fuses dense cosine rank and Postgres full-text rank with Reciprocal
    Rank Fusion (see supabase/migrations).
  * sessions / actions / watches / price_history / playbooks tables.

Fallback: an in-memory store that implements the *same* RRF hybrid
algorithm (cosine + BM25) so behaviour is identical in Demo Mode.
"""
from __future__ import annotations

import math
import re
import time
from collections import Counter, defaultdict
from typing import Any

import httpx

from ..config import get_settings

RRF_K = 50


def _tok(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 1]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class Store:
    def __init__(self) -> None:
        self.s = get_settings()
        self.docs: list[dict] = []
        self.tables: dict[str, dict[str, dict]] = defaultdict(dict)
        self.price_history: dict[str, list[tuple[float, float]]] = defaultdict(list)

    @property
    def backend(self) -> str:
        return "supabase-pgvector" if self.s.has_supabase else "memory-hybrid"

    # ---------------------------------------------------------- supabase io
    def _h(self, prefer: str | None = None) -> dict:
        h = {"apikey": self.s.supabase_service_key, "Authorization": f"Bearer {self.s.supabase_service_key}",
             "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        return h

    async def _sb(self, method: str, path: str, *, json: Any = None, params: dict | None = None, prefer: str | None = None) -> Any:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.request(method, f"{self.s.supabase_url}/rest/v1/{path}", headers=self._h(prefer), json=json, params=params)
            r.raise_for_status()
            return r.json() if r.content else None

    # ------------------------------------------------------------ documents
    async def upsert_documents(self, docs: list[dict]) -> int:
        """docs: {id, session_id, engine, category, title, content, url, price, embedding, metadata}"""
        if not docs:
            return 0
        for d in docs:
            d.setdefault("created_at", time.time())
        if self.s.has_supabase:
            try:
                rows = [{k: d.get(k) for k in ("id", "session_id", "engine", "category", "title", "content", "url", "price", "embedding", "metadata")}
                        for d in docs]
                await self._sb("POST", "documents", json=rows, prefer="resolution=merge-duplicates,return=minimal")
                return len(rows)
            except Exception:
                pass  # fall through to memory so the session still works
        ids = {d["id"] for d in docs}
        self.docs = [d for d in self.docs if d["id"] not in ids] + docs
        if len(self.docs) > 4000:
            self.docs = self.docs[-4000:]
        return len(docs)

    async def hybrid_search(self, query: str, qvec: list[float], k: int = 12, session_id: str | None = None,
                            category: str | None = None) -> list[dict]:
        if self.s.has_supabase:
            try:
                rows = await self._sb("POST", "rpc/hybrid_search", json={
                    "query_text": query, "query_embedding": qvec, "match_count": k,
                    "filter_session": session_id, "filter_category": category, "rrf_k": RRF_K})
                return rows or []
            except Exception:
                pass
        pool = [d for d in self.docs if (not session_id or d.get("session_id") == session_id)
                and (not category or d.get("category") == category)]
        if not pool:
            return []
        # dense ranking
        dense = sorted(pool, key=lambda d: -_cos(qvec, d.get("embedding") or [0.0]))
        # BM25 keyword ranking
        q = _tok(query)
        N = len(pool)
        df = Counter(w for d in pool for w in set(_tok(d.get("title", "") + " " + d.get("content", ""))))
        avgdl = sum(len(_tok(d.get("content", ""))) for d in pool) / N or 1

        def bm25(d: dict) -> float:
            toks = _tok(d.get("title", "") + " " + d.get("content", ""))
            tf = Counter(toks)
            sc = 0.0
            for w in q:
                if w not in tf:
                    continue
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                sc += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(toks) / avgdl))
            return sc

        kw_scores = {d["id"]: bm25(d) for d in pool}
        keyword = sorted([d for d in pool if kw_scores[d["id"]] > 0], key=lambda d: -kw_scores[d["id"]])
        fused: dict[str, float] = defaultdict(float)
        dr, kr = {}, {}
        for i, d in enumerate(dense[: k * 3]):
            fused[d["id"]] += 1 / (RRF_K + i + 1)
            dr[d["id"]] = i + 1
        for i, d in enumerate(keyword[: k * 3]):
            fused[d["id"]] += 1 / (RRF_K + i + 1)
            kr[d["id"]] = i + 1
        by_id = {d["id"]: d for d in pool}
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [{**{kk: vv for kk, vv in by_id[i].items() if kk != "embedding"}, "rrf_score": round(s, 5),
                 "dense_rank": dr.get(i), "keyword_rank": kr.get(i),
                 "similarity": round(_cos(qvec, by_id[i].get("embedding") or [0.0]), 4)} for i, s in ranked]

    # --------------------------------------------------------- generic rows
    async def put(self, table: str, row: dict) -> dict:
        self.tables[table][row["id"]] = row
        if self.s.has_supabase:
            try:
                await self._sb("POST", table, json=row, prefer="resolution=merge-duplicates,return=minimal")
            except Exception:
                pass
        return row

    async def get(self, table: str, id_: str) -> dict | None:
        if id_ in self.tables[table]:
            return self.tables[table][id_]
        if self.s.has_supabase:
            try:
                rows = await self._sb("GET", table, params={"id": f"eq.{id_}", "limit": "1"})
                if rows:
                    self.tables[table][id_] = rows[0]
                    return rows[0]
            except Exception:
                return None
        return None

    async def list(self, table: str, limit: int = 100, **eq: Any) -> list[dict]:
        if self.s.has_supabase:
            try:
                params = {"limit": str(limit), "order": "created_at.desc"}
                params.update({k: f"eq.{v}" for k, v in eq.items()})
                rows = await self._sb("GET", table, params=params)
                for r in rows or []:
                    self.tables[table][r["id"]] = r
                if rows is not None:
                    return rows
            except Exception:
                pass
        rows = [r for r in self.tables[table].values() if all(r.get(k) == v for k, v in eq.items())]
        return sorted(rows, key=lambda r: -float(r.get("created_at") or 0))[:limit]

    # ------------------------------------------------- playbooks (pgvector)
    async def sync_playbooks(self, playbooks: dict[str, dict], vecs: dict[str, list[float]]) -> bool:
        """Upsert the Playbook library + embeddings into Supabase so intent
        classification can run as a pgvector similarity query."""
        if not self.s.has_supabase:
            return False
        try:
            rows = [{"id": pid, "name": pb["name"], "lens": pb.get("lens"), "spec": pb, "embedding": vecs.get(pid)}
                    for pid, pb in playbooks.items()]
            await self._sb("POST", "playbooks", json=rows, prefer="resolution=merge-duplicates,return=minimal")
            return True
        except Exception:
            return False

    async def match_playbooks(self, qvec: list[float], k: int = 10) -> dict[str, float] | None:
        """RPC public.match_playbooks -> {playbook_id: cosine similarity}."""
        if not self.s.has_supabase:
            return None
        try:
            rows = await self._sb("POST", "rpc/match_playbooks", json={"query_embedding": qvec, "match_count": k})
            return {r["id"]: float(r["similarity"]) for r in rows or []} or None
        except Exception:
            return None

    # -------------------------------------------------------- price history
    async def record_price(self, key: str, price: float) -> None:
        self.price_history[key].append((time.time(), price))
        self.price_history[key] = self.price_history[key][-200:]
        if self.s.has_supabase:
            try:
                await self._sb("POST", "price_history", json={"item_key": key, "price": price}, prefer="return=minimal")
            except Exception:
                pass

    async def get_prices(self, key: str, limit: int = 50) -> list[float]:
        if self.s.has_supabase:
            try:
                rows = await self._sb("GET", "price_history", params={"item_key": f"eq.{key}", "order": "observed_at.desc", "limit": str(limit)})
                if rows:
                    return [float(r["price"]) for r in reversed(rows)]
            except Exception:
                pass
        return [p for _, p in self.price_history.get(key, [])[-limit:]]


store = Store()

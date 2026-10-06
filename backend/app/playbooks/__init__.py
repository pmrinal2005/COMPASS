"""Playbook library: declarative JSON specs (engines, RAG sources,
comparison dimensions, action connectors). Loaded from disk, embedded and
(optionally) synced into Supabase pgvector for intent matching."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).parent


def load_playbooks() -> dict[str, dict[str, Any]]:
    out = {}
    for f in sorted(DIR.glob("*.json")):
        pb = json.loads(f.read_text())
        out[pb["id"]] = pb
    return out


PLAYBOOKS = load_playbooks()


def playbook_text(pb: dict) -> str:
    return " ".join([pb["name"], pb["description"], " ".join(pb.get("keywords", [])), " ".join(pb.get("examples", []))])

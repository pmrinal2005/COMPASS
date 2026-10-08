"""Guards the contract between the backend and the Next.js Command Center (no network, 0 credits):
  * the bundled offline Playbook library == GET /api/playbooks (so the UI never shows a stale copy)
  * every recorded scenario carries the events the reducer/stepper/insight panels depend on
  * the GitHub Actions scheduler workflows referenced by README / render.yaml exist and target the real endpoints
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.playbooks import PLAYBOOKS

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "frontend" / "lib" / "demo"
REC = json.loads((DEMO / "recordings.json").read_text())
LIB = json.loads((DEMO / "playbooks.json").read_text())

SCENARIO_INSIGHT = {"tacos": "venues", "seo": "seo", "tokyo": "trip"}
STAGES = {"plan", "research", "verify", "analyze", "act", "done"}       # the stepper's Plan/Search/Verify/Compare/Act + terminal
DISRUPTION = {"tokyo": "price_spike", "headphones": "price_spike", "tacos": "rating_drop", "seo": "rank_drop"}


def _summary(pb: dict) -> dict:
    item = {k: v for k, v in pb.items() if k != "fallback_engines"}
    item["engine_list"] = sorted({e["engine"] for e in pb["engines"]})
    item["fallback_engine_list"] = sorted({e["engine"] for e in pb.get("fallback_engines", [])})
    return item


def test_offline_playbook_library_matches_backend():
    assert {p["id"] for p in LIB} == set(PLAYBOOKS), "frontend/lib/demo/playbooks.json is stale: run scripts/record_demo.py"
    by_id = {p["id"]: p for p in LIB}
    for pid, pb in PLAYBOOKS.items():
        assert json.loads(json.dumps(_summary(pb))) == by_id[pid], f"{pid} drifted from the bundled copy"


def test_every_playbook_is_describable_by_the_library_panel():
    for pid, pb in PLAYBOOKS.items():
        assert pb["examples"], pid
        assert pb["lens"] in ("go", "pro") and pb["ecosystem"] in ("A", "B", "C"), pid
        assert pb["dimensions"] and all({"weight", "direction", "label"} <= set(d) for d in pb["dimensions"].values()), pid
        assert abs(sum(d["weight"] for d in pb["dimensions"].values()) - 1) < 0.02, f"{pid}: dimension weights should sum to 1"


@pytest.mark.parametrize("key", sorted(REC))
def test_recording_drives_every_panel(key):
    ev = REC[key]["events"]
    types = [e["type"] for e in ev]
    for need in ("session.start", "orchestrator.intent", "orchestrator.graph", "serp.request", "serp.response", "rag.retrieval",
                 "rag.verification", "analyst.matrix", "actor.proposal", "session.complete"):
        assert need in types, f"{key}: missing {need}"
    assert STAGES <= {e["data"].get("stage") for e in ev if e["type"] == "stage"}, f"{key}: stepper needs every stage event"
    intent = next(e for e in ev if e["type"] == "orchestrator.intent")["data"]
    assert len(intent["scores"]) >= 3 and all({"id", "name", "score", "cosine", "keyword_hits"} <= set(s) for s in intent["scores"])
    assert [e["seq"] for e in ev] == sorted(e["seq"] for e in ev)
    ins = next(e for e in ev if e["type"] == "analyst.matrix")["data"].get("insights")
    if key in SCENARIO_INSIGHT:
        assert ins and ins["kind"] == SCENARIO_INSIGHT[key], f"{key}: insights panel would be empty"


def test_insight_payload_shapes():
    seo = next(e for e in REC["seo"]["events"] if e["type"] == "analyst.matrix")["data"]["insights"]
    assert len(seo["grid"]) == 7 and {"engine", "label", "weight", "position", "found", "ctr"} <= set(seo["grid"][0])
    assert seo["leaders"] and {"google_ai_mode", "google_ai_overview"} == {a["engine"] for a in seo["ai"]}
    ven = next(e for e in REC["tacos"]["events"] if e["type"] == "analyst.matrix")["data"]["insights"]
    v = ven["venues"][0]
    assert {"id", "title", "rating", "platforms", "verified", "spread"} <= set(v) and len(v["platforms"]) >= 2
    trip = next(e for e in REC["tokyo"]["events"] if e["type"] == "analyst.matrix")["data"]["insights"]
    assert trip["stays"] and trip["events"]


@pytest.mark.parametrize("key,kind", sorted(DISRUPTION.items()))
def test_recorded_disruption_replans_within_the_cap(key, kind):
    d = REC[key]["disruption"]
    assert d["kind"] == kind
    types = [e["type"] for e in d["events"]]
    assert "watch.repoll" in types and "analyst.anomaly" in types and "orchestrator.replan" in types
    loops = [e for e in d["events"] if e["type"] == "orchestrator.replan"]
    assert 1 <= len(loops) <= loops[0]["data"]["max"] == 2
    assert any(e["type"] == "actor.superseded" for e in d["events"]) or any(e["type"] == "actor.proposal" for e in d["events"])


def test_watch_proposals_cover_price_rating_position():
    metrics = set()
    for r in REC.values():
        for e in r["events"]:
            if e["type"] == "actor.proposal" and e["data"]["action"]["type"] == "watch":
                metrics.add(e["data"]["action"]["payload"].get("metric", "price"))
    assert metrics == {"price", "rating", "position"}


@pytest.mark.parametrize("name,needs", [("watch-cron.yml", ["/api/watch/tick", "x-cron-secret", "CRON_SECRET", "COMPASS_API_URL", "cron:"]),
                                        ("keep-warm.yml", ["/api/health", "COMPASS_API_URL", "cron:"])])
def test_scheduler_workflows_exist(name, needs):
    path = ROOT / ".github" / "workflows" / name
    assert path.exists(), f"{name} is referenced by README/render.yaml but missing"
    text = path.read_text()
    doc = yaml.safe_load(text)
    assert doc["jobs"] and (doc.get(True) or doc.get("on")), "workflow needs a trigger"        # PyYAML parses the key `on` as True
    for n in needs:
        assert n in text, f"{name} should mention {n}"
    assert "workflow_dispatch" in text


def test_render_blueprint_matches_the_scheduler_story():
    r = yaml.safe_load((ROOT / "render.yaml").read_text())
    svc = r["services"][0]
    assert svc["runtime"] == "python" and svc["healthCheckPath"] == "/api/health" and "Dockerfile" not in json.dumps(r)
    keys = {e["key"] for e in svc["envVars"]}
    assert {"SERPAPI_KEY", "CRON_SECRET", "MAX_REPLANS", "SESSION_CREDIT_BUDGET", "FRONTEND_ORIGINS"} <= keys
    assert (ROOT / "supabase" / "migrations" / "0002_sessions_persistence.sql").exists()

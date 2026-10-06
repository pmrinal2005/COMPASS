"""Record real COMPASS event streams (Demo Mode backend) into a fixture the
frontend replays when no backend is reachable ("pre-cached Demo Mode").
Usage:  cd backend && PYTHONPATH=. python scripts/record_demo.py"""
import asyncio
import json
import os
from pathlib import Path

os.environ.setdefault("DEMO_MODE", "true")

from app import graph as G  # noqa: E402
from app.agents import actor  # noqa: E402
from app.agents.researcher import candidate_key  # noqa: E402
from app.models import Candidate  # noqa: E402
from app.services.events import bus  # noqa: E402

SCENARIOS = [
    ("tokyo", "Plan a 4-day Tokyo trip under $1,200, flights + hotel", "go", True),
    ("earbuds", "Source 3 reliable suppliers for bulk Bluetooth earbuds, compare price/MOQ/reviews", "pro", False),
    ("headphones", "Find the best deal on Sony WH-1000XM5 headphones", "go", True),
    ("jobs", "Remote senior React developer jobs", "go", False),
    ("prior_art", "Prior art for solid-state battery dendrite suppression", "pro", False),
]


def rel(events, t0):
    return [{**e, "t": round(e["ts"] - t0, 3)} for e in events]


async def receipts_for(sid):
    out = {}
    for a in list(G.rt(sid).actions.values()):
        if a.status == "pending":
            r = await actor.execute(a.model_copy(deep=True))
            r.pop("html", None)
            out[a.id] = r
    return out


async def main():
    rec = {}
    for key, prompt, lens, disrupt in SCENARIOS:
        sid = f"demo_{key}"
        await G.run_session(sid, prompt, lens, None, None, True)
        hist = bus.history(sid)
        t0 = hist[0]["ts"]
        entry = {"prompt": prompt, "lens": lens, "events": rel(hist, t0), "receipts": await receipts_for(sid)}
        if disrupt:
            top = G.rt(sid).state["_ranked"][0]
            tgt = Candidate(**top.attributes["flight"]) if top.category == "bundle" else top
            n0 = len(bus.history(sid))
            await G.repoll(sid, {"kind": "price_spike", "pct": 45, "target_key": candidate_key(tgt), "target_title": tgt.title})
            dh = bus.history(sid)[n0:]
            entry["disruption"] = {"events": rel(dh, dh[0]["ts"]), "receipts": await receipts_for(sid)}
        # strip heavy raw payloads beyond 2 items (already trimmed) and binary screenshots
        rec[key] = entry
        print(key, len(entry["events"]), "events", "+disruption" if disrupt else "")
    out = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "demo" / "recordings.json"
    out.write_text(json.dumps(rec, default=str, separators=(",", ":")))
    print("wrote", out, round(out.stat().st_size / 1024), "KB")


asyncio.run(main())

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
from app.services.events import bus  # noqa: E402

# (key, prompt, lens, disruption kind | None)
SCENARIOS = [
    ("tokyo", "Plan a 4-day Tokyo trip under $1,200, flights + hotel", "go", "price_spike"),
    ("earbuds", "Source 3 reliable suppliers for bulk Bluetooth earbuds, compare price/MOQ/reviews", "pro", None),
    ("headphones", "Find the best deal on Sony WH-1000XM5 headphones", "go", "price_spike"),
    ("jobs", "Remote senior React developer jobs", "go", None),
    ("prior_art", "Prior art for solid-state battery dendrite suppression", "pro", None),
    ("tacos", "Best tacos in Austin, TX under $$ with 4.5+ rating", "go", "rating_drop"),
    ("seo", "Track SEO visibility of serpapi.com for \"google search api\" across search engines", "pro", "rank_drop"),
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
            n0 = len(bus.history(sid))
            await G.repoll(sid, G.make_disruption(sid, disrupt))
            dh = bus.history(sid)[n0:]
            entry["disruption"] = {"kind": disrupt, "events": rel(dh, dh[0]["ts"]), "receipts": await receipts_for(sid)}
        # strip heavy raw payloads beyond 2 items (already trimmed) and binary screenshots
        rec[key] = entry
        print(key, len(entry["events"]), "events", f"+disruption({disrupt})" if disrupt else "")
    out = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "demo" / "recordings.json"
    out.write_text(json.dumps(rec, default=str, separators=(",", ":")))
    print("wrote", out, round(out.stat().st_size / 1024), "KB")
    # offline copy of the Playbook library for the UI's library panel (same shape as GET /api/playbooks)
    from app.playbooks import PLAYBOOKS
    lib = []
    for pb in PLAYBOOKS.values():
        item = {k: v for k, v in pb.items() if k != "fallback_engines"}
        item["engine_list"] = sorted({e["engine"] for e in pb["engines"]})
        item["fallback_engine_list"] = sorted({e["engine"] for e in pb.get("fallback_engines", [])})
        lib.append(item)
    out2 = out.with_name("playbooks.json")
    out2.write_text(json.dumps(lib, separators=(",", ":")))
    print("wrote", out2, round(out2.stat().st_size / 1024), "KB")


asyncio.run(main())

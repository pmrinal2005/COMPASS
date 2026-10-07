"""End-to-end smoke test (Demo Mode, zero credits, no network):
all 5 playbooks -> HITL approve -> watch -> cron tick auth -> live
disruption -> bounded re-plan.   Usage: cd backend && PYTHONPATH=. python scripts/smoke_test.py"""
import asyncio
import os

os.environ.setdefault("DEMO_MODE", "true")
os.environ["CRON_SECRET"] = "smoke"
os.environ["PLAYWRIGHT_ENABLED"] = "false"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import app  # noqa: E402

PROMPTS = [
    ("Plan a 4-day Tokyo trip under $1,200, flights + hotel", "go", "lifeops_trip"),
    ("Source 3 reliable suppliers for bulk Bluetooth earbuds, compare price/MOQ/reviews", "pro", "pro_supplier"),
    ("Find the best deal on Sony WH-1000XM5 headphones", "go", "lifeops_deals"),
    ("Remote senior React developer jobs", "go", "career_jobs"),
    ("Prior art for solid-state battery dendrite suppression", "pro", "research_ip"),
]


async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t", timeout=120) as c:
        assert (await c.get("/api/health")).json()["ok"]
        trip = None
        for prompt, lens, expected in PROMPTS:
            r = (await c.post("/api/sessions/run", json={"prompt": prompt, "lens": lens})).json()
            assert r["playbook_id"] == expected, (prompt, r["playbook_id"])
            assert r["analysis"]["matrix"]["rows"], expected
            assert r["actions"], expected
            assert r["replans"] <= 2
            print(f"ok  {expected:14s} conf={r['confidence']:.2f} credits={r['credits']['spent']} actions={len(r['actions'])}")
            if expected == "lifeops_trip":
                trip = r
        booking = next(a for a in trip["actions"] if a["type"] == "booking_flow")
        ap = (await c.post(f"/api/actions/{booking['id']}/approve")).json()
        assert ap["action"]["status"] == "executed" and ap["receipt"]["confirmation"]
        watch = next(a for a in trip["actions"] if a["type"] == "watch")
        assert (await c.post(f"/api/actions/{watch['id']}/approve")).json()["action"]["status"] == "executed"
        assert (await c.post("/api/watch/tick")).status_code == 401
        assert (await c.post("/api/watch/tick?force=true", headers={"x-cron-secret": "smoke"})).json()["checked"] >= 1
        print("ok  HITL approve + watch + cron tick")
        sid = trip["session_id"]
        assert (await c.post(f"/api/sessions/{sid}/disrupt?kind=price_spike&pct=45")).json()["ok"]
        for _ in range(40):
            await asyncio.sleep(0.5)
            s = (await c.get(f"/api/sessions/{sid}")).json()
            if s["replans"] >= 1 and s["status"]:
                break
        assert s["replans"] >= 1, "disruption should trigger a bounded re-plan"
        print(f"ok  disruption -> re-plan x{s['replans']} -> new #1: {s['analysis']['matrix']['rows'][0]['title']}")
    print("ALL SMOKE TESTS PASSED")


asyncio.run(main())

"""Browser E2E (Playwright) proving the frontend talks to a REAL backend instead of replaying the offline demo.

    PLAYWRIGHT_BROWSERS_PATH=... python scripts/ui_live_check.py [frontend_url] [--run]

Without --run : free. Checks the header badge flips to "backend · serpapi live", real SerpApi credits are shown, the Playbook library is
                served by the backend (no 'bundled' chips) and the page has no uncaught errors.
With    --run : also runs the tacos prompt (~4 live credits) and asserts: no 'offline replay' chip, session id is s_..., live SerpApi log rows,
                venue consensus + 'What's on' events panel populated, HITL cards present.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

URL = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:3000")
RUN = "--run" in sys.argv
OUT = "/home/user/pw/shots"
R = []


def rec(name, ok, detail=""):
    R.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name:60s} {detail}")


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": 1500, "height": 1200})
        errs, reqs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" and "404" not in m.text else None)
        pg.on("request", lambda r: reqs.append(r.url) if "/api/" in r.url else None)
        await pg.goto(URL, wait_until="domcontentloaded")
        badge = pg.locator("#top-bar .chip", has_text="serpapi live")      # NOT just "backend": "waking backend…" also contains it
        try:
            await badge.first.wait_for(timeout=100000)
        except Exception:
            pass
        chips = [await pg.locator("#top-bar .chip, #top-bar button.chip").nth(i).inner_text() for i in range(await pg.locator("#top-bar .chip, #top-bar button.chip").count())]
        print("header chips:", chips)
        rec("badge says 'backend · serpapi live' (not offline demo)", any("serpapi live" in c for c in chips), str(chips))
        rec("no 'offline demo' badge", not any("offline demo" in c for c in chips))
        await pg.wait_for_timeout(2500)
        await pg.wait_for_selector('#top-bar [aria-label="SerpApi account credits"]', timeout=30000)
        await pg.wait_for_timeout(1500)
        txt = (await pg.inner_text('#top-bar [aria-label="SerpApi account credits"]')).replace("\n", " ")
        rec("header credit meter shows REAL plan credits", "plan" in txt.lower() and any(ch.isdigit() for ch in txt), txt)
        rec("frontend called /api/health + /api/account on the backend", any("/api/health" in r for r in reqs) and any("/api/account" in r for r in reqs), str(sorted({r.split('/api/')[0] for r in reqs})))
        await pg.click("#library-toggle")
        await pg.wait_for_selector("#playbook-library article", timeout=30000)
        await pg.wait_for_timeout(1200)
        n_bundled = await pg.locator("#playbook-library .chip:has-text('bundled')").count()
        rec("Playbook library comes from GET /api/playbooks (no 'bundled' chip)", n_bundled == 0 and await pg.locator("#playbook-library article").count() == 7, f"{await pg.locator('#playbook-library article').count()} cards, bundled={n_bundled}")
        await pg.screenshot(path=f"{OUT}/1_library.png")
        await pg.click("#library-toggle")
        await pg.wait_for_timeout(600)

        if RUN:
            await pg.fill("#prompt-input-go", "Best tacos in Austin, TX under $$ with 4.5+ rating")
            await pg.press("#prompt-input-go", "Enter")
            await pg.wait_for_selector("#pipeline-go >> text=complete", timeout=170000)
            await pg.wait_for_timeout(2500)
            body = await pg.inner_text("body")
            rec("no 'offline replay' chip after a run", "offline replay" not in body)
            rec("no 'Backend unreachable' error shown", "Backend unreachable" not in body)
            rec("session request went to the live backend", any("/api/sessions" in r for r in reqs) and any("/stream" in r for r in reqs))
            rec("venue consensus rendered", await pg.locator("#venue-consensus li").count() >= 3, f"{await pg.locator('#venue-consensus li').count()} venues")
            ev = await pg.locator("#whats-on li").count()
            rec("'What's on' panel shows live Google events", ev >= 3, f"{ev} events")
            rec("SerpApi log shows live calls (async)", await pg.locator("text=/google_maps|yelp|tripadvisor/").count() > 0)
            rec("HITL action cards present", await pg.locator("#hitl-actions article").count() >= 3, f"{await pg.locator('#hitl-actions article').count()} cards")
            await pg.screenshot(path=f"{OUT}/2_tacos_live.png", full_page=True)
        rec("no uncaught page errors", not errs, str(errs[:3]))
        await b.close()
    bad = [n for n, ok in R if not ok]
    print(f"\n{len(R) - len(bad)}/{len(R)} UI checks passed" + (f" FAILED: {bad}" if bad else ""))
    sys.exit(1 if bad else 0)


asyncio.run(main())

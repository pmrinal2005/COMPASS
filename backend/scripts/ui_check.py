"""Browser end-to-end check of the Command Center (Playwright, runs against any deployed/local frontend).

    pip install playwright && python -m playwright install chromium
    python scripts/ui_check.py [http://localhost:3000]

Exercises: Playbook library, pipeline stepper, intent bars, venue consensus / SEO grid / trip extras, the playbook-aware
disruption button + bounded re-plan, the HITL watch approval -> Watches tab -> "Check now", and split-screen.
Works with a live backend (real /api/watches ticks) and offline (simulated polls); fails on any uncaught page error."""
import sys

import asyncio
from playwright.async_api import async_playwright
URL=(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000").rstrip("/")
if not URL.endswith("/dashboard"): URL += "/dashboard"   # the Command Center lives at /dashboard (landing page is /)
async def run(pg, lens, text, wait="complete"):
    await pg.fill(f"#prompt-input-{lens}", text); await pg.press(f"#prompt-input-{lens}", "Enter")
    await pg.wait_for_selector(f"#pipeline-{lens} >> text=complete", timeout=120000); await pg.wait_for_timeout(1200)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"]); pg = await b.new_page(viewport={"width":1500,"height":1100})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text[:160]) if m.type=="error" and "404" not in m.text else None)
        await pg.goto(URL, wait_until="networkidle"); await pg.wait_for_timeout(800)
        print("badges:", [await pg.locator("#top-bar .chip").nth(i).inner_text() for i in range(await pg.locator("#top-bar .chip").count())])
        await pg.click("#library-toggle"); await pg.wait_for_selector("#playbook-library article")
        print("library:", await pg.locator("#playbook-library article").count(), "|", await pg.locator("#playbook-library .chip:has-text('bundled')").count(), "bundled")
        await pg.click("#library-toggle"); await pg.wait_for_timeout(700)
        for lens, text, tag in [("go","Best tacos in Austin, TX under $$ with 4.5+ rating","venues"),("pro",'Track SEO visibility of serpapi.com for "google search api"',"seo"),("go","Plan a 4-day Tokyo trip under $1,200, flights + hotel","trip")]:
            if lens=="pro": await pg.click("#lens-toggle button:has-text('Pro')")
            else: await pg.click("#lens-toggle button:has-text('Go')")
            await run(pg, lens, text)
            ins = await pg.locator(f"#insights-{lens} .chip").last.inner_text()
            btn = (await pg.inner_text(f"#disrupt-{lens}")).strip()
            await pg.click(f"#disrupt-{lens}"); await pg.wait_for_selector(f"#pipeline-{lens} >> text=/re-plan/", timeout=60000); await pg.wait_for_timeout(6000)
            print(f"{tag}: insights={ins} disrupt='{btn}' loops={await pg.locator(f'#pipeline-{lens} >> text=/re-plan/').count()}")
        # offline watch simulation (tacos)
        await pg.click("#lens-toggle button:has-text('Go')"); await run(pg,"go","Best tacos in Austin, TX under $$ with 4.5+ rating")
        await pg.locator("#hitl-actions article:has-text('Watch this venue')").first.locator("button:has-text('Approve')").click()
        await pg.wait_for_selector("#hitl-actions >> text=Action receipt", timeout=20000)
        await pg.click("#tab-watches-go"); await pg.wait_for_selector("#watches-go li[data-watch]")
        for i in range(3):
            await pg.locator("#watches-go li[data-watch] button:has-text('Check now')").first.click(); await pg.wait_for_timeout(1600)
        print("sim watch:", (await pg.locator("#watches-go li[data-watch]").first.inner_text()).replace("\n"," | ")[:230])
        print("simulated chip:", await pg.locator("#watches-go >> text=simulated polls").count())
        await pg.screenshot(path="/tmp/off_watches.png")
        # split
        await pg.click("#split-toggle"); await pg.wait_for_timeout(700)
        await pg.fill("#prompt-input-go","Plan a 4-day Tokyo trip"); await pg.press("#prompt-input-go","Enter")
        await pg.fill("#prompt-input-pro","Source 3 reliable suppliers for bulk Bluetooth earbuds"); await pg.press("#prompt-input-pro","Enter")
        await pg.wait_for_selector("#pipeline-go >> text=complete", timeout=120000); await pg.wait_for_selector("#pipeline-pro >> text=complete", timeout=120000)
        await pg.screenshot(path="/tmp/off_split.png"); print("split OK; ERRORS:", errs)
        await b.close()
asyncio.run(main())

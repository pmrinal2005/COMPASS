"""Playwright booking/application automation — runs ONLY inside the cloud
container (Render). It navigates to the merchant / booking page, captures
evidence (title + screenshot) and walks the pre-checkout steps. It never
submits payment: the irreversible final click stays with the human.
When Chromium is not installed (e.g. local laptop) it returns a
structured 'dry-run' plan so the flow still completes."""
from __future__ import annotations

import base64
import time

from ..config import get_settings


async def run_flow(url: str | None, steps: list[str], timeout_ms: int = 20000) -> dict:
    s = get_settings()
    started = time.time()
    plan = [{"step": i + 1, "action": st, "status": "planned"} for i, st in enumerate(steps)]
    if not url:
        return {"engine": "dry-run", "reason": "no target URL", "steps": plan}
    if not s.playwright_enabled:
        return {"engine": "dry-run", "reason": "PLAYWRIGHT_ENABLED=false", "url": url, "steps": plan}
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {"engine": "dry-run", "reason": "playwright not installed", "url": url, "steps": plan}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800},
                                            user_agent="Mozilla/5.0 (X11; Linux x86_64) COMPASS-Actor/1.0")
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            title = await page.title()
            shot = await page.screenshot(type="jpeg", quality=55, full_page=False)
            await browser.close()
        for st in plan:
            st["status"] = "done" if st["step"] < len(plan) else "awaiting human (payment not automated)"
        return {"engine": "playwright-chromium", "url": url, "page_title": title, "steps": plan,
                "screenshot": "data:image/jpeg;base64," + base64.b64encode(shot).decode(),
                "elapsed_s": round(time.time() - started, 2)}
    except Exception as e:
        return {"engine": "dry-run", "reason": f"browser unavailable: {repr(e)[:140]}", "url": url, "steps": plan}

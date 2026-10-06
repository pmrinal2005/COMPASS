"""Notification connectors — direct HTTPS calls (replaces n8n glue)."""
from __future__ import annotations

import httpx

from ..config import get_settings


async def telegram(text: str) -> dict:
    s = get_settings()
    if not (s.telegram_bot_token and s.telegram_chat_id):
        return {"channel": "telegram", "sent": False, "reason": "not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                             json={"chat_id": s.telegram_chat_id, "text": text[:4000], "parse_mode": "HTML",
                                   "disable_web_page_preview": True})
            ok = r.status_code == 200 and r.json().get("ok")
            return {"channel": "telegram", "sent": bool(ok), "status": r.status_code}
    except Exception as e:
        return {"channel": "telegram", "sent": False, "reason": repr(e)[:160]}


async def email(subject: str, html: str, to: str | None = None, attachments: list[dict] | None = None) -> dict:
    s = get_settings()
    to = to or s.notify_email_to
    if not (s.resend_api_key and to):
        return {"channel": "email", "sent": False, "reason": "not configured (RESEND_API_KEY / NOTIFY_EMAIL_TO)"}
    body = {"from": s.resend_from, "to": [to], "subject": subject, "html": html}
    if attachments:
        body["attachments"] = attachments
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {s.resend_api_key}"}, json=body)
            return {"channel": "email", "sent": r.status_code in (200, 201), "status": r.status_code,
                    "id": (r.json() or {}).get("id") if r.content else None}
    except Exception as e:
        return {"channel": "email", "sent": False, "reason": repr(e)[:160]}

"""Invia a te su Telegram slide + caption + avvisi per la revisione (nessuna pubblicazione automatica)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from newsbot.config import Settings

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/{method}"


def _call(settings: Settings, method: str, **kwargs) -> dict:
    r = httpx.post(API.format(token=settings.telegram_token, method=method), timeout=60, **kwargs)
    r.raise_for_status()
    return r.json()


def send_for_review(settings: Settings, out_dir: Path, title: str, warnings: list[str] | None = None) -> bool:
    if not (settings.telegram_token and settings.telegram_chat_id):
        log.warning("Telegram non configurato (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        return False
    chat = settings.telegram_chat_id
    pngs = sorted(out_dir.glob("slide_*.png"), key=lambda p: int(p.stem.split("_")[1]))
    head = f"📝 Bozza: {title}"
    if warnings:
        head += "\n\n⚠️ Da controllare:\n" + "\n".join(f"• {w}" for w in warnings)
    _call(settings, "sendMessage", data={"chat_id": chat, "text": head[:4000]})
    for i in range(0, len(pngs), 10):      # sendMediaGroup: max 10 immagini
        batch = pngs[i:i + 10]
        media = [{"type": "photo", "media": f"attach://p{j}"} for j in range(len(batch))]
        files = {f"p{j}": (p.name, p.read_bytes(), "image/png") for j, p in enumerate(batch)}
        _call(settings, "sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)}, files=files)
    caption = (out_dir / "caption.txt").read_text(encoding="utf-8")
    _call(settings, "sendMessage", data={"chat_id": chat, "text": "Caption:\n\n" + caption[:3900]})
    return True

"""Scraper social tramite Apify (servizio di terzi, a pagamento).

ATTENZIONE: lo scraping di Instagram/X è in zona grigia rispetto ai ToS delle piattaforme.
Valuta rischi e costi. Alternativa senza scraper: usa l'import manuale (data/manual/*.csv).

L'attore e lo schema di input vanno verificati sulla documentazione Apify attuale.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from newsbot.models import Source
from newsbot.utils import utcnow

log = logging.getLogger(__name__)

INSTAGRAM_ACTOR = "apify~instagram-scraper"   # da verificare


def fetch_instagram(src: Source, token: str, limit: int = 10) -> list[dict]:
    if not token:
        raise RuntimeError("APIFY_TOKEN mancante")
    if not src.handle:
        raise ValueError(f"{src.id}: manca 'handle'")
    url = f"https://api.apify.com/v2/acts/{INSTAGRAM_ACTOR}/run-sync-get-dataset-items"
    payload = {
        "directUrls": [f"https://www.instagram.com/{src.handle}/"],
        "resultsType": "posts",
        "resultsLimit": limit,
    }
    r = httpx.post(url, params={"token": token}, json=payload, timeout=180)
    r.raise_for_status()
    items = []
    for p in r.json():
        caption = (p.get("caption") or "").strip()
        link = p.get("url")
        if not caption or not link:
            continue
        ts = p.get("timestamp")
        try:
            published = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else utcnow()
        except ValueError:
            published = utcnow()
        items.append({
            "url": link,
            "title": caption.split("\n", 1)[0][:140],
            "summary": caption[:600],
            "text": caption,
            "published_at": published.astimezone(timezone.utc),
            "engagement": float((p.get("likesCount") or 0) + 3 * (p.get("commentsCount") or 0)),
        })
    return items


# TODO X/Twitter: l'API ufficiale è a pagamento e cambia spesso; per ora usa data/manual/*.csv

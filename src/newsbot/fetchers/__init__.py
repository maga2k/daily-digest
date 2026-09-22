"""Raccolta delle fonti. Ogni fetcher restituisce una lista di dict con chiavi:
url, title, summary, text, published_at (datetime aware), engagement."""
from __future__ import annotations

import logging

import httpx

from newsbot.config import Settings
from newsbot.db import DB
from newsbot.fetchers.apify import fetch_instagram
from newsbot.fetchers.rss import fetch_rss
from newsbot.fetchers.web import fetch_fulltext, fetch_web_index
from newsbot.models import Profile, Source

log = logging.getLogger(__name__)


def make_client(settings: Settings) -> httpx.Client:
    """Client HTTP. Se c'è `truststore` usa i certificati di sistema (utile su macOS/aziende
    dove alcuni siti hanno catene di certificati incomplete); non disattiva MAI la verifica SSL."""
    verify: object = True
    try:
        import ssl

        import truststore
        verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    return httpx.Client(
        headers={"User-Agent": settings.user_agent, "Accept-Language": "it,en;q=0.8"},
        timeout=20.0, verify=verify,
    )


def fetch_source(src: Source, settings: Settings, client: httpx.Client) -> list[dict]:
    if src.type == "rss":
        return fetch_rss(src, client)
    if src.type == "web":
        return fetch_web_index(src, client)
    if src.type == "apify_instagram":
        return fetch_instagram(src, settings.apify_token or "")
    raise ValueError(f"tipo di fonte sconosciuto: {src.type}")


def fetch_profile(profile: Profile, settings: Settings, db: DB) -> dict[str, int]:
    """Scarica tutte le fonti del profilo. Una fonte che fallisce non blocca le altre."""
    stats = {"new": 0, "seen": 0, "errors": 0}
    with make_client(settings) as client:
        for src in profile.sources:
            if not src.enabled:
                continue
            try:
                items = fetch_source(src, settings, client)
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                log.warning("[%s] %s: errore (%s)", profile.id, src.id, exc)
                continue
            new = 0
            for it in items:
                text = it["text"]
                if src.fulltext and not text:
                    text = fetch_fulltext(it["url"], client)
                ok = db.add_article(
                    url=it["url"], profile=profile.id, source_id=src.id, source_name=src.name,
                    title=it["title"], summary=it["summary"], text=text,
                    published_at=it["published_at"], kind=src.kind, party=src.party,
                    lang=src.lang, weight=src.weight, engagement=it.get("engagement", 0.0),
                )
                new += int(ok)
            stats["new"] += new
            stats["seen"] += len(items)
            log.info("[%s] %s: %d elementi (%d nuovi)", profile.id, src.id, len(items), new)
    return stats

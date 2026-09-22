"""Estrazione di testo da pagine web (trafilatura) e scraping leggero di pagine-indice."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from newsbot.models import Source
from newsbot.utils import truncate, utcnow

log = logging.getLogger(__name__)


def fetch_fulltext(url: str, client: httpx.Client) -> str:
    """Scarica una pagina ed estrae il testo principale ('' se fallisce)."""
    import trafilatura   # import pigro: serve solo per il testo completo

    try:
        r = client.get(url, follow_redirects=True)
        r.raise_for_status()
        return trafilatura.extract(r.text, include_comments=False, favor_precision=True) or ""
    except Exception as exc:  # noqa: BLE001
        log.debug("fulltext fallito per %s: %s", url, exc)
        return ""


def fetch_web_index(src: Source, client: httpx.Client) -> list[dict]:
    """Per siti senza RSS: apre una pagina-indice, prende i link che combaciano con
    `link_pattern` (regex) e ne estrae titolo/data/testo. Controlla robots.txt e ToS!"""
    import trafilatura

    r = client.get(src.url, follow_redirects=True)
    r.raise_for_status()
    pattern = re.compile(src.link_pattern or r"/(notizie|news|comunicati)/")
    links: list[str] = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', r.text):
        full = urljoin(src.url, href)
        if pattern.search(full) and full not in links and full != src.url:
            links.append(full)
    items = []
    for link in links[: src.max_items]:
        page = client.get(link, follow_redirects=True)
        if page.status_code != 200:
            continue
        meta = trafilatura.extract_metadata(page.text)
        text = trafilatura.extract(page.text, favor_precision=True) or ""
        title = (getattr(meta, "title", None) or "").strip()
        if not title:
            continue
        date_s = getattr(meta, "date", None)
        try:
            published = datetime.fromisoformat(date_s).replace(tzinfo=timezone.utc) if date_s else utcnow()
        except ValueError:
            published = utcnow()
        items.append({
            "url": link, "title": title, "summary": truncate(text, 500), "text": text,
            "published_at": published, "engagement": 0.0,
        })
    return items

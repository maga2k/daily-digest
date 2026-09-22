"""Fetcher RSS/Atom."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

from newsbot.models import Source
from newsbot.utils import strip_html, truncate, utcnow

log = logging.getLogger(__name__)

_POINTS_RE = re.compile(r"Points:\s*(\d+)")   # feed di Hacker News


def _entry_dt(e) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = e.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return utcnow()


def fetch_rss(src: Source, client: httpx.Client) -> list[dict]:
    resp = client.get(src.url, follow_redirects=True, timeout=src.timeout or client.timeout)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    items: list[dict] = []
    for e in feed.entries[: src.max_items]:
        url = e.get("link")
        title = strip_html(e.get("title", ""))
        if not url or not title:
            continue
        summary = e.get("summary", "")
        if not summary and e.get("content"):
            summary = e["content"][0].get("value", "")
        m = _POINTS_RE.search(summary)
        engagement = float(m.group(1)) if m else 0.0
        items.append({
            "url": url,
            "title": title,
            "summary": truncate(strip_html(summary), 600),
            "text": "",
            "published_at": _entry_dt(e),
            "engagement": engagement,
        })
    if not items:
        ctype = resp.headers.get("content-type", "?")
        snippet = strip_html(resp.text[:200])[:80]
        raise ValueError(f"nessuna voce nel feed (HTTP {resp.status_code}, {ctype}, inizio: '{snippet}'). "
                         "Probabile URL sbagliato o blocco anti-bot: prova `newsbot discover <sito>`")
    return items

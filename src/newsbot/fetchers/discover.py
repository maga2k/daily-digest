"""Trova i feed RSS/Atom di un sito: legge i <link rel="alternate"> della home e prova percorsi comuni."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

COMMON_PATHS = ["/feed", "/feed/", "/rss", "/rss/", "/rss.xml", "/feed.xml", "/atom.xml",
                "/index.xml", "/?feed=rss2", "/rss/index.xml", "/feeds/all.rss"]

_LINK_RE = re.compile(r"<link\b[^>]*>", re.I)


def find_feed_links(html: str, base_url: str) -> list[str]:
    """URL dei feed dichiarati nell'HTML (<link type="application/rss+xml" href=...>)."""
    out: list[str] = []
    for tag in _LINK_RE.findall(html):
        if not re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
            continue
        m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if m:
            u = urljoin(base_url, m.group(1))
            if u not in out:
                out.append(u)
    return out


def _try(url: str, client: httpx.Client) -> int:
    try:
        r = client.get(url, follow_redirects=True)
        if r.status_code != 200:
            return 0
        return len(feedparser.parse(r.content).entries)
    except Exception:  # noqa: BLE001
        return 0


def discover_feeds(site_url: str, client: httpx.Client) -> list[dict]:
    parsed = urlparse(site_url if "://" in site_url else "https://" + site_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    candidates: list[tuple[str, str]] = []
    try:
        r = client.get(site_url if "://" in site_url else origin, follow_redirects=True)
        candidates += [(u, "dichiarato nella pagina") for u in find_feed_links(r.text, str(r.url))]
    except Exception:  # noqa: BLE001
        pass
    candidates += [(origin + path, "percorso comune") for path in COMMON_PATHS]
    seen, found = set(), []
    for url, how in candidates:
        if url in seen:
            continue
        seen.add(url)
        n = _try(url, client)
        if n:
            found.append({"url": url, "items": n, "how": how})
    return found

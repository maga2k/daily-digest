"""Funzioni di utilità piccole e senza dipendenze pesanti."""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timezone

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def from_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", s))).strip()


def truncate(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.- ") + "…"


def first_sentence(s: str, max_len: int = 180) -> str:
    s = (s or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    return truncate(m.group(1) if m else s, max_len)


def normalize(s: str) -> str:
    """minuscolo, senza accenti né punteggiatura: per confronti tra stringhe."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return _WS_RE.sub(" ", s).strip()


def slugify(s: str) -> str:
    return normalize(s).replace(" ", "-")[:60] or "post"


def domain_of(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else (url or "")

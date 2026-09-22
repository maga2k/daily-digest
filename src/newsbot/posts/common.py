from __future__ import annotations

from newsbot.models import Profile
from newsbot.utils import domain_of, truncate

CAPTION_MAX = 2200   # limite Instagram
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
         "settembre", "ottobre", "novembre", "dicembre"]


def it_date(day: str) -> str:
    """'2026-09-19' -> '19 settembre 2026'"""
    try:
        y, m, d = (int(x) for x in day.split("-"))
        return f"{d} {_MESI[m - 1]} {y}"
    except (ValueError, IndexError):
        return day


def build_caption(profile: Profile, intro: str, bullets: list[str], extra: str = "") -> str:
    parts = [intro.strip()]
    if bullets:
        parts.append("\n".join(f"• {truncate(b, 110)}" for b in bullets))
    if extra:
        parts.append(extra.strip())
    parts.append("Fonti e link nell'ultima slide.")
    if profile.disclosure:
        parts.append(profile.disclosure)
    if profile.hashtags:
        parts.append(" ".join(profile.hashtags))
    return truncate("\n\n".join(p for p in parts if p), CAPTION_MAX)


def source_entry(name: str, url: str, title: str = "") -> dict[str, str]:
    return {"name": name, "url": url, "title": title, "domain": domain_of(url)}


def dedupe_sources(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    seen, out = set(), []
    for e in entries:
        if e["url"] not in seen:
            seen.add(e["url"])
            out.append(e)
    return out

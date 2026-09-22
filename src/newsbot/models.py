"""Modelli dati (dataclass semplici)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from newsbot.utils import from_iso


@dataclass
class Source:
    id: str
    name: str
    type: str = "rss"          # rss | web | apify_instagram
    kind: str = "news"         # news | party | factcheck | social
    url: str = ""
    lang: str = "it"
    weight: float = 1.0
    party: str | None = None
    handle: str | None = None
    fulltext: bool = False
    enabled: bool = True              # false = salta la fonte (es. feed rotto)
    timeout: float | None = None      # secondi, se il sito è lento
    max_items: int = 30
    link_pattern: str | None = None   # per type=web


@dataclass
class Profile:
    id: str
    label: str
    lookback_hours: int = 36
    top_n: int = 3
    min_sources: int = 1
    cluster_kinds: list[str] = field(default_factory=lambda: ["news"])
    post_types: list[str] = field(default_factory=lambda: ["digest"])
    ranking: dict[str, float] = field(default_factory=dict)
    hashtags: list[str] = field(default_factory=list)
    handle: str = ""
    disclosure: str = ""
    style: dict[str, str] = field(default_factory=dict)
    system_prompt: str = ""
    sources: list[Source] = field(default_factory=list)
    versus_parties: list[str] = field(default_factory=list)
    parties: dict[str, dict[str, Any]] = field(default_factory=dict)
    factcheck_lookback_days: int = 30
    clustering_threshold: float | None = None
    exclude_title_patterns: list[str] = field(default_factory=list)   # regex: titoli da scartare


@dataclass
class Article:
    id: int
    url: str
    profile: str
    source_id: str
    source_name: str
    kind: str
    party: str | None
    title: str
    summary: str
    text: str
    lang: str
    weight: float
    published_at: datetime
    sentiment: float | None = None
    engagement: float = 0.0

    @classmethod
    def from_row(cls, r) -> "Article":
        return cls(
            id=r["id"], url=r["url"], profile=r["profile"], source_id=r["source_id"],
            source_name=r["source_name"], kind=r["kind"], party=r["party"], title=r["title"],
            summary=r["summary"] or "", text=r["text"] or "", lang=r["lang"] or "it",
            weight=r["weight"] or 1.0, published_at=from_iso(r["published_at"]),
            sentiment=r["sentiment"], engagement=r["engagement"] or 0.0,
        )


@dataclass
class Cluster:
    profile: str
    title: str
    articles: list[Article]
    score: float = 0.0
    id: int | None = None
    framing_spread: float | None = None   # differenza di tono tra testate (se c'è il sentiment)

    @property
    def n_sources(self) -> int:
        return len({a.source_id for a in self.articles})


@dataclass
class Claim:
    id: int
    article_id: int
    party: str
    theme: str
    claim: str
    quote: str | None
    url: str
    source_name: str
    published_at: datetime


@dataclass
class PostPlan:
    """Tutto ciò che serve per renderizzare e rivedere un post."""
    profile_id: str
    post_type: str
    day: str
    slides: list[dict[str, Any]]
    caption: str
    sources: list[dict[str, str]]
    warnings: list[str] = field(default_factory=list)

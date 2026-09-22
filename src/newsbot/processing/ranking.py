"""Ranking dei cluster: quante testate, quanto fresco, quanto autorevole, quanto engagement."""
from __future__ import annotations

import math
from datetime import datetime

from newsbot.models import Article, Cluster

DEFAULT_RANKING = {
    "w_sources": 1.0, "w_recency": 0.8, "w_authority": 0.5, "w_engagement": 0.0,
    "half_life_hours": 12.0,
}


def representative_title(articles: list[Article]) -> str:
    """Titolo dell'articolo della fonte con peso più alto (a parità, il più vecchio)."""
    best = sorted(articles, key=lambda a: (-a.weight, a.published_at))[0]
    return best.title


def framing_spread(articles: list[Article]) -> float | None:
    vals = [a.sentiment for a in articles if a.sentiment is not None]
    if len(vals) < 2:
        return None
    return max(vals) - min(vals)


def score_cluster(articles: list[Article], now: datetime, cfg: dict | None = None) -> float:
    c = {**DEFAULT_RANKING, **(cfg or {})}
    by_source: dict[str, float] = {}
    for a in articles:
        by_source[a.source_id] = max(by_source.get(a.source_id, 0.0), a.weight)
    n_src = len(by_source)
    authority = sum(by_source.values()) / max(n_src, 1)
    newest = max(a.published_at for a in articles)
    age_h = max((now - newest).total_seconds() / 3600, 0.0)
    recency = 0.5 ** (age_h / max(c["half_life_hours"], 0.1))
    engagement = math.log1p(sum(a.engagement for a in articles))
    return (c["w_sources"] * math.log1p(n_src)
            + c["w_recency"] * recency
            + c["w_authority"] * authority
            + c["w_engagement"] * engagement)


def build_clusters(profile_id: str, groups: list[list[Article]], now: datetime,
                   cfg: dict | None = None, min_sources: int = 1) -> list[Cluster]:
    clusters = []
    for g in groups:
        c = Cluster(profile=profile_id, title=representative_title(g), articles=g)
        if c.n_sources < min_sources:
            continue
        c.score = score_cluster(g, now, cfg)
        c.framing_spread = framing_spread(g)
        clusters.append(c)
    return sorted(clusters, key=lambda c: c.score, reverse=True)

"""Raggruppa gli articoli che parlano dello stesso evento."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from newsbot.models import Article
from newsbot.processing.embeddings import Embedder
from newsbot.utils import truncate


def _clean_summary(s: str) -> str:
    # il feed di Hacker News mette in ogni sommario la stessa frase standard: va ignorata
    return "" if ("Comments URL" in s or "Article URL" in s) else s


def article_text(a: Article) -> str:
    return f"{a.title}. {truncate(_clean_summary(a.summary), 300)}"


def cluster_articles(articles: list[Article], embedder: Embedder,
                     threshold: float | None = None) -> list[list[Article]]:
    """Clustering agglomerativo con distanza coseno. Restituisce liste di articoli."""
    if not articles:
        return []
    if len(articles) == 1:
        return [articles]
    X = embedder.encode([article_text(a) for a in articles])
    thr = threshold if threshold is not None else embedder.cluster_threshold
    model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                    distance_threshold=thr)
    labels = model.fit_predict(np.asarray(X))
    groups: dict[int, list[Article]] = defaultdict(list)
    for a, lab in zip(articles, labels):
        groups[int(lab)].append(a)
    return list(groups.values())

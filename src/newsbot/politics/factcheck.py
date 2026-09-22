"""Collega un tema/claim ai fact-check GIÀ pubblicati da terzi (Pagella Politica, Facta, ecc.).
Il bot non emette verdetti: riporta titolo e link del fact-checker, attribuiti."""
from __future__ import annotations

from newsbot.models import Article
from newsbot.processing.embeddings import Embedder
from newsbot.utils import truncate


def find_factchecks(query: str, candidates: list[Article], embedder: Embedder, k: int = 2) -> list[dict]:
    if not candidates or not query.strip():
        return []
    docs = [f"{a.title}. {truncate(a.summary, 300)}" for a in candidates]
    sims = embedder.similarity([query], docs)[0]
    ranked = sorted(zip(sims, candidates), key=lambda x: -x[0])
    out = []
    for s, a in ranked[:k]:
        if s >= embedder.factcheck_threshold:
            out.append({"source": a.source_name, "title": truncate(a.title, 140), "url": a.url,
                        "similarity": round(float(s), 3)})
    return out

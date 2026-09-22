"""Orchestrazione: fetch -> process (cluster+ranking+claims) -> generate (piano post + render) -> review."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from newsbot.config import Settings, load_profiles, load_themes
from newsbot.db import DB
from newsbot.delivery.telegram import send_for_review
from newsbot.fetchers import fetch_profile
from newsbot.fetchers.manual import import_manual
from newsbot.llm.client import LLM
from newsbot.models import PostPlan, Profile
from newsbot.politics.claims import extract_claims
from newsbot.politics.programs import ingest_programs
from newsbot.posts.digest import plan_digest
from newsbot.posts.versus import plan_versus
from newsbot.processing.clustering import article_text, cluster_articles
from newsbot.processing.embeddings import Embedder
from newsbot.processing.ranking import build_clusters, framing_spread
from newsbot.processing.sentiment import SentimentScorer
from newsbot.render.renderer import render_post
from newsbot.utils import utcnow

log = logging.getLogger(__name__)


@dataclass
class Context:
    settings: Settings
    db: DB
    llm: LLM
    embedder: Embedder
    sentiment: SentimentScorer
    profiles: dict[str, Profile]
    themes: dict


def build_context(settings: Settings) -> Context:
    db = DB(settings.db_path)
    db.init()
    backend = settings.resolved_embedding_backend()
    log.info("embeddings: %s | LLM: %s", backend, "attivo" if settings.anthropic_api_key else "non configurato")
    return Context(
        settings=settings, db=db, llm=LLM(settings),
        embedder=Embedder(backend, settings.embedding_model),
        sentiment=SentimentScorer(settings.sentiment_backend),
        profiles=load_profiles(settings), themes=load_themes(settings),
    )


def select_profiles(ctx: Context, ids: list[str] | None) -> list[Profile]:
    if not ids:
        return list(ctx.profiles.values())
    missing = [i for i in ids if i not in ctx.profiles]
    if missing:
        raise SystemExit(f"Profili sconosciuti: {missing}. Disponibili: {list(ctx.profiles)}")
    return [ctx.profiles[i] for i in ids]


def day_of(now: datetime) -> str:
    return now.astimezone().date().isoformat()


# ---------------------------------------------------------------------- fetch
def run_fetch(ctx: Context, profile_ids: list[str] | None = None) -> None:
    for p in select_profiles(ctx, profile_ids):
        stats = fetch_profile(p, ctx.settings, ctx.db)
        print(f"[{p.id}] {stats['seen']} letti, {stats['new']} nuovi, {stats['errors']} fonti in errore")
    import_manual(ctx.db, ctx.settings.data_dir / "manual", set(ctx.profiles))


def run_programs(ctx: Context) -> None:
    folder = ctx.settings.data_dir / "programs"
    folder.mkdir(parents=True, exist_ok=True)
    n = ingest_programs(ctx.db, folder)
    print(f"programmi: {n} chunk indicizzati da {folder}")


# ---------------------------------------------------------------------- process
def run_process(ctx: Context, profile_ids: list[str] | None = None, now: datetime | None = None) -> None:
    now = now or utcnow()
    day = day_of(now)
    for p in select_profiles(ctx, profile_ids):
        since = now - timedelta(hours=p.lookback_hours)
        arts = ctx.db.get_articles(p.id, since, kinds=p.cluster_kinds)
        if p.exclude_title_patterns:
            rx = re.compile("|".join(p.exclude_title_patterns), re.I)
            arts = [a for a in arts if not rx.search(a.title)]
        groups = cluster_articles(arts, ctx.embedder, p.clustering_threshold)
        clusters = build_clusters(p.id, groups, now, p.ranking, p.min_sources)[:30]

        if ctx.sentiment.enabled:
            top = clusters[: max(p.top_n * 2, 6)]
            flat = [a for c in top for a in c.articles if a.sentiment is None]
            for a, s in zip(flat, ctx.sentiment.score([article_text(a) for a in flat])):
                a.sentiment = s
                ctx.db.set_sentiment(a.id, s)
            for c in top:
                c.framing_spread = framing_spread(c.articles)

        ctx.db.save_clusters(p.id, day, clusters)
        print(f"[{p.id}] {len(arts)} articoli -> {len(clusters)} cluster (top score: "
              f"{clusters[0].score:.2f})" if clusters else f"[{p.id}] nessun cluster")

        if p.parties:
            extract_claims(ctx.db, ctx.llm, p, ctx.themes, now)


# ---------------------------------------------------------------------- generate
def output_path(ctx: Context, day: str, profile_id: str, post_type: str) -> Path:
    return ctx.settings.output_dir / day / profile_id / post_type


def run_generate(ctx: Context, profile_ids: list[str] | None = None, types: list[str] | None = None,
                 png: bool = True, now: datetime | None = None) -> list[Path]:
    now = now or utcnow()
    day = day_of(now)
    outputs: list[Path] = []
    for p in select_profiles(ctx, profile_ids):
        for ptype in (types or p.post_types):
            plan: PostPlan | None = None
            if ptype == "digest":
                plan = plan_digest(p, ctx.db.load_clusters(p.id, day), ctx.llm, day)
            elif ptype == "versus":
                plan = plan_versus(ctx.db, p, ctx.llm, ctx.embedder, ctx.themes, day, now)
            else:
                log.warning("tipo di post sconosciuto: %s", ptype)
            if plan is None:
                print(f"[{p.id}/{ptype}] niente da generare (dati insufficienti)")
                continue
            out = output_path(ctx, day, p.id, ptype)
            render_post(plan, p, out, png=png)
            ctx.db.add_post(p.id, ptype, day, str(out))
            outputs.append(out)
            print(f"[{p.id}/{ptype}] -> {out}" + (f"  ⚠ {len(plan.warnings)} avvisi" if plan.warnings else ""))
    return outputs


# ---------------------------------------------------------------------- review
def run_review(ctx: Context, outputs: list[Path]) -> None:
    for out in outputs:
        warnings_file = out / "DA_CONTROLLARE.txt"
        warnings = warnings_file.read_text(encoding="utf-8").splitlines() if warnings_file.exists() else []
        ok = send_for_review(ctx.settings, out, f"{out.parent.name}/{out.name}", warnings)
        print(f"{'inviato' if ok else 'NON inviato'}: {out}")

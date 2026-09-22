"""Estrazione dei claim dei partiti per tema (lista chiusa di temi).

L'LLM NON giudica la verità: parafrasa cosa è stato dichiarato. Le citazioni letterali
sono validate (devono comparire nel testo originale), così non si "inventano" virgolette.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from newsbot.db import DB
from newsbot.llm import prompts
from newsbot.llm.client import LLM
from newsbot.models import Article, Profile
from newsbot.utils import first_sentence, normalize, truncate, utcnow

log = logging.getLogger(__name__)


def heuristic_theme(text: str, themes: dict) -> str | None:
    """Tema per conteggio di parole chiave (fallback senza LLM)."""
    t = " " + normalize(text) + " "
    best, best_n = None, 0
    for key, cfg in themes.items():
        n = sum(t.count(" " + normalize(k) + " ") for k in cfg.get("keywords", []))
        if n > best_n:
            best, best_n = key, n
    return best


def _valid_quote(quote: str | None, source_text: str) -> str | None:
    if not quote:
        return None
    q = quote.strip().strip('"“”«»')
    if len(q.split()) > 15 or normalize(q) not in normalize(source_text):
        return None
    return q


def extract_claims_for_article(a: Article, llm: LLM, themes: dict, profile: Profile) -> list[dict]:
    body = a.text or a.summary or a.title
    if llm.enabled:
        theme_labels = {k: v["label"] for k, v in themes.items()}
        data = llm.json(prompts.system_for(profile.system_prompt),
                        prompts.claims_user_prompt(a.party or "?", a.source_name, body, theme_labels))
        if isinstance(data, dict):
            out = []
            for c in data.get("claims", [])[:3]:
                if c.get("theme") in themes and c.get("claim"):
                    out.append({"theme": c["theme"], "claim": truncate(c["claim"], 220),
                                "quote": _valid_quote(c.get("quote"), body)})
            return out
    # fallback euristico
    theme = heuristic_theme(f"{a.title} {a.summary} {a.text[:1500]}", themes)
    if not theme:
        return []
    return [{"theme": theme, "claim": first_sentence(a.summary or a.title, 200), "quote": None}]


def extract_claims(db: DB, llm: LLM, profile: Profile, themes: dict, now=None) -> int:
    """Estrae i claim dagli articoli 'party'/'social' non ancora elaborati."""
    now = now or utcnow()
    since = now - timedelta(hours=max(profile.lookback_hours, 72))
    total = 0
    for a in db.pending_claim_articles(profile.id, since, ["party", "social"]):
        if not a.party or (profile.parties and a.party not in profile.parties):
            db.mark_claims_done(a.id)
            continue
        for c in extract_claims_for_article(a, llm, themes, profile):
            db.add_claim(article_id=a.id, profile=profile.id, party=a.party, theme=c["theme"],
                         claim=c["claim"], quote=c["quote"])
            total += 1
        db.mark_claims_done(a.id)
    log.info("[%s] claim estratti: %d", profile.id, total)
    return total

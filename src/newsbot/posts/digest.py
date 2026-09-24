"""Post 'digest': le top N storie del profilo, una slide ciascuna."""
from __future__ import annotations

import logging

from newsbot.llm import prompts
from newsbot.llm.client import LLM
from newsbot.models import Cluster, PostPlan, Profile
from newsbot.posts.common import build_caption, dedupe_sources, it_date, source_entry
from newsbot.utils import first_sentence, truncate

log = logging.getLogger(__name__)


def _payload(clusters: list[Cluster]) -> list[dict]:
    out = []
    for c in clusters:
        arts = sorted(c.articles, key=lambda a: -a.weight)[:6]
        out.append({
            "cluster_id": c.id,
            "n_testate": c.n_sources,
            "differenza_di_tono_tra_testate": None if c.framing_spread is None else round(c.framing_spread, 2),
            "articoli": [{
                "fonte": a.source_name, "titolo": a.title, "sommario": truncate(a.summary, 300),
                "tono": None if a.sentiment is None else round(a.sentiment, 2),
            } for a in arts],
        })
    return out


def _tone_label(c: Cluster) -> str | None:
    vals = [a.sentiment for a in c.articles if a.sentiment is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    return "tono prevalente: negativo" if m < -0.25 else "tono prevalente: positivo" if m > 0.25 else "tono prevalente: neutro"


def _fallback_story(c: Cluster) -> dict:
    bullets, seen = [], set()
    for a in sorted(c.articles, key=lambda a: -a.weight):
        s = first_sentence(a.summary, 110) if a.summary else ""
        if s and s not in seen:
            bullets.append(f"{a.source_name}: {s}")
            seen.add(s)
        if len(bullets) == 2:
            break
    return {"headline": truncate(c.title, 90), "bullets": bullets or [truncate(c.title, 110)],
            "framing": None, "note": None}


def plan_digest(profile: Profile, clusters: list[Cluster], llm: LLM, day: str) -> PostPlan | None:
    top = clusters[: profile.top_n]
    if not top:
        return None
    warnings: list[str] = []
    llm_out = None
    if llm.enabled:
        llm_out = llm.json(prompts.system_for(profile.system_prompt),
                           prompts.digest_user_prompt(profile.label, _payload(top), profile.hashtags),
                           max_tokens=4500)
        if not isinstance(llm_out, dict) or "stories" not in llm_out:
            warnings.append("Risposta LLM non valida: uso il fallback euristico.")
            llm_out = None
    else:
        warnings.append("LLM non configurato: testi generati con euristica. Rivedi con attenzione.")

    stories = (llm_out or {}).get("stories", []) if llm_out else []

    def story_for(i: int, c: Cluster) -> dict | None:
        for st in stories:
            if st.get("cluster_id") == c.id:
                return st
        return stories[i - 1] if i - 1 < len(stories) else None

    slides: list[dict] = []
    headlines: list[str] = []
    all_sources: list[dict] = []
    for i, c in enumerate(top, start=1):
        s = story_for(i, c) or _fallback_story(c)
        headline = truncate(s.get("headline") or c.title, 90)
        headlines.append(headline)
        src_entries = [source_entry(a.source_name, a.url, a.title) for a in c.articles]
        all_sources.extend(src_entries)
        names = sorted({a.source_name for a in c.articles})
        slides.append({
            "type": "story", "n": i, "headline": headline,
            "bullets": [truncate(b, 120) for b in (s.get("bullets") or [])[:3]],
            "framing": truncate(s["framing"], 160) if s.get("framing") else None,
            "note": truncate(s["note"], 100) if s.get("note") else None,
            "tone": _tone_label(c),
            "source_names": names,
        })
        if c.n_sources < 2 and profile.min_sources > 1:
            warnings.append(f"Storia {i} coperta da una sola testata.")
        if c.n_sources == 1:
            warnings.append(f"Storia {i} ('{truncate(c.title, 50)}'): una sola fonte, verifica.")

    hook = truncate((llm_out or {}).get("hook") or f"{profile.label}: le {len(top)} notizie di oggi", 100)
    slides.insert(0, {"type": "cover", "title": hook, "subtitle": profile.label, "day": it_date(day)})
    sources = dedupe_sources(all_sources)
    # slide fonti: per ogni storia, nomi testate + domini
    slides.append({"type": "sources",
                   "groups": [{"n": s["n"], "headline": s["headline"], "names": s["source_names"]}
                              for s in slides if s["type"] == "story"],
                   "note": "I link completi sono nel file fonti.json e nei commenti/bio."})

    llm_caption = (llm_out or {}).get("caption")
    if llm_out and not llm_caption:
        warnings.append("Il modello non ha restituito la caption: uso il fallback con i titoli.")
    intro = llm_caption or f"{profile.label} — le notizie principali di oggi:"
    caption = build_caption(profile, intro, [] if llm_caption else headlines)
    return PostPlan(profile_id=profile.id, post_type="digest", day=day, slides=slides,
                    caption=caption, sources=sources, warnings=warnings)

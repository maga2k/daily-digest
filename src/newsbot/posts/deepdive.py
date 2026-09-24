"""Approfondimento lungo di un tema, pensato per Telegram (non per le slide Instagram).

Per il profilo politica, se c'è un tema con dichiarazioni di entrambi i partiti nelle ultime ore
(stesso criterio del post "versus"), lo usa come argomento; altrimenti usa il cluster più rilevante
della giornata. Con l'LLM scrive un'analisi in più sezioni; senza, assembla comunque un messaggio
completo dai dati grezzi (claim, fact-check, programma, articoli) — più povero, ma mai vuoto.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from newsbot.db import DB
from newsbot.llm import prompts
from newsbot.llm.client import LLM
from newsbot.models import Profile
from newsbot.politics.factcheck import find_factchecks
from newsbot.politics.programs import program_excerpt
from newsbot.processing.embeddings import Embedder
from newsbot.utils import truncate, utcnow


@dataclass
class Deepdive:
    profile_id: str
    day: str
    title: str
    html: str                       # pronto per Telegram (parse_mode=HTML)
    sources: list[dict[str, str]]
    warnings: list[str] = field(default_factory=list)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _political_topic(db: DB, profile: Profile, themes: dict, now: datetime) -> dict | None:
    """Stesso criterio del post 'versus': il tema con più dichiarazioni di entrambi i partiti."""
    if len(profile.versus_parties) < 2:
        return None
    a_name, b_name = profile.versus_parties[0], profile.versus_parties[1]
    since = now - timedelta(hours=max(profile.lookback_hours, 72))
    claims = db.get_claims(profile.id, since)
    by_theme: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for c in claims:
        by_theme[c.theme][c.party].append(c)
    candidates = [t for t, v in by_theme.items() if a_name in v and b_name in v]
    if not candidates:
        return None
    theme = max(candidates, key=lambda t: sum(len(v) for v in by_theme[t].values()))
    return {"theme": theme, "label": themes.get(theme, {}).get("label", theme),
            "per_party": by_theme[theme], "a": a_name, "b": b_name}


def _fallback_html(materials: dict) -> str:
    parts = []
    if materials.get("political"):
        m = materials["political"]
        for key in ("a", "b"):
            parts.append(f"<b>{_esc(m[f'{key}_name'])}</b>")
            for c in m[f"{key}_claims"][:3]:
                parts.append(f"• {_esc(c['claim'])} <i>({_esc(c['source'])})</i>")
            parts.append("")
        if m.get("factchecks"):
            parts.append("<b>Fact-check di terzi</b>")
            for fc in m["factchecks"]:
                parts.append(f"• secondo {_esc(fc['source'])}: {_esc(fc['title'])}")
        else:
            parts.append("<i>Nessun fact-check di terzi trovato su questo tema: non verificato.</i>")
        parts.append("")
    else:
        for a in materials.get("articles", [])[:6]:
            parts.append(f"• <b>{_esc(a['source'])}</b>: {_esc(a['title'])}")
        parts.append("")
    parts.append("<i>Sintesi assemblata senza IA (nessun modello configurato o risposta non valida): "
                 "testi grezzi, da riscrivere prima di condividerli.</i>")
    return "\n".join(parts)


def build_deepdive(db: DB, profile: Profile, llm: LLM, embedder: Embedder, themes: dict,
                   day: str, now: datetime | None = None) -> Deepdive | None:
    now = now or utcnow()
    warnings: list[str] = []
    political = _political_topic(db, profile, themes, now) if profile.parties else None

    sources: list[dict[str, str]] = []
    if political:
        a_name, b_name = political["a"], political["b"]
        per_party = political["per_party"]
        a_info, b_info = profile.parties.get(a_name, {}), profile.parties.get(b_name, {})
        title = f"{political['label']}: {a_name} vs {b_name}"

        def claim_payload(party: str) -> list[dict]:
            recent = sorted(per_party[party], key=lambda c: c.published_at, reverse=True)[:4]
            return [{"claim": c.claim, "source": c.source_name,
                     "date": c.published_at.date().isoformat(), "quote": c.quote} for c in recent]

        a_claims, b_claims = claim_payload(a_name), claim_payload(b_name)
        query = " ".join([political["label"]] + [c["claim"] for c in a_claims + b_claims])
        fc_since = now - timedelta(days=profile.factcheck_lookback_days)
        fc_candidates = db.get_articles(profile.id, fc_since, kinds=["factcheck"])
        factchecks = find_factchecks(query, fc_candidates, embedder, k=3)
        prog_a = program_excerpt(db, embedder, a_name, query)
        prog_b = program_excerpt(db, embedder, b_name, query)

        materials = {"political": {
            "theme": political["label"], "a_name": a_info.get("name", a_name), "b_name": b_info.get("name", b_name),
            "a_claims": a_claims, "b_claims": b_claims, "factchecks": factchecks,
            "program_a": prog_a["text"] if prog_a else None, "program_b": prog_b["text"] if prog_b else None,
        }}
        sources = [{"name": c.source_name, "url": c.url} for c in per_party[a_name][:2] + per_party[b_name][:2]]
        sources += [{"name": f["source"], "url": f["url"]} for f in factchecks]
        if not factchecks:
            warnings.append("Nessun fact-check collegato: il messaggio lo dichiara come 'non verificato'.")
    else:
        clusters = db.load_clusters(profile.id, day)
        if not clusters:
            return None
        top = clusters[0]
        title = truncate(top.title, 100)
        arts = sorted(top.articles, key=lambda a: -a.weight)[:6]
        materials = {"articles": [{"source": a.source_name, "title": a.title,
                                   "summary": truncate(a.summary, 400)} for a in arts]}
        sources = [{"name": a.source_name, "url": a.url} for a in arts]

    html_out = None
    if llm.enabled:
        data = llm.json(prompts.system_for(profile.system_prompt),
                        prompts.deepdive_user_prompt(profile.label, title, materials), max_tokens=1800)
        if isinstance(data, dict) and data.get("paragraphs"):
            parts = [f"<b>{_esc(data.get('headline') or title)}</b>", ""]
            if data.get("intro"):
                parts += [_esc(data["intro"]), ""]
            for sec in data.get("paragraphs", [])[:5]:
                if sec.get("heading"):
                    parts.append(f"<b>{_esc(sec['heading'])}</b>")
                parts.append(_esc(sec.get("text", "")))
                parts.append("")
            if data.get("closing"):
                parts += [f"<i>{_esc(data['closing'])}</i>", ""]
            html_out = "\n".join(parts)
        else:
            warnings.append("Risposta LLM non valida per l'approfondimento: uso l'assemblaggio grezzo.")
    else:
        warnings.append("LLM non configurato: approfondimento assemblato dai dati grezzi, da riscrivere.")

    body = html_out or _fallback_html(materials)
    header = "" if html_out else f"<b>{_esc(title)}</b>\n\n"
    html = header + body

    seen, dedup = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            dedup.append(s)
    if dedup:
        html += "\n<b>Fonti</b>\n" + "\n".join(f'• <a href="{_esc(s["url"])}">{_esc(s["name"])}</a>' for s in dedup[:10])

    return Deepdive(profile_id=profile.id, day=day, title=title, html=html.strip(), sources=dedup, warnings=warnings)
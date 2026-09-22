"""Post 'versus' (profilo politica): cosa dicono due partiti sullo stesso tema, dove divergono,
fact-check di terzi esistenti e cosa c'era nel programma. Trattamento simmetrico per tutti."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from newsbot.db import DB
from newsbot.llm import prompts
from newsbot.llm.client import LLM
from newsbot.models import Claim, PostPlan, Profile
from newsbot.politics.factcheck import find_factchecks
from newsbot.politics.programs import program_excerpt
from newsbot.posts.common import build_caption, dedupe_sources, it_date, source_entry
from newsbot.processing.embeddings import Embedder
from newsbot.utils import truncate

log = logging.getLogger(__name__)


def _latest(claims: list[Claim]) -> Claim:
    return sorted(claims, key=lambda c: c.published_at)[-1]


def plan_versus(db: DB, profile: Profile, llm: LLM, embedder: Embedder, themes: dict,
                day: str, now: datetime) -> PostPlan | None:
    parties = profile.versus_parties
    if len(parties) < 2:
        return None
    a_name, b_name = parties[0], parties[1]
    since = now - timedelta(hours=max(profile.lookback_hours, 72))
    claims = db.get_claims(profile.id, since)

    by_theme: dict[str, dict[str, list[Claim]]] = defaultdict(lambda: defaultdict(list))
    for c in claims:
        by_theme[c.theme][c.party].append(c)
    candidates = [t for t, v in by_theme.items() if a_name in v and b_name in v]
    if not candidates:
        log.info("[%s] nessun tema con claim di entrambi i partiti", profile.id)
        return None
    theme = max(candidates, key=lambda t: sum(len(v) for v in by_theme[t].values()))
    theme_label = themes.get(theme, {}).get("label", theme)
    per_party = by_theme[theme]
    warnings: list[str] = []

    # --- posizioni e disaccordo
    positions, key_diff, level = {}, None, None
    if llm.enabled:
        payload = {p: [{"claim": c.claim, "fonte": c.source_name, "data": c.published_at.date().isoformat()}
                       for c in per_party[p][:4]] for p in (a_name, b_name)}
        out = llm.json(prompts.system_for(profile.system_prompt),
                       prompts.compare_user_prompt(theme_label, payload))
        if isinstance(out, dict) and isinstance(out.get("positions"), dict):
            positions = {p: truncate(str(out["positions"].get(p, "")), 180) for p in (a_name, b_name)}
            key_diff = out.get("key_difference")
            level = out.get("disagreement")
    if not positions or not all(positions.values()):
        if llm.enabled:
            warnings.append("Confronto LLM non disponibile: uso le dichiarazioni originali.")
        else:
            warnings.append("LLM non configurato: posizioni = prima dichiarazione estratta. Rivedi.")
        positions = {p: truncate(_latest(per_party[p]).claim, 180) for p in (a_name, b_name)}

    def side(p: str) -> dict:
        c = _latest(per_party[p])
        info = profile.parties.get(p, {})
        return {"party": p, "party_name": info.get("name", p), "color": info.get("color"),
                "text": positions[p], "quote": c.quote,
                "meta": f"{c.source_name}, {c.published_at.date().strftime('%d/%m/%Y')}"}

    left, right = side(a_name), side(b_name)

    # --- fact-check di terzi
    fc_since = now - timedelta(days=profile.factcheck_lookback_days)
    fc_candidates = db.get_articles(profile.id, fc_since, kinds=["factcheck"])
    query = " ".join([theme_label] + [c.claim for p in (a_name, b_name) for c in per_party[p][:2]])
    factchecks = find_factchecks(query, fc_candidates, embedder, k=2)

    # --- programma
    prog_slide = None
    prog = {p: program_excerpt(db, embedder, p, query) for p in (a_name, b_name)}
    if any(prog.values()):
        def pside(p: str) -> dict:
            info = profile.parties.get(p, {})
            ex = prog[p]
            return {"party": p, "party_name": info.get("name", p), "color": info.get("color"),
                    "text": ex["text"] if ex else "Nessun passaggio pertinente trovato nel programma.",
                    "quote": None, "meta": f"Programma ({ex['file']})" if ex else ""}
        prog_slide = {"type": "versus", "heading": "Cosa c'era nel programma",
                      "theme": theme_label, "left": pside(a_name), "right": pside(b_name),
                      "footer": "Estratti dai programmi ufficiali: verifica sempre il testo integrale."}

    slides: list[dict] = [
        {"type": "cover", "title": f"{theme_label}: cosa dicono {a_name} e {b_name}",
         "subtitle": profile.label, "day": it_date(day)},
        {"type": "versus", "heading": "Le posizioni", "theme": theme_label, "left": left, "right": right,
         "footer": truncate(f"Dove divergono: {key_diff}", 180) if key_diff else
                   (f"Livello di disaccordo: {level}" if level else "")},
    ]
    if prog_slide:
        slides.append(prog_slide)
    slides.append({
        "type": "factcheck", "theme": theme_label, "items": factchecks,
        "note": ("Verdetti e analisi sono dei fact-checker citati, non del bot."
                 if factchecks else
                 "Non abbiamo trovato fact-check pubblicati su questo tema: le affermazioni restano non verificate."),
    })

    sources = [source_entry(c.source_name, c.url, c.claim) for p in (a_name, b_name) for c in per_party[p][:2]]
    sources += [source_entry(f["source"], f["url"], f["title"]) for f in factchecks]
    sources = dedupe_sources(sources)
    slides.append({"type": "sources",
                   "groups": [{"n": i, "headline": s["title"] or s["name"], "names": [s["name"]]}
                              for i, s in enumerate(sources[:8], start=1)],
                   "note": "Dichiarazioni riportate come tali, non come fatti verificati."})

    if not factchecks:
        warnings.append("Nessun fact-check collegato: la slide lo dichiara ('non verificato').")
    intro = f"{theme_label}: cosa dicono {a_name} e {b_name}, e dove divergono."
    caption = build_caption(profile, intro, [f"{a_name}: {positions[a_name]}", f"{b_name}: {positions[b_name]}"])
    return PostPlan(profile_id=profile.id, post_type="versus", day=day, slides=slides,
                    caption=caption, sources=sources, warnings=warnings)

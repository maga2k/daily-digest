"""Prompt. Tenerli qui rende facile iterare sulla qualità senza toccare la logica."""
from __future__ import annotations

import json

BASE_RULES = """\
Sei l'editor di un account Instagram che riassume le notizie in caroselli.
Regole inderogabili:
1. Usa SOLO informazioni presenti nel materiale fornito. Non aggiungere fatti, numeri, date o citazioni.
2. Attribuisci ogni affermazione alla sua fonte ("secondo X", "X riferisce").
3. Tono neutro e chiaro, in italiano. Frasi brevi (le slide hanno poco spazio).
4. Non esprimere opinioni né giudizi di verità. Per le dichiarazioni politiche riporta cosa è stato detto,
   e cita eventuali fact-check solo se forniti, attribuiti a chi li ha pubblicati.
5. Se le fonti si contraddicono, dillo esplicitamente invece di scegliere.
6. Rispondi SOLO con JSON valido, senza testo prima o dopo.
"""


def system_for(profile_prompt: str) -> str:
    return BASE_RULES + ("\nIndicazioni specifiche del profilo:\n" + profile_prompt.strip() if profile_prompt else "")


def digest_user_prompt(label: str, clusters_payload: list[dict], hashtags: list[str]) -> str:
    schema = {
        "hook": "frase di apertura per la cover (max 90 caratteri)",
        "stories": [{
            "cluster_id": "int, uguale a quello fornito",
            "headline": "titolo della storia (max 80 caratteri)",
            "bullets": ["2-3 punti, max 110 caratteri ciascuno"],
            "framing": "una riga su come le testate divergono nel raccontarla, oppure null",
            "note": "es. 'preprint non ancora rivisto' / 'dato non verificato', oppure null",
        }],
        "caption": "caption Instagram (max 600 caratteri), senza hashtag e senza link",
    }
    return (
        f"Profilo: {label}\n"
        f"Materiale (cluster di articoli sullo stesso evento):\n{json.dumps(clusters_payload, ensure_ascii=False, indent=1)}\n\n"
        f"Produci un JSON con questa forma:\n{json.dumps(schema, ensure_ascii=False, indent=1)}\n"
        "Una storia per cluster, nello stesso ordine."
    )


def claims_user_prompt(party: str, source_name: str, text: str, themes: dict[str, str]) -> str:
    return (
        f"Testo pubblicato da/su {party} ({source_name}):\n\"\"\"\n{text[:4000]}\n\"\"\"\n\n"
        f"Temi ammessi (usa SOLO queste chiavi): {json.dumps(themes, ensure_ascii=False)}\n"
        "Estrai fino a 3 affermazioni (claim) che il partito fa su uno di questi temi. "
        "Per ogni claim: una parafrasi neutra (max 200 caratteri) e, se possibile, una citazione "
        "LETTERALE dal testo di al massimo 15 parole (altrimenti null). Non giudicare la verità.\n"
        'Rispondi con: {"claims": [{"theme": "...", "claim": "...", "quote": "..." | null}]}. '
        'Se non ci sono claim sui temi ammessi: {"claims": []}.'
    )


def compare_user_prompt(theme_label: str, by_party: dict[str, list[dict]]) -> str:
    return (
        f"Tema: {theme_label}\nDichiarazioni per partito:\n"
        f"{json.dumps(by_party, ensure_ascii=False, indent=1)}\n\n"
        "Confronta le posizioni in modo simmetrico (stessa lunghezza e stessi criteri per ogni partito). "
        "Rispondi con JSON: "
        '{"positions": {"<partito>": "sintesi neutra della posizione, max 170 caratteri"}, '
        '"disagreement": "alto|medio|basso|nessuno", '
        '"key_difference": "in cosa divergono, max 160 caratteri, oppure null"}'
    )

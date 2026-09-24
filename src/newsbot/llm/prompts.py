"""Prompt. Tenerli qui rende facile iterare sulla qualità senza toccare la logica."""
from __future__ import annotations

import json

BASE_RULES = """\
Sei l'editor di un account Instagram che riassume le notizie in caroselli.
Regole inderogabili:
1. Usa SOLO informazioni presenti nel materiale fornito. Non aggiungere fatti, numeri, date, nomi
   o citazioni che non compaiano nel materiale. Vale anche per numeri "di cornice" nella caption
   (es. "sette notizie"): non scriverli se non corrispondono esattamente al conteggio reale.
2. Attribuisci ogni affermazione alla sua fonte ("secondo X", "X riferisce").
3. Tono neutro e chiaro, in italiano. Frasi brevi (le slide hanno poco spazio).
4. Non esprimere opinioni né giudizi di verità. Per le dichiarazioni politiche riporta cosa è stato detto,
   e cita eventuali fact-check solo se forniti, attribuiti a chi li ha pubblicati.
5. Se le fonti si contraddicono, dillo esplicitamente invece di scegliere.
6. Rispondi SOLO con JSON valido, senza testo prima o dopo.
7. Non concludere con inviti a seguire il profilo né con giudizi sulla propria affidabilità
   (niente "verificato", "neutro", "accurato" riferiti a te stesso): lo dice la disclosure, non il testo.
8. Scrivi esclusivamente in italiano: non inserire parole o frasi in altre lingue, nemmeno un singolo termine.
9. Usa i nomi propri (persone, luoghi, aziende) esattamente come compaiono nel materiale fornito.
   Se non sei sicuro dell'ortografia esatta di un nome, riformula la frase senza quel nome
   piuttosto che rischiare un errore di trascrizione.
10. Riferisciti alle testate sempre con il loro nome proprio (es. "DW", "Al Jazeera"), mai con
    aggettivi di nazionalità o provenienza ("la testata tedesca", "l'emittente qatariota") a meno
    che quell'informazione non compaia esplicitamente nel materiale fornito.
   """


def system_for(profile_prompt: str) -> str:
    return BASE_RULES + ("\nIndicazioni specifiche del profilo:\n" + profile_prompt.strip() if profile_prompt else "")


def digest_user_prompt(label: str, clusters_payload: list[dict], hashtags: list[str]) -> str:
    schema = {
        "hook": "frase di apertura per la cover (max 90 caratteri)",
                "caption": "caption Instagram (max 900 caratteri), senza hashtag e senza link. "
                   "La prima frase deve essere un gancio che spinge a continuare a leggere, "
                   "non un'etichetta generica come 'riassunto delle notizie' o 'ecco cosa è successo'. "
                   "Tocca ogni storia dell'elenco, nello stesso ordine, con una o due frasi ciascuna "
                   "separate da una riga vuota: non fonderle in un unico paragrafo continuo. "
                   "Per almeno una storia aggiungi una frase di contesto o del perché conta, non solo il fatto. "
                   "Chiudi con una frase che colleghi le storie tra loro (un filo comune o un contrasto), "
                   "non un ulteriore elenco.",
        "stories": [{
            "cluster_id": "int, uguale a quello fornito",
            "headline": "titolo della storia (max 80 caratteri)",
            "bullets": ["2-3 punti, max 110 caratteri ciascuno"],
            "framing": "una riga su come le testate divergono nel raccontarla, oppure null",
            "note": "es. 'preprint non ancora rivisto' / 'dato non verificato', oppure null",
        }],
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


def deepdive_user_prompt(label: str, title: str, materials: dict) -> str:
    schema = {
        "headline": "titolo dell'approfondimento, puoi migliorare quello fornito (max 100 caratteri)",
        "intro": "1-2 frasi di contesto: perché se ne parla, senza ripetere il titolo",
        "paragraphs": [{
            "heading": "titolo breve della sezione (es. 'Cosa dice X', 'Il contesto', 'Cosa dicono i fatti'), oppure null",
            "text": "80-160 parole, in italiano, con attribuzione esplicita di ogni affermazione",
        }],
        "closing": "1-2 frasi finali: perché conta, cosa succede dopo, o cosa resta incerto. "
                   "Non un invito a seguire il profilo.",
    }
    return (
        f"Profilo: {label}\nArgomento: {title}\n"
        f"Materiale disponibile (usa SOLO questo, non aggiungere altro):\n"
        f"{json.dumps(materials, ensure_ascii=False, indent=1)}\n\n"
        "Scrivi un approfondimento più lungo e ragionato di una caption Instagram, adatto a un messaggio "
        "Telegram per lettori che vogliono capire meglio, non solo la notizia veloce. Al massimo 3-4 sezioni. "
        "Se nel materiale ci sono due parti che dicono cose diverse, dedica una sezione a ciascuna, "
        "in modo simmetrico, e una sezione a cosa dicono le verifiche di terzi (se presenti), oppure "
        "dichiara esplicitamente che non ce ne sono ('non verificato').\n"
        f"Rispondi con questo JSON:\n{json.dumps(schema, ensure_ascii=False, indent=1)}"
    )
"""Dati FITTIZI per provare l'intera pipeline offline (nessuna rete, nessuna chiave API).
(Sono tutti in italiano perché il backend TF-IDF non sa accoppiare titoli in lingue diverse:
per il vero clustering multilingua IT/EN serve il backend "st", vedi README.)

Tutto ciò che è qui dentro è inventato: luoghi, aziende e persino le 'dichiarazioni' dei partiti
sono segnaposto marcati [DEMO], così non si possono scambiare per notizie o posizioni reali."""
from __future__ import annotations

from datetime import timedelta

from newsbot.db import DB
from newsbot.models import Profile
from newsbot.utils import utcnow


def seed_demo(db: DB, profiles: dict[str, Profile]) -> None:
    now = utcnow()

    def add(profile, sid, name, title, summary, hours_ago, kind="news", party=None, weight=1.0,
            eng=0.0, text="", lang="it"):
        db.add_article(url=f"https://example.org/{profile}/{sid}/{abs(hash(title)) % 10**8}",
                       profile=profile, source_id=sid, source_name=name, title=title, summary=summary,
                       text=text or summary, published_at=now - timedelta(hours=hours_ago), kind=kind,
                       party=party, weight=weight, engagement=eng, lang=lang)

    # ---- mondo
    add("mondo", "ansa", "ANSA", "[DEMO] Vertice sul clima a Nordhavn: firmato l'accordo sulle emissioni",
        "I delegati di 40 paesi hanno firmato a Nordhavn un accordo per ridurre le emissioni entro il 2035.", 3)
    add("mondo", "bbc_world", "BBC News", "[DEMO] Si chiude il vertice sul clima di Nordhavn: intesa sulle emissioni",
        "Delegati di 40 paesi firmano l'intesa sulle emissioni al vertice sul clima di Nordhavn.", 4, weight=1.1)
    add("mondo", "guardian", "The Guardian", "[DEMO] Vertice di Nordhavn: firmata l'intesa sulle emissioni, ma i critici parlano di obiettivi troppo deboli",
        "Secondo i critici l'accordo sulle emissioni firmato a Nordhavn fissa obiettivi troppo deboli.", 2)
    add("mondo", "ansa", "ANSA", "[DEMO] Sciopero dei trasporti a Valdoria: treni e metro fermi",
        "Sciopero generale dei trasporti a Valdoria: treni e metropolitane fermi per 24 ore.", 6)
    add("mondo", "dw", "DW", "[DEMO] Sciopero dei trasporti a Valdoria ferma treni e metro",
        "Uno sciopero di 24 ore dei trasporti a Valdoria ha fermato treni e servizi di metropolitana.", 7)
    add("mondo", "aljazeera", "Al Jazeera", "[DEMO] Festival del cinema di Portomare: al via la 10a edizione",
        "Al via la decima edizione del festival del cinema di Portomare.", 5)

    # ---- politica: testate
    add("politica", "ansa_pol", "ANSA Politica", "[DEMO] Manovra, il testo arriva in Parlamento",
        "Il governo ha presentato in Parlamento il testo della manovra con misure su sanità e lavoro.", 5)
    add("politica", "repubblica_pol", "la Repubblica", "[DEMO] Manovra in Parlamento: le misure su sanità e lavoro",
        "Depositato il testo della manovra: previste misure su sanità e lavoro, opposizioni critiche.", 4)
    add("politica", "corriere_pol", "Corriere della Sera", "[DEMO] La manovra approda in Parlamento",
        "La manovra approda in Parlamento con misure su sanità e lavoro.", 6)
    add("politica", "ansa_pol", "ANSA Politica", "[DEMO] Legge elettorale, aperto il confronto tra i partiti",
        "Si apre il confronto tra i partiti sulla riforma della legge elettorale.", 8)
    add("politica", "fatto_pol", "Il Fatto Quotidiano", "[DEMO] Legge elettorale: il confronto tra maggioranza e opposizione",
        "Confronto tra maggioranza e opposizione sulla riforma della legge elettorale.", 9, weight=0.9)

    # ---- politica: posizioni dichiarate (segnaposto, NON dichiarazioni reali)
    add("politica", "fdi_sito", "Fratelli d'Italia (sito)", "[DEMO] Comunicato di prova FdI sulla sanità",
        "[DEMO] Segnaposto: il partito afferma che le risorse per la sanità e per le liste d'attesa sono aumentate.",
        10, kind="party", party="FdI")
    add("politica", "pd_sito", "Partito Democratico (sito)", "[DEMO] Comunicato di prova PD sulla sanità",
        "[DEMO] Segnaposto: il partito afferma che le risorse per la sanità e per le liste d'attesa sono insufficienti.",
        12, kind="party", party="PD")
    add("politica", "fdi_sito", "Fratelli d'Italia (sito)", "[DEMO] Comunicato di prova FdI sul lavoro",
        "[DEMO] Segnaposto: il partito afferma che l'occupazione e i contratti di lavoro stanno migliorando.",
        20, kind="party", party="FdI")

    # ---- politica: fact-check di terzi (segnaposto)
    add("politica", "pagella", "Pagella Politica", "[DEMO] Fact-check di prova: le risorse per la sanità e le liste d'attesa",
        "[DEMO] Analisi di prova sulle risorse per la sanità e sulle liste d'attesa.", 30, kind="factcheck")

    # ---- scienza
    add("scienza", "nature", "Nature", "[DEMO] Nuovo studio: un composto sperimentale riduce l'infiammazione nei topi",
        "Uno studio peer-reviewed condotto su topi mostra che un composto sperimentale riduce l'infiammazione.", 10, weight=1.3)
    add("scienza", "guardian_sci", "The Guardian Science", "[DEMO] Composto sperimentale riduce l'infiammazione nei topi, secondo uno studio",
        "Uno studio peer-reviewed sui topi rileva che un composto sperimentale riduce l'infiammazione.", 9)
    add("scienza", "medrxiv", "medRxiv (preprint)", "[DEMO] Preprint: associazione tra sonno e memoria in adulti",
        "Preprint non ancora sottoposto a revisione: associazione tra qualità del sonno e memoria in 800 adulti.", 14, weight=0.6)

    # ---- tech
    add("tech", "verge", "The Verge", "[DEMO] Lumen Labs rilascia un modello di IA open source",
        "Lumen Labs ha rilasciato un modello di IA open source con licenza permissiva.", 3)
    add("tech", "ars", "Ars Technica", "[DEMO] Lumen Labs apre il codice del nuovo modello di IA, benchmark indipendenti in arrivo",
        "Lumen Labs rende open source un nuovo modello di IA; i benchmark indipendenti non sono ancora disponibili.", 2, weight=1.1)
    add("tech", "hn", "Hacker News", "[DEMO] Lumen Labs, rilascio del modello di IA open source: la discussione",
        "Discussione sul rilascio del modello di IA open source di Lumen Labs.", 3, weight=0.8, eng=850)
    add("tech", "techcrunch", "TechCrunch", "[DEMO] La startup Orbitly raccoglie un round seed per il software satellitare",
        "Orbitly raccoglie un round seed per sviluppare software per gli operatori satellitari.", 5, weight=0.9)

    # ---- programmi (segnaposto)
    db.replace_program("FdI", "FdI-demo.txt", [
        "[DEMO] Segnaposto programma. Sanità: investimenti nella sanità pubblica e riduzione delle liste d'attesa.",
        "[DEMO] Segnaposto programma. Lavoro: incentivi all'occupazione e ai contratti stabili."])
    db.replace_program("PD", "PD-demo.txt", [
        "[DEMO] Segnaposto programma. Sanità: rafforzare il servizio sanitario nazionale e le liste d'attesa.",
        "[DEMO] Segnaposto programma. Lavoro: salario minimo e tutele per i lavoratori precari."])

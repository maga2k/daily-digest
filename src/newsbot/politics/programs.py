"""Programmi elettorali / pagine "posizioni": ingest una tantum e ricerca per tema.

Metti i file in data/programs/<Partito>.txt|.md|.pdf (es. FdI.pdf, PD.txt) e lancia
`newsbot programs`. Il nome del file (senza estensione) è la sigla del partito.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from newsbot.db import DB
from newsbot.processing.embeddings import Embedder
from newsbot.utils import truncate

log = logging.getLogger(__name__)


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("per i PDF installa l'extra: pip install -e '.[pdf]'") from exc
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= size:
            cur = f"{cur}\n{p}".strip()
        else:
            if cur:
                chunks.append(cur)
            while len(p) > size:                      # paragrafo enorme: spezzalo
                chunks.append(p[:size])
                p = p[size - overlap:]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def ingest_programs(db: DB, folder: Path) -> int:
    n = 0
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in (".txt", ".md", ".pdf") or path.name.startswith("."):
            continue
        chunks = chunk_text(read_file(path))
        db.replace_program(path.stem, path.name, chunks)
        log.info("programma %s: %d chunk", path.stem, len(chunks))
        n += len(chunks)
    return n


def program_excerpt(db: DB, embedder: Embedder, party: str, query: str) -> dict | None:
    """Passaggio del programma più vicino al tema/claim, se abbastanza pertinente."""
    chunks = db.get_program_chunks(party)
    if not chunks:
        return None
    sims = embedder.similarity([query], [c["text"] for c in chunks])[0]
    i = int(sims.argmax())
    if sims[i] < embedder.program_threshold:
        return None
    return {"party": party, "file": chunks[i]["source_file"], "text": truncate(chunks[i]["text"], 320),
            "similarity": round(float(sims[i]), 3)}

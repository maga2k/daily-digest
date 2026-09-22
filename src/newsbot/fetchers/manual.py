"""Import manuale da CSV: il modo più semplice (e sicuro) per portare dentro post social.

Metti file .csv in data/manual/ con colonne:
    published_at (ISO, es. 2026-09-19T10:30), profile, source, kind (party|social|news),
    party (opzionale), url, text
Ogni volta che li aggiungi/modifichi: `newsbot manual`.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

from newsbot.db import DB
from newsbot.utils import slugify, truncate, utcnow

log = logging.getLogger(__name__)


def import_manual(db: DB, folder: Path, profiles: set[str]) -> int:
    added = 0
    for path in sorted(folder.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                profile = (row.get("profile") or "").strip()
                text = (row.get("text") or "").strip()
                if profile not in profiles or not text:
                    continue
                try:
                    dt = datetime.fromisoformat((row.get("published_at") or "").strip())
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = utcnow()
                source = (row.get("source") or "manuale").strip()
                url = (row.get("url") or "").strip() or f"manual://{path.stem}/{slugify(text)[:40]}"
                ok = db.add_article(
                    url=url, profile=profile, source_id=f"manual_{slugify(source)}", source_name=source,
                    title=truncate(text.split("\n", 1)[0], 140), summary=truncate(text, 600), text=text,
                    published_at=dt, kind=(row.get("kind") or "social").strip(),
                    party=(row.get("party") or "").strip() or None,
                )
                added += int(ok)
    log.info("import manuale: %d nuovi elementi", added)
    return added

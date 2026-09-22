"""Storage SQLite. Un'unica classe DB con i metodi che servono alla pipeline."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from newsbot.models import Article, Claim, Cluster
from newsbot.utils import from_iso, to_iso, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL,
  profile TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'news',
  party TEXT,
  title TEXT NOT NULL,
  summary TEXT DEFAULT '',
  text TEXT DEFAULT '',
  lang TEXT DEFAULT 'it',
  weight REAL DEFAULT 1.0,
  published_at TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  sentiment REAL,
  engagement REAL DEFAULT 0,
  claims_done INTEGER DEFAULT 0,
  UNIQUE(url, profile)
);
CREATE INDEX IF NOT EXISTS idx_articles_profile_pub ON articles(profile, published_at);

CREATE TABLE IF NOT EXISTS clusters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile TEXT NOT NULL,
  day TEXT NOT NULL,
  title TEXT NOT NULL,
  score REAL NOT NULL,
  framing_spread REAL,
  article_ids TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clusters_profile_day ON clusters(profile, day);

CREATE TABLE IF NOT EXISTS claims(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_id INTEGER NOT NULL,
  profile TEXT NOT NULL,
  party TEXT NOT NULL,
  theme TEXT NOT NULL,
  claim TEXT NOT NULL,
  quote TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(article_id, theme, claim)
);

CREATE TABLE IF NOT EXISTS program_chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  party TEXT NOT NULL,
  source_file TEXT NOT NULL,
  idx INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_program_party ON program_chunks(party);

CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile TEXT NOT NULL,
  post_type TEXT NOT NULL,
  day TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',   -- draft | sent | approved | published
  output_dir TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def init(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ articles
    def add_article(self, *, url: str, profile: str, source_id: str, source_name: str,
                    title: str, published_at: datetime, kind: str = "news",
                    party: str | None = None, summary: str = "", text: str = "",
                    lang: str = "it", weight: float = 1.0, engagement: float = 0.0) -> bool:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO articles
               (url, profile, source_id, source_name, kind, party, title, summary, text, lang,
                weight, published_at, fetched_at, engagement)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (url, profile, source_id, source_name, kind, party, title, summary, text, lang,
             weight, to_iso(published_at), to_iso(utcnow()), engagement),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get_articles(self, profile: str, since: datetime, kinds: list[str] | None = None) -> list[Article]:
        q = "SELECT * FROM articles WHERE profile=? AND published_at>=?"
        args: list = [profile, to_iso(since)]
        if kinds:
            q += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += kinds
        q += " ORDER BY published_at DESC"
        return [Article.from_row(r) for r in self.conn.execute(q, args)]

    def articles_by_ids(self, ids: list[int]) -> list[Article]:
        if not ids:
            return []
        q = f"SELECT * FROM articles WHERE id IN ({','.join('?' * len(ids))})"
        return [Article.from_row(r) for r in self.conn.execute(q, ids)]

    def set_sentiment(self, article_id: int, value: float | None) -> None:
        self.conn.execute("UPDATE articles SET sentiment=? WHERE id=?", (value, article_id))
        self.conn.commit()

    def mark_claims_done(self, article_id: int) -> None:
        self.conn.execute("UPDATE articles SET claims_done=1 WHERE id=?", (article_id,))
        self.conn.commit()

    def pending_claim_articles(self, profile: str, since: datetime, kinds: list[str]) -> list[Article]:
        q = (f"SELECT * FROM articles WHERE profile=? AND published_at>=? AND claims_done=0 "
             f"AND kind IN ({','.join('?' * len(kinds))}) ORDER BY published_at DESC")
        return [Article.from_row(r) for r in self.conn.execute(q, [profile, to_iso(since), *kinds])]

    def count_articles(self, profile: str | None = None) -> int:
        if profile:
            return self.conn.execute("SELECT COUNT(*) FROM articles WHERE profile=?", (profile,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    # ------------------------------------------------------------------ clusters
    def save_clusters(self, profile: str, day: str, clusters: list[Cluster]) -> None:
        self.conn.execute("DELETE FROM clusters WHERE profile=? AND day=?", (profile, day))
        for c in clusters:
            cur = self.conn.execute(
                "INSERT INTO clusters(profile, day, title, score, framing_spread, article_ids, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (profile, day, c.title, c.score, c.framing_spread,
                 json.dumps([a.id for a in c.articles]), to_iso(utcnow())),
            )
            c.id = cur.lastrowid
        self.conn.commit()

    def load_clusters(self, profile: str, day: str) -> list[Cluster]:
        rows = self.conn.execute(
            "SELECT * FROM clusters WHERE profile=? AND day=? ORDER BY score DESC", (profile, day)
        ).fetchall()
        out = []
        for r in rows:
            arts = self.articles_by_ids(json.loads(r["article_ids"]))
            out.append(Cluster(profile=profile, title=r["title"], articles=arts, score=r["score"],
                               id=r["id"], framing_spread=r["framing_spread"]))
        return out

    # ------------------------------------------------------------------ claims
    def add_claim(self, *, article_id: int, profile: str, party: str, theme: str,
                  claim: str, quote: str | None) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO claims(article_id, profile, party, theme, claim, quote, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (article_id, profile, party, theme, claim, quote, to_iso(utcnow())),
        )
        self.conn.commit()

    def get_claims(self, profile: str, since: datetime) -> list[Claim]:
        rows = self.conn.execute(
            """SELECT c.*, a.url, a.source_name, a.published_at FROM claims c
               JOIN articles a ON a.id=c.article_id
               WHERE c.profile=? AND a.published_at>=? ORDER BY a.published_at DESC""",
            (profile, to_iso(since)),
        ).fetchall()
        return [Claim(id=r["id"], article_id=r["article_id"], party=r["party"], theme=r["theme"],
                      claim=r["claim"], quote=r["quote"], url=r["url"], source_name=r["source_name"],
                      published_at=from_iso(r["published_at"])) for r in rows]

    # ------------------------------------------------------------------ programmi
    def replace_program(self, party: str, source_file: str, chunks: list[str]) -> None:
        self.conn.execute("DELETE FROM program_chunks WHERE party=? AND source_file=?", (party, source_file))
        self.conn.executemany(
            "INSERT INTO program_chunks(party, source_file, idx, text) VALUES (?,?,?,?)",
            [(party, source_file, i, t) for i, t in enumerate(chunks)],
        )
        self.conn.commit()

    def get_program_chunks(self, party: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT source_file, idx, text FROM program_chunks WHERE party=? ORDER BY source_file, idx",
            (party,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ posts
    def add_post(self, profile: str, post_type: str, day: str, output_dir: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO posts(profile, post_type, day, output_dir, created_at) VALUES (?,?,?,?,?)",
            (profile, post_type, day, output_dir, to_iso(utcnow())),
        )
        self.conn.commit()
        return cur.lastrowid

    def set_post_status(self, post_id: int, status: str) -> None:
        self.conn.execute("UPDATE posts SET status=? WHERE id=?", (status, post_id))
        self.conn.commit()

    def list_posts(self, day: str | None = None) -> list[sqlite3.Row]:
        if day:
            return self.conn.execute("SELECT * FROM posts WHERE day=? ORDER BY id DESC", (day,)).fetchall()
        return self.conn.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 50").fetchall()

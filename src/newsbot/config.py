"""Caricamento configurazione: .env + config/*.yaml."""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from newsbot.models import Profile, Source

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    root: Path = ROOT
    config_dir: Path = ROOT / "config"
    data_dir: Path = ROOT / "data"
    db_path: Path = ROOT / "data" / "newsbot.db"
    output_dir: Path = ROOT / "output"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5"
    embedding_backend: str = "auto"      # auto | st | tfidf
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    sentiment_backend: str = "none"      # none | hf
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    apify_token: str | None = None
    user_agent: str = "newsbot/0.1 (progetto personale; rispetta robots.txt)"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        e = os.environ.get

        def path(var: str, default: Path) -> Path:
            v = e(var)
            return (ROOT / v).resolve() if v and not Path(v).is_absolute() else Path(v or default)

        return cls(
            db_path=path("NEWSBOT_DB", ROOT / "data" / "newsbot.db"),
            output_dir=path("NEWSBOT_OUTPUT", ROOT / "output"),
            anthropic_api_key=e("ANTHROPIC_API_KEY") or None,
            llm_model=e("NEWSBOT_MODEL", "claude-sonnet-5"),
            embedding_backend=e("NEWSBOT_EMBEDDINGS", "auto"),
            embedding_model=e("NEWSBOT_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
            sentiment_backend=e("NEWSBOT_SENTIMENT", "none"),
            telegram_token=e("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=e("TELEGRAM_CHAT_ID") or None,
            apify_token=e("APIFY_TOKEN") or None,
        )

    def resolved_embedding_backend(self) -> str:
        if self.embedding_backend != "auto":
            return self.embedding_backend
        return "st" if importlib.util.find_spec("sentence_transformers") else "tfidf"


def _yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profiles(settings: Settings) -> dict[str, Profile]:
    raw = _yaml(settings.config_dir / "profiles.yaml")["profiles"]
    srcs = _yaml(settings.config_dir / "sources.yaml").get("sources", {})
    profiles: dict[str, Profile] = {}
    known = set(Profile.__dataclass_fields__)
    for pid, cfg in raw.items():
        cfg = {k: v for k, v in cfg.items() if k in known and k != "sources"}
        sources = [Source(**{k: v for k, v in s.items() if k in Source.__dataclass_fields__})
                   for s in srcs.get(pid, [])]
        profiles[pid] = Profile(id=pid, sources=sources, **cfg)
    return profiles


def load_themes(settings: Settings) -> dict[str, dict[str, Any]]:
    return _yaml(settings.config_dir / "themes.yaml").get("themes", {})

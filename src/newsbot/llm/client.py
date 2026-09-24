"""Wrapper minimale su Anthropic o su un'API compatibile OpenAI (Groq, OpenRouter, Gemini, Ollama...).
Senza chiave `enabled` è False e i moduli chiamanti usano le versioni euristiche
(utile per test e sviluppo offline)."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from ftfy import fix_text

from newsbot.config import Settings

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, settings: Settings):
        self.model = settings.llm_model
        self.provider = settings.llm_provider
        self._client = None
        if self.provider == "anthropic" and settings.anthropic_api_key:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "openai_compatible" and settings.llm_api_key:
            import openai   # pip install -e ".[free-llm]"
            self._client = openai.OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        # rispetta i limiti dei piani gratuiti: attesa minima tra una chiamata e l'altra
        default_interval = 2.1 if self.provider == "openai_compatible" else 0.0
        self.min_interval = settings.llm_min_interval if settings.llm_min_interval is not None else default_interval
        self._last_call = 0.0

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        assert self._client is not None, "LLM non configurato"
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            if self.provider == "anthropic":
                msg = self._client.messages.create(
                    model=self.model, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            else:
                resp = self._client.chat.completions.create(
                    model=self.model, max_tokens=max_tokens,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                text = resp.choices[0].message.content or ""
            # alcuni provider (in particolare Groq con certi modelli) a volte restituiscono testo con
            # una codifica dei caratteri corrotta ("Ã¨" invece di "è"): ftfy la ripara qui, una volta
            # per tutte, cosi ogni comando che usa l'LLM (digest, versus, claims, deepdive) ne beneficia.
            return fix_text(text)
        finally:
            self._last_call = time.monotonic()

    def json(self, system: str, user: str, max_tokens: int = 2000, retries: int = 1) -> Any | None:
        """Chiede JSON e lo interpreta. Restituisce None se fallisce (il chiamante ha un fallback)."""
        if not self.enabled:
            return None
        for attempt in range(retries + 1):
            try:
                return parse_json(self.complete(system, user, max_tokens))
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM/JSON fallito (tentativo %d): %s", attempt + 1, exc)
        return None


def parse_json(text: str) -> Any:
    """Estrae il primo oggetto/array JSON da un testo (tollera ```json ... ```)."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("nessun JSON nella risposta")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start: end + 1])
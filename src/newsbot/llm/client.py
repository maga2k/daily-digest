"""Wrapper minimale sull'SDK Anthropic. Senza chiave API `enabled` è False e i moduli
chiamanti usano le versioni euristiche (utile per test e sviluppo offline)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from newsbot.config import Settings

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, settings: Settings):
        self.model = settings.llm_model
        self._client = None
        if settings.anthropic_api_key:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        assert self._client is not None, "LLM non configurato"
        msg = self._client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

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

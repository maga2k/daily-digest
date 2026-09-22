"""Sentiment opzionale. Sui titoli da solo dice poco: il valore è nel CONFRONTO tra testate
sullo stesso evento (framing_spread). Backend: none | hf (transformers)."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

HF_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"   # multilingua; verifica licenza/uso


class SentimentScorer:
    def __init__(self, backend: str = "none"):
        self.backend = backend
        self._pipe = None

    @property
    def enabled(self) -> bool:
        return self.backend == "hf"

    def score(self, texts: list[str]) -> list[float | None]:
        """Valori in [-1, 1]: p(positivo) - p(negativo)."""
        if not self.enabled:
            return [None] * len(texts)
        if self._pipe is None:
            from transformers import pipeline
            log.info("carico il modello di sentiment %s ...", HF_MODEL)
            self._pipe = pipeline("text-classification", model=HF_MODEL, top_k=None, truncation=True)
        out: list[float | None] = []
        for res in self._pipe(texts):
            probs = {r["label"].lower(): r["score"] for r in res}
            out.append(probs.get("positive", 0.0) - probs.get("negative", 0.0))
        return out

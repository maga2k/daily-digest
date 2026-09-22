"""Embeddings: sentence-transformers (multilingua, locale, consigliato) oppure TF-IDF (leggero).

Il backend TF-IDF non ha bisogno di scaricare modelli: va bene per testare la pipeline,
ma per titoli in lingue diverse (IT/EN) il backend "st" funziona molto meglio.
"""
from __future__ import annotations

import hashlib
import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger(__name__)

_STOP = set("""
il lo la i gli le un uno una di a da in con su per tra fra e ed o ma che non piu come anche
del dello della dei degli delle al allo alla ai agli alle dal dalla dai dalle nel nella nei nelle
sul sulla sui sulle si se e' è sono ha hanno nuovo nuova the of and to in for on with is are was
at by from an as it its this that be has have new
""".split())


class Embedder:
    # soglie di default per backend: (distanza coseno per clustering, similarità min fact-check,
    # similarità min programma elettorale)
    THRESHOLDS = {
        "st": (0.40, 0.45, 0.35),
        "tfidf": (0.85, 0.20, 0.08),
    }

    def __init__(self, backend: str = "tfidf", model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        if backend not in ("st", "tfidf"):
            raise ValueError(f"backend embeddings sconosciuto: {backend}")
        self.backend = backend
        self.model_name = model_name
        self._model = None
        self._cache: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ soglie
    @property
    def cluster_threshold(self) -> float:
        return self.THRESHOLDS[self.backend][0]

    @property
    def factcheck_threshold(self) -> float:
        return self.THRESHOLDS[self.backend][1]

    @property
    def program_threshold(self) -> float:
        return self.THRESHOLDS[self.backend][2]

    # ------------------------------------------------------------------ encoding
    def _st_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            log.info("carico il modello di embeddings %s ...", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """Restituisce una matrice (n, d) con righe normalizzate (norma 1)."""
        if not texts:
            return np.zeros((0, 1))
        if self.backend == "st":
            keys = [hashlib.md5(t.encode()).hexdigest() for t in texts]
            missing = [(k, t) for k, t in zip(keys, texts) if k not in self._cache]
            if missing:
                vecs = self._st_model().encode([t for _, t in missing], normalize_embeddings=True,
                                               show_progress_bar=False)
                for (k, _), v in zip(missing, vecs):
                    self._cache[k] = np.asarray(v)
            return np.vstack([self._cache[k] for k in keys])
        vec = TfidfVectorizer(sublinear_tf=True, strip_accents="unicode", ngram_range=(1, 2),
                              stop_words=list(_STOP), min_df=1)
        try:
            return vec.fit_transform(texts).toarray()
        except ValueError:  # vocabolario vuoto
            return np.zeros((len(texts), 1))

    def similarity(self, a: list[str], b: list[str]) -> np.ndarray:
        """Matrice di similarità coseno (len(a), len(b))."""
        if not a or not b:
            return np.zeros((len(a), len(b)))
        X = self.encode(list(a) + list(b))
        return X[: len(a)] @ X[len(a):].T

import hashlib
import math
import re
from threading import Lock

from sentence_transformers import SentenceTransformer

import app.core.settings as settings_module


class EmbeddingService:
    _model = None
    _model_error = None
    _model_key = None
    _lock = Lock()

    def __init__(self) -> None:
        pass

    @property
    def settings(self):
        return settings_module.get_settings()

    @property
    def dimension(self) -> int:
        return self.settings.embedding_dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        if model is not None:
            vectors = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return [vector.astype(float).tolist() for vector in vectors]

        return [self._fallback_embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else [0.0] * self.dimension

    def _get_model(self):
        current_key = (
            self.settings.embedding_model_name,
            self.settings.embedding_allow_downloads,
            self.dimension,
        )

        if (
            EmbeddingService._model_key == current_key
            and (EmbeddingService._model is not None or EmbeddingService._model_error is not None)
        ):
            return EmbeddingService._model

        with EmbeddingService._lock:
            if (
                EmbeddingService._model_key == current_key
                and (EmbeddingService._model is not None or EmbeddingService._model_error is not None)
            ):
                return EmbeddingService._model

            EmbeddingService._model = None
            EmbeddingService._model_error = None
            EmbeddingService._model_key = current_key

            if not self.settings.embedding_model_name:
                EmbeddingService._model_error = RuntimeError("Embedding model name is empty.")
                return None

            try:
                EmbeddingService._model = SentenceTransformer(
                    self.settings.embedding_model_name,
                    local_files_only=not self.settings.embedding_allow_downloads,
                )
            except Exception as exc:  # pragma: no cover - depends on host model availability
                EmbeddingService._model_error = exc
            return EmbeddingService._model

    def _fallback_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        terms = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text.lower())
        if not terms:
            return vector

        for term in terms:
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=16).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimension
            sign = -1.0 if digest[8] % 2 else 1.0
            weight = 1.0 + (digest[9] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

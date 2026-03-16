from __future__ import annotations

from threading import Lock

import httpx
from sentence_transformers import CrossEncoder

import app.core.settings as settings_module
from app.repositories.search_repository import SearchRepository


class RerankerService:
    _local_model = None
    _local_model_error = None
    _local_model_key = None
    _lock = Lock()

    @property
    def settings(self):
        return settings_module.get_settings()

    def rerank(self, *, query: str, hits: list[dict], top_n: int | None = None) -> tuple[list[dict], dict]:
        if not hits:
            return [], {"backend": "rule", "applied": False, "fallback_reason": "empty_hits"}

        budget = max(1, top_n or self.settings.reranker_top_n)
        candidates = hits[:budget]
        backend = self.settings.reranker_backend
        fallback_reason = None

        if backend == "cross_encoder_remote":
            reranked, diagnostics = self._rerank_remote(query=query, hits=candidates)
            if reranked is not None:
                return reranked + hits[budget:], diagnostics
            fallback_reason = diagnostics["fallback_reason"]

        elif backend == "cross_encoder_local":
            reranked, diagnostics = self._rerank_local(query=query, hits=candidates)
            if reranked is not None:
                return reranked + hits[budget:], diagnostics
            fallback_reason = diagnostics["fallback_reason"]

        reranked = self._rule_rerank(query=query, hits=candidates)
        return reranked + hits[budget:], {"backend": "rule", "applied": True, "fallback_reason": fallback_reason}

    def _rerank_local(self, *, query: str, hits: list[dict]) -> tuple[list[dict] | None, dict]:
        model = self._get_local_model()
        if model is None:
            return None, {"backend": "cross_encoder_local", "applied": False, "fallback_reason": "model_unavailable"}

        try:
            pairs = [[query, self._pair_text(item)] for item in hits]
            scores = model.predict(pairs)
        except Exception:
            return None, {"backend": "cross_encoder_local", "applied": False, "fallback_reason": "prediction_failed"}

        reranked = []
        for item, score in zip(hits, scores, strict=True):
            reranked.append(
                {
                    **item,
                    "relevance_score": round(float(score), 6),
                    "rerank_score": round(float(score), 6),
                }
            )
        reranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return reranked, {"backend": "cross_encoder_local", "applied": True, "fallback_reason": None}

    def _rerank_remote(self, *, query: str, hits: list[dict]) -> tuple[list[dict] | None, dict]:
        if not self.settings.reranker_remote_url:
            return None, {"backend": "cross_encoder_remote", "applied": False, "fallback_reason": "missing_url"}

        payload = {
            "query": query,
            "documents": [self._pair_text(item) for item in hits],
        }
        try:
            with httpx.Client(timeout=self.settings.reranker_remote_timeout_seconds) as client:
                response = client.post(self.settings.reranker_remote_url, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception:
            return None, {"backend": "cross_encoder_remote", "applied": False, "fallback_reason": "request_failed"}

        scores = data.get("scores")
        if not isinstance(scores, list) or len(scores) != len(hits):
            return None, {"backend": "cross_encoder_remote", "applied": False, "fallback_reason": "invalid_response"}

        reranked = []
        for item, score in zip(hits, scores, strict=True):
            reranked.append(
                {
                    **item,
                    "relevance_score": round(float(score), 6),
                    "rerank_score": round(float(score), 6),
                }
            )
        reranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return reranked, {"backend": "cross_encoder_remote", "applied": True, "fallback_reason": None}

    def _rule_rerank(self, *, query: str, hits: list[dict]) -> list[dict]:
        normalized_query = " ".join(query.split()).lower()
        terms = SearchRepository().build_query_terms(query)
        reranked: list[dict] = []
        for item in hits:
            title = item["source_title"].lower()
            haystack = f"{title} {item.get('excerpt', '')} {item.get('normalized_text', '')}".lower()
            score = float(item.get("relevance_score", 0.0))
            score += 0.8 * sum(1 for term in terms if term in title)
            score += 0.35 * sum(1 for term in terms if term in haystack)
            if normalized_query and normalized_query in haystack:
                score += 2.2
            if item["source_type"] in {"file_pdf", "file_docx"}:
                score += 0.1
            reranked.append({**item, "relevance_score": round(score, 6)})
        reranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return reranked

    def _pair_text(self, item: dict) -> str:
        parts = [
            item.get("source_title", ""),
            item.get("heading_path", ""),
            item.get("field_label", ""),
            item.get("excerpt", ""),
            item.get("normalized_text", ""),
        ]
        return "\n".join(part for part in parts if part)

    def _get_local_model(self):
        current_key = (
            self.settings.reranker_model_name,
            self.settings.reranker_allow_downloads,
        )
        if (
            RerankerService._local_model_key == current_key
            and (RerankerService._local_model is not None or RerankerService._local_model_error is not None)
        ):
            return RerankerService._local_model

        with RerankerService._lock:
            if (
                RerankerService._local_model_key == current_key
                and (RerankerService._local_model is not None or RerankerService._local_model_error is not None)
            ):
                return RerankerService._local_model

            RerankerService._local_model = None
            RerankerService._local_model_error = None
            RerankerService._local_model_key = current_key

            if not self.settings.reranker_model_name:
                RerankerService._local_model_error = RuntimeError("Reranker model name is empty.")
                return None

            try:
                RerankerService._local_model = CrossEncoder(
                    self.settings.reranker_model_name,
                    local_files_only=not self.settings.reranker_allow_downloads,
                )
            except Exception as exc:  # pragma: no cover - depends on host model availability
                RerankerService._local_model_error = exc
            return RerankerService._local_model

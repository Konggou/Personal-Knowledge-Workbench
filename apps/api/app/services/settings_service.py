from __future__ import annotations

from fastapi import HTTPException

import app.core.settings as settings_module
from app.core.database import get_connection
from app.core.settings import MODEL_SETTING_KEYS
from app.schemas.settings import ModelSettingsResponse, ModelSettingsUpdateRequest


class SettingsService:
    def get_model_settings(self) -> ModelSettingsResponse:
        settings = settings_module.get_settings()
        return ModelSettingsResponse(
            llm={
                "base_url": settings.llm_base_url,
                "model": settings.llm_model,
                "timeout_seconds": settings.llm_timeout_seconds,
                "has_api_key": bool(settings.llm_api_key),
                "api_key_preview": self._mask_secret(settings.llm_api_key),
            },
            embedding={
                "model_name": settings.embedding_model_name,
                "dimension": settings.embedding_dimension,
                "allow_downloads": settings.embedding_allow_downloads,
            },
            reranker={
                "backend": settings.reranker_backend,
                "model_name": settings.reranker_model_name,
                "remote_url": settings.reranker_remote_url,
                "remote_timeout_seconds": settings.reranker_remote_timeout_seconds,
                "top_n": settings.reranker_top_n,
                "allow_downloads": settings.reranker_allow_downloads,
            },
        )

    def update_model_settings(self, payload: ModelSettingsUpdateRequest) -> ModelSettingsResponse:
        if payload.reranker.backend == "cross_encoder_remote" and not payload.reranker.remote_url.strip():
            raise HTTPException(status_code=422, detail="Remote reranker backend requires a remote URL.")

        updates = {
            MODEL_SETTING_KEYS["WORKBENCH_LLM_BASE_URL"]: payload.llm.base_url.strip(),
            MODEL_SETTING_KEYS["WORKBENCH_LLM_MODEL"]: payload.llm.model.strip(),
            MODEL_SETTING_KEYS["WORKBENCH_LLM_TIMEOUT_SECONDS"]: str(payload.llm.timeout_seconds),
            MODEL_SETTING_KEYS["WORKBENCH_EMBEDDING_MODEL"]: payload.embedding.model_name.strip(),
            MODEL_SETTING_KEYS["WORKBENCH_EMBEDDING_DIMENSION"]: str(payload.embedding.dimension),
            MODEL_SETTING_KEYS["WORKBENCH_EMBEDDING_ALLOW_DOWNLOADS"]: str(payload.embedding.allow_downloads).lower(),
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_BACKEND"]: payload.reranker.backend,
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_MODEL"]: payload.reranker.model_name.strip(),
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_ALLOW_DOWNLOADS"]: str(payload.reranker.allow_downloads).lower(),
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_REMOTE_URL"]: payload.reranker.remote_url.strip(),
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_REMOTE_TIMEOUT_SECONDS"]: str(payload.reranker.remote_timeout_seconds),
            MODEL_SETTING_KEYS["WORKBENCH_RERANKER_TOP_N"]: str(payload.reranker.top_n),
        }

        if payload.llm.clear_api_key:
            updates[MODEL_SETTING_KEYS["WORKBENCH_LLM_API_KEY"]] = ""
        elif payload.llm.api_key is not None and payload.llm.api_key.strip():
            updates[MODEL_SETTING_KEYS["WORKBENCH_LLM_API_KEY"]] = payload.llm.api_key.strip()

        connection = get_connection()
        try:
            for key, value in updates.items():
                if value is None:
                    connection.execute("DELETE FROM _app_metadata WHERE key = ?", (key,))
                    continue
                connection.execute(
                    """
                    INSERT INTO _app_metadata (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
            connection.commit()
        finally:
            connection.close()

        return self.get_model_settings()

    def _mask_secret(self, value: str) -> str | None:
        if not value:
            return None
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:3]}{'*' * (len(value) - 6)}{value[-3:]}"

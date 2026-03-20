from pathlib import Path

from fastapi.testclient import TestClient

import app.core.database as database_module
import app.core.settings as settings_module
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    sqlite_path = data_dir / "state.db"
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WORKBENCH_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("WORKBENCH_QDRANT_URL", ":memory:")
    monkeypatch.setenv("WORKBENCH_LLM_API_KEY", "env-secret-key")
    monkeypatch.setenv("WORKBENCH_LLM_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("WORKBENCH_LLM_MODEL", "env-chat")
    monkeypatch.setenv("WORKBENCH_LLM_TIMEOUT_SECONDS", "33")
    monkeypatch.setenv("WORKBENCH_EMBEDDING_MODEL", "env-embedding")
    monkeypatch.setenv("WORKBENCH_EMBEDDING_DIMENSION", "512")
    monkeypatch.setenv("WORKBENCH_EMBEDDING_ALLOW_DOWNLOADS", "false")
    monkeypatch.setenv("WORKBENCH_RERANKER_BACKEND", "rule")
    monkeypatch.setenv("WORKBENCH_RERANKER_MODEL", "env-reranker")
    monkeypatch.setenv("WORKBENCH_RERANKER_ALLOW_DOWNLOADS", "false")
    monkeypatch.setenv("WORKBENCH_RERANKER_REMOTE_URL", "")
    monkeypatch.setenv("WORKBENCH_RERANKER_REMOTE_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("WORKBENCH_RERANKER_TOP_N", "8")
    database_module.initialize_database()
    return sqlite_path


def test_get_model_settings_falls_back_to_environment(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/v1/settings/models")

    assert response.status_code == 200, response.text
    item = response.json()["item"]
    assert item["llm"]["base_url"] == "https://env.example.com"
    assert item["llm"]["model"] == "env-chat"
    assert item["llm"]["timeout_seconds"] == 33.0
    assert item["llm"]["has_api_key"] is True
    assert item["llm"]["api_key_preview"] != "env-secret-key"
    assert item["embedding"]["model_name"] == "env-embedding"
    assert item["embedding"]["dimension"] == 512
    assert item["reranker"]["backend"] == "rule"


def test_put_model_settings_persists_and_overrides_runtime(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    payload = {
        "llm": {
            "base_url": "https://sqlite.example.com",
            "model": "sqlite-chat",
            "timeout_seconds": 55,
            "api_key": "sqlite-secret-key",
            "clear_api_key": False,
        },
        "embedding": {
            "model_name": "sqlite-embedding",
            "dimension": 768,
            "allow_downloads": True,
        },
        "reranker": {
            "backend": "cross_encoder_remote",
            "model_name": "sqlite-reranker",
            "remote_url": "https://reranker.example.com",
            "remote_timeout_seconds": 12,
            "top_n": 5,
            "allow_downloads": True,
        },
    }

    with TestClient(app) as client:
        update_response = client.put("/api/v1/settings/models", json=payload)
        assert update_response.status_code == 200, update_response.text

        get_response = client.get("/api/v1/settings/models")
        assert get_response.status_code == 200, get_response.text

    item = get_response.json()["item"]
    assert item["llm"]["base_url"] == "https://sqlite.example.com"
    assert item["llm"]["model"] == "sqlite-chat"
    assert item["llm"]["has_api_key"] is True
    assert item["llm"]["api_key_preview"] != "sqlite-secret-key"
    assert item["embedding"]["model_name"] == "sqlite-embedding"
    assert item["embedding"]["dimension"] == 768
    assert item["embedding"]["allow_downloads"] is True
    assert item["reranker"]["backend"] == "cross_encoder_remote"
    assert item["reranker"]["remote_url"] == "https://reranker.example.com"
    assert settings_module.get_settings().llm_model == "sqlite-chat"
    assert settings_module.get_settings().embedding_dimension == 768
    assert settings_module.get_settings().reranker_backend == "cross_encoder_remote"


def test_put_model_settings_can_clear_api_key(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.put(
            "/api/v1/settings/models",
            json={
                "llm": {
                    "base_url": "https://sqlite.example.com",
                    "model": "sqlite-chat",
                    "timeout_seconds": 55,
                    "api_key": "sqlite-secret-key",
                    "clear_api_key": False,
                },
                "embedding": {
                    "model_name": "sqlite-embedding",
                    "dimension": 768,
                    "allow_downloads": True,
                },
                "reranker": {
                    "backend": "rule",
                    "model_name": "sqlite-reranker",
                    "remote_url": "",
                    "remote_timeout_seconds": 12,
                    "top_n": 5,
                    "allow_downloads": False,
                },
            },
        )

        clear_response = client.put(
            "/api/v1/settings/models",
            json={
                "llm": {
                    "base_url": "https://sqlite.example.com",
                    "model": "sqlite-chat",
                    "timeout_seconds": 55,
                    "api_key": None,
                    "clear_api_key": True,
                },
                "embedding": {
                    "model_name": "sqlite-embedding",
                    "dimension": 768,
                    "allow_downloads": True,
                },
                "reranker": {
                    "backend": "rule",
                    "model_name": "sqlite-reranker",
                    "remote_url": "",
                    "remote_timeout_seconds": 12,
                    "top_n": 5,
                    "allow_downloads": False,
                },
            },
        )

    assert clear_response.status_code == 200, clear_response.text
    item = clear_response.json()["item"]
    assert item["llm"]["has_api_key"] is False
    assert item["llm"]["api_key_preview"] is None


def test_put_model_settings_rejects_remote_backend_without_url(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/models",
            json={
                "llm": {
                    "base_url": "https://sqlite.example.com",
                    "model": "sqlite-chat",
                    "timeout_seconds": 55,
                    "api_key": None,
                    "clear_api_key": False,
                },
                "embedding": {
                    "model_name": "sqlite-embedding",
                    "dimension": 768,
                    "allow_downloads": True,
                },
                "reranker": {
                    "backend": "cross_encoder_remote",
                    "model_name": "sqlite-reranker",
                    "remote_url": "",
                    "remote_timeout_seconds": 12,
                    "top_n": 5,
                    "allow_downloads": False,
                },
            },
        )

    assert response.status_code == 422, response.text


def test_put_model_settings_rejects_invalid_numeric_values(monkeypatch, tmp_path):
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.put(
            "/api/v1/settings/models",
            json={
                "llm": {
                    "base_url": "https://sqlite.example.com",
                    "model": "sqlite-chat",
                    "timeout_seconds": 0,
                    "api_key": None,
                    "clear_api_key": False,
                },
                "embedding": {
                    "model_name": "sqlite-embedding",
                    "dimension": 0,
                    "allow_downloads": True,
                },
                "reranker": {
                    "backend": "rule",
                    "model_name": "sqlite-reranker",
                    "remote_url": "",
                    "remote_timeout_seconds": 12,
                    "top_n": 0,
                    "allow_downloads": False,
                },
            },
        )

    assert response.status_code == 422, response.text

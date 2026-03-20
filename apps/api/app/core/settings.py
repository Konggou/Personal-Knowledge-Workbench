import os
import sqlite3
from pathlib import Path

from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[4]

MODEL_SETTING_KEYS = {
    "WORKBENCH_LLM_API_KEY": "settings.llm.api_key",
    "WORKBENCH_LLM_BASE_URL": "settings.llm.base_url",
    "WORKBENCH_LLM_MODEL": "settings.llm.model",
    "WORKBENCH_LLM_TIMEOUT_SECONDS": "settings.llm.timeout_seconds",
    "WORKBENCH_EMBEDDING_MODEL": "settings.embedding.model_name",
    "WORKBENCH_EMBEDDING_DIMENSION": "settings.embedding.dimension",
    "WORKBENCH_EMBEDDING_ALLOW_DOWNLOADS": "settings.embedding.allow_downloads",
    "WORKBENCH_RERANKER_BACKEND": "settings.reranker.backend",
    "WORKBENCH_RERANKER_MODEL": "settings.reranker.model_name",
    "WORKBENCH_RERANKER_ALLOW_DOWNLOADS": "settings.reranker.allow_downloads",
    "WORKBENCH_RERANKER_REMOTE_URL": "settings.reranker.remote_url",
    "WORKBENCH_RERANKER_REMOTE_TIMEOUT_SECONDS": "settings.reranker.remote_timeout_seconds",
    "WORKBENCH_RERANKER_TOP_N": "settings.reranker.top_n",
}


def _load_file_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for candidate in (
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / ".env",
        ROOT_DIR / ".env.local",
        ROOT_DIR / ".env",
    ):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def _base_env() -> dict[str, str]:
    file_env = _load_file_env()
    merged = dict(file_env)
    merged.update({key: value for key, value in os.environ.items() if value is not None})
    return merged


def _load_sqlite_model_settings(sqlite_path: Path) -> dict[str, str]:
    if not sqlite_path.exists():
        return {}

    try:
        connection = sqlite3.connect(sqlite_path)
        rows = connection.execute(
            """
            SELECT key, value
            FROM _app_metadata
            WHERE key LIKE 'settings.%'
            """
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        try:
            connection.close()
        except Exception:
            pass

    return {str(key): str(value) for key, value in rows}


def _setting(name: str, default, *, env: dict[str, str], sqlite_values: dict[str, str]):
    sqlite_key = MODEL_SETTING_KEYS.get(name)
    if sqlite_key and sqlite_key in sqlite_values:
        return sqlite_values[sqlite_key]
    if name in env:
        return env[name]
    return default


class Settings(BaseModel):
    app_name: str = "Personal Knowledge Workbench API"
    api_prefix: str = "/api/v1"
    root_dir: Path = ROOT_DIR
    project_root: Path = PROJECT_ROOT
    data_dir: Path = ROOT_DIR / "data"
    sqlite_path: Path = ROOT_DIR / "data" / "state.db"
    qdrant_url: str = "embedded"
    qdrant_collection: str = "knowledge_chunks_v1"
    qdrant_local_path: Path = ROOT_DIR / "data" / "qdrant-local"
    qdrant_allow_embedded_fallback: bool = True
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_allow_downloads: bool = False
    retrieval_fts_version: str = "v4_rrf_ce"
    retrieval_lexical_candidate_limit: int = 8
    retrieval_semantic_candidate_limit: int = 8
    retrieval_rrf_k: int = 30
    retrieval_second_pass_limit: int = 4
    reranker_backend: str = "cross_encoder_local"
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_allow_downloads: bool = False
    reranker_remote_url: str = ""
    reranker_remote_timeout_seconds: float = 20.0
    reranker_top_n: int = 4
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 45.0
    llm_grounded_factoid_max_tokens: int = 96
    llm_grounded_default_max_tokens: int = 220
    llm_grounded_research_max_tokens: int = 360
    agent_web_result_limit: int = 3
    agent_web_fetch_limit: int = 2


def get_settings() -> Settings:
    env = _base_env()
    data_dir = Path(env.get("WORKBENCH_DATA_DIR", str(ROOT_DIR / "data")))
    sqlite_path = Path(env.get("WORKBENCH_SQLITE_PATH", str(data_dir / "state.db")))
    sqlite_values = _load_sqlite_model_settings(sqlite_path)

    return Settings(
        app_name="Personal Knowledge Workbench API",
        api_prefix="/api/v1",
        root_dir=ROOT_DIR,
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        sqlite_path=sqlite_path,
        qdrant_url=str(_setting("WORKBENCH_QDRANT_URL", "embedded", env=env, sqlite_values=sqlite_values)),
        qdrant_collection="knowledge_chunks_v1",
        qdrant_local_path=Path(env.get("WORKBENCH_QDRANT_LOCAL_PATH", str(data_dir / "qdrant-local"))),
        qdrant_allow_embedded_fallback=str(
            _setting("WORKBENCH_QDRANT_ALLOW_EMBEDDED_FALLBACK", "true", env=env, sqlite_values=sqlite_values)
        ).lower()
        == "true",
        embedding_model_name=str(
            _setting(
                "WORKBENCH_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
                env=env,
                sqlite_values=sqlite_values,
            )
        ),
        embedding_dimension=int(_setting("WORKBENCH_EMBEDDING_DIMENSION", "384", env=env, sqlite_values=sqlite_values)),
        embedding_allow_downloads=str(
            _setting("WORKBENCH_EMBEDDING_ALLOW_DOWNLOADS", "false", env=env, sqlite_values=sqlite_values)
        ).lower()
        == "true",
        retrieval_fts_version=str(_setting("WORKBENCH_RETRIEVAL_FTS_VERSION", "v4_rrf_ce", env=env, sqlite_values={})),
        retrieval_lexical_candidate_limit=int(
            _setting("WORKBENCH_RETRIEVAL_LEXICAL_CANDIDATE_LIMIT", "8", env=env, sqlite_values={})
        ),
        retrieval_semantic_candidate_limit=int(
            _setting("WORKBENCH_RETRIEVAL_SEMANTIC_CANDIDATE_LIMIT", "8", env=env, sqlite_values={})
        ),
        retrieval_rrf_k=int(_setting("WORKBENCH_RETRIEVAL_RRF_K", "30", env=env, sqlite_values={})),
        retrieval_second_pass_limit=int(
            _setting("WORKBENCH_RETRIEVAL_SECOND_PASS_LIMIT", "4", env=env, sqlite_values={})
        ),
        reranker_backend=str(
            _setting("WORKBENCH_RERANKER_BACKEND", "cross_encoder_local", env=env, sqlite_values=sqlite_values)
        ),
        reranker_model_name=str(
            _setting(
                "WORKBENCH_RERANKER_MODEL",
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                env=env,
                sqlite_values=sqlite_values,
            )
        ),
        reranker_allow_downloads=str(
            _setting("WORKBENCH_RERANKER_ALLOW_DOWNLOADS", "false", env=env, sqlite_values=sqlite_values)
        ).lower()
        == "true",
        reranker_remote_url=str(
            _setting("WORKBENCH_RERANKER_REMOTE_URL", "", env=env, sqlite_values=sqlite_values)
        ),
        reranker_remote_timeout_seconds=float(
            _setting("WORKBENCH_RERANKER_REMOTE_TIMEOUT_SECONDS", "20", env=env, sqlite_values=sqlite_values)
        ),
        reranker_top_n=int(_setting("WORKBENCH_RERANKER_TOP_N", "4", env=env, sqlite_values=sqlite_values)),
        llm_api_key=str(
            _setting(
                "WORKBENCH_LLM_API_KEY",
                env.get("DEEPSEEK_API_KEY", ""),
                env=env,
                sqlite_values=sqlite_values,
            )
        ),
        llm_base_url=str(
            _setting("WORKBENCH_LLM_BASE_URL", "https://api.deepseek.com", env=env, sqlite_values=sqlite_values)
        ),
        llm_model=str(_setting("WORKBENCH_LLM_MODEL", "deepseek-chat", env=env, sqlite_values=sqlite_values)),
        llm_timeout_seconds=float(
            _setting("WORKBENCH_LLM_TIMEOUT_SECONDS", "45", env=env, sqlite_values=sqlite_values)
        ),
        llm_grounded_factoid_max_tokens=int(
            _setting("WORKBENCH_LLM_GROUNDED_FACTOID_MAX_TOKENS", "96", env=env, sqlite_values={})
        ),
        llm_grounded_default_max_tokens=int(
            _setting("WORKBENCH_LLM_GROUNDED_DEFAULT_MAX_TOKENS", "220", env=env, sqlite_values={})
        ),
        llm_grounded_research_max_tokens=int(
            _setting("WORKBENCH_LLM_GROUNDED_RESEARCH_MAX_TOKENS", "360", env=env, sqlite_values={})
        ),
        agent_web_result_limit=int(_setting("WORKBENCH_AGENT_WEB_RESULT_LIMIT", "3", env=env, sqlite_values={})),
        agent_web_fetch_limit=int(_setting("WORKBENCH_AGENT_WEB_FETCH_LIMIT", "2", env=env, sqlite_values={})),
    )

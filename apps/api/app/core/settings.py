import os
from pathlib import Path

from pydantic import BaseModel


ROOT_DIR = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[4]


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


def _setting(name: str, default):
    file_env = _load_file_env()
    return os.getenv(name, file_env.get(name, default))


class Settings(BaseModel):
    app_name: str = "Personal Knowledge Workbench API"
    api_prefix: str = "/api/v1"
    root_dir: Path = ROOT_DIR
    data_dir: Path = Path(_setting("WORKBENCH_DATA_DIR", ROOT_DIR / "data"))
    sqlite_path: Path = Path(_setting("WORKBENCH_SQLITE_PATH", data_dir / "state.db"))
    qdrant_url: str = _setting("WORKBENCH_QDRANT_URL", "embedded")
    qdrant_collection: str = "knowledge_chunks_v1"
    qdrant_local_path: Path = Path(_setting("WORKBENCH_QDRANT_LOCAL_PATH", data_dir / "qdrant-local"))
    qdrant_allow_embedded_fallback: bool = (
        str(_setting("WORKBENCH_QDRANT_ALLOW_EMBEDDED_FALLBACK", "true")).lower() == "true"
    )
    embedding_model_name: str = _setting("WORKBENCH_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: int = int(_setting("WORKBENCH_EMBEDDING_DIMENSION", "384"))
    embedding_allow_downloads: bool = str(_setting("WORKBENCH_EMBEDDING_ALLOW_DOWNLOADS", "false")).lower() == "true"
    llm_api_key: str = _setting("WORKBENCH_LLM_API_KEY", _setting("DEEPSEEK_API_KEY", ""))
    llm_base_url: str = _setting("WORKBENCH_LLM_BASE_URL", "https://api.deepseek.com")
    llm_model: str = _setting("WORKBENCH_LLM_MODEL", "deepseek-chat")
    llm_timeout_seconds: float = float(_setting("WORKBENCH_LLM_TIMEOUT_SECONDS", "45"))


def get_settings() -> Settings:
    return Settings()

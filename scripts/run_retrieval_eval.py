from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local retrieval evaluation suite and print JSON results.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write the JSON result payload.")
    args = parser.parse_args()

    with TemporaryDirectory(prefix="workbench-retrieval-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        os.environ["WORKBENCH_DATA_DIR"] = str(temp_path / "data")
        os.environ["WORKBENCH_SQLITE_PATH"] = str(temp_path / "data" / "state.db")
        os.environ["WORKBENCH_QDRANT_URL"] = ":memory:"
        os.environ["WORKBENCH_EMBEDDING_MODEL"] = ""

        import app.core.database as database_module
        import app.core.settings as settings_module
        from app.main import app
        from app.services.retrieval_eval_service import run_retrieval_eval

        database_module.initialize_database()
        with patch("app.services.vector_store.VectorStore.search", lambda self, *, query, project_id, limit: []):
            with TestClient(app) as client:
                result = run_retrieval_eval(client)

        payload = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload)

        original_get_settings = settings_module.get_settings
        if hasattr(original_get_settings, "cache_clear"):
            original_get_settings.cache_clear()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

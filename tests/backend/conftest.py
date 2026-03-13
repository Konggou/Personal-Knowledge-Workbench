import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.core.settings import Settings  # noqa: E402
import app.core.settings as settings_module  # noqa: E402
import app.core.database as database_module  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    sqlite_path = data_dir / "state.db"
    settings = Settings(
        root_dir=ROOT_DIR,
        data_dir=data_dir,
        sqlite_path=sqlite_path,
        api_prefix="/api/v1",
        qdrant_url=":memory:",
        qdrant_collection="knowledge_chunks_v1",
        embedding_model_name="",
    )

    original_get_settings = settings_module.get_settings
    if hasattr(original_get_settings, "cache_clear"):
        original_get_settings.cache_clear()
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(database_module, "get_settings", lambda: settings)
    database_module.initialize_database()

    with TestClient(app) as test_client:
        yield test_client

    if hasattr(original_get_settings, "cache_clear"):
        original_get_settings.cache_clear()


@pytest.fixture()
def html_server(tmp_path):
    server_root = tmp_path / "html"
    server_root.mkdir(parents=True, exist_ok=True)

    handler = partial(SimpleHTTPRequestHandler, directory=str(server_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield {
        "root": server_root,
        "base_url": f"http://127.0.0.1:{server.server_port}",
    }

    server.shutdown()
    server.server_close()
    thread.join(timeout=1)

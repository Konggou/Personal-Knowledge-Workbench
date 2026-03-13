import shutil
import sqlite3
from pathlib import Path

from app.core.settings import get_settings

SCHEMA_VERSION = "chat_first_grounded_v1"


def _load_schema(schema_path: Path) -> str:
    return schema_path.read_text(encoding="utf-8")


def _read_existing_version(sqlite_path: Path) -> str | None:
    if not sqlite_path.exists():
        return None

    connection = sqlite3.connect(sqlite_path)
    try:
        row = connection.execute(
            """
            SELECT value
            FROM _app_metadata
            WHERE key = 'schema_version'
            """,
        ).fetchone()
        if row is None:
            return None
        return str(row[0])
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _reset_local_state(sqlite_path: Path, qdrant_local_path: Path) -> None:
    if sqlite_path.exists():
        sqlite_path.unlink()
    if qdrant_local_path.exists():
        shutil.rmtree(qdrant_local_path, ignore_errors=True)


def initialize_database() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    existing_version = _read_existing_version(settings.sqlite_path)
    if existing_version != SCHEMA_VERSION:
        _reset_local_state(settings.sqlite_path, settings.qdrant_local_path)

    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    schema_sql = _load_schema(schema_path)

    connection = sqlite3.connect(settings.sqlite_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(schema_sql)
        connection.execute(
            """
            INSERT INTO _app_metadata (key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SCHEMA_VERSION,),
        )
        connection.commit()
    finally:
        connection.close()


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    connection = sqlite3.connect(settings.sqlite_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.row_factory = sqlite3.Row
    return connection

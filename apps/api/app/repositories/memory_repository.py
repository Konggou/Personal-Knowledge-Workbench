from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.database import get_connection


@dataclass
class MemoryEntryRecord:
    id: str
    scope_type: str
    scope_id: str
    topic: str
    fact_text: str
    salience: float
    source_message_id: str | None
    created_at: str
    updated_at: str
    last_used_at: str | None

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "topic": self.topic,
            "fact_text": self.fact_text,
            "salience": float(self.salience),
            "source_message_id": self.source_message_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used_at": self.last_used_at,
        }


class MemoryRepository:
    def list_scope_entries(self, *, scope_type: str, scope_id: str) -> list[MemoryEntryRecord]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                  id,
                  scope_type,
                  scope_id,
                  topic,
                  fact_text,
                  salience,
                  source_message_id,
                  created_at,
                  updated_at,
                  last_used_at
                FROM memory_entries
                WHERE scope_type = ?
                  AND scope_id = ?
                ORDER BY salience DESC, updated_at DESC
                """,
                (scope_type, scope_id),
            ).fetchall()
            return [MemoryEntryRecord(**dict(row)) for row in rows]
        finally:
            connection.close()

    def upsert_entry(
        self,
        *,
        scope_type: str,
        scope_id: str,
        topic: str,
        fact_text: str,
        salience: float,
        source_message_id: str | None,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            existing = connection.execute(
                """
                SELECT id, salience
                FROM memory_entries
                WHERE scope_type = ?
                  AND scope_id = ?
                  AND topic = ?
                  AND fact_text = ?
                """,
                (scope_type, scope_id, topic, fact_text),
            ).fetchone()
            if existing is None:
                entry_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO memory_entries (
                      id,
                      scope_type,
                      scope_id,
                      topic,
                      fact_text,
                      salience,
                      source_message_id,
                      created_at,
                      updated_at,
                      last_used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        scope_type,
                        scope_id,
                        topic,
                        fact_text,
                        float(salience),
                        source_message_id,
                        now,
                        now,
                        now,
                    ),
                )
            else:
                entry_id = str(existing["id"])
                merged_salience = max(float(existing["salience"]), float(salience))
                connection.execute(
                    """
                    UPDATE memory_entries
                    SET salience = ?, source_message_id = ?, updated_at = ?, last_used_at = ?
                    WHERE id = ?
                    """,
                    (merged_salience, source_message_id, now, now, entry_id),
                )
            connection.commit()
        finally:
            connection.close()
        return self.get_entry(entry_id)

    def get_entry(self, entry_id: str) -> dict:
        connection = get_connection()
        try:
            row = connection.execute(
                """
                SELECT
                  id,
                  scope_type,
                  scope_id,
                  topic,
                  fact_text,
                  salience,
                  source_message_id,
                  created_at,
                  updated_at,
                  last_used_at
                FROM memory_entries
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Memory entry not found after upsert: {entry_id}")
            return MemoryEntryRecord(**dict(row)).to_summary()
        finally:
            connection.close()

    def touch_entries(self, entry_ids: list[str]) -> None:
        if not entry_ids:
            return
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            placeholders = ", ".join("?" for _ in entry_ids)
            connection.execute(
                f"""
                UPDATE memory_entries
                SET last_used_at = ?, updated_at = ?
                WHERE id IN ({placeholders})
                """,
                (now, now, *entry_ids),
            )
            connection.commit()
        finally:
            connection.close()

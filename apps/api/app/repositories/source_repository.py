from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

from app.core.database import get_connection


@dataclass
class SourceRecord:
    id: str
    project_id: str
    project_name: str
    source_type: str
    title: str
    canonical_uri: str
    original_filename: str | None
    mime_type: str | None
    content_hash: str | None
    ingestion_status: str
    quality_level: str
    refresh_strategy: str
    last_refreshed_at: str | None
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    archived_at: str | None
    deleted_at: str | None

    def to_summary(self) -> dict:
        host = urlparse(self.canonical_uri).netloc if self.source_type == "web_page" else None
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "source_type": self.source_type,
            "title": self.title,
            "canonical_uri": self.canonical_uri,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "ingestion_status": self.ingestion_status,
            "quality_level": self.quality_level,
            "refresh_strategy": self.refresh_strategy,
            "last_refreshed_at": self.last_refreshed_at,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "deleted_at": self.deleted_at,
            "favicon_url": f"https://www.google.com/s2/favicons?sz=64&domain={host}" if host else None,
        }


@dataclass
class SourcePreviewChunkRecord:
    id: str
    section_label: str
    section_type: str
    heading_path: str | None
    field_label: str | None
    table_origin: str | None
    proposition_type: str | None
    chunk_index: int
    excerpt: str
    normalized_text: str
    char_count: int

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "location_label": f"{self.section_label} #{self.chunk_index + 1}",
            "section_type": self.section_type,
            "heading_path": self.heading_path,
            "field_label": self.field_label,
            "table_origin": self.table_origin,
            "proposition_type": self.proposition_type,
            "excerpt": self.excerpt,
            "normalized_text": self.normalized_text,
            "char_count": self.char_count,
        }


class SourceRepository:
    def _touch_project_activity(self, *, connection, project_id: str, timestamp: str) -> None:
        connection.execute(
            """
            UPDATE projects
            SET last_activity_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, project_id),
        )

    def _advance_project_snapshot(self, *, connection, project_id: str, reason: str) -> str:
        created_at = datetime.now(UTC).isoformat()
        snapshot_id = str(uuid4())
        snapshot_row = connection.execute(
            "SELECT COALESCE(MAX(snapshot_number), 0) AS max_number FROM project_snapshots WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        snapshot_number = int(snapshot_row["max_number"]) + 1

        source_count_row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM sources
            WHERE project_id = ?
              AND deleted_at IS NULL
              AND ingestion_status != 'archived'
            """,
            (project_id,),
        ).fetchone()
        indexed_count_row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM sources
            WHERE project_id = ?
              AND deleted_at IS NULL
              AND ingestion_status IN ('ready', 'ready_low_quality')
            """,
            (project_id,),
        ).fetchone()
        low_quality_row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM sources
            WHERE project_id = ?
              AND deleted_at IS NULL
              AND ingestion_status != 'archived'
              AND quality_level = 'low'
            """,
            (project_id,),
        ).fetchone()

        connection.execute(
            """
            INSERT INTO project_snapshots (
              id, project_id, snapshot_number, reason, status,
              source_count, indexed_source_count, low_quality_source_count, created_at
            ) VALUES (?, ?, ?, ?, 'ready', ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                project_id,
                snapshot_number,
                reason,
                int(source_count_row["total"]),
                int(indexed_count_row["total"]),
                int(low_quality_row["total"]),
                created_at,
            ),
        )
        connection.execute(
            """
            UPDATE projects
            SET current_snapshot_id = ?, updated_at = ?, last_activity_at = ?
            WHERE id = ?
            """,
            (snapshot_id, created_at, created_at, project_id),
        )
        return snapshot_id

    def project_exists(self, project_id: str) -> bool:
        connection = get_connection()
        try:
            row = connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
            return row is not None
        finally:
            connection.close()

    def list_sources(self, project_id: str, *, include_archived: bool = False) -> list[SourceRecord]:
        connection = get_connection()
        try:
            sql = """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.source_type,
                  s.title,
                  s.canonical_uri,
                  s.original_filename,
                  s.mime_type,
                  s.content_hash,
                  s.ingestion_status,
                  s.quality_level,
                  s.refresh_strategy,
                  s.last_refreshed_at,
                  s.error_code,
                  s.error_message,
                  s.created_at,
                  s.updated_at,
                  s.archived_at,
                  s.deleted_at
                FROM sources s
                JOIN projects p ON p.id = s.project_id
                WHERE s.project_id = ?
                  AND s.deleted_at IS NULL
            """
            if not include_archived:
                sql += " AND s.ingestion_status != 'archived'"
            sql += " ORDER BY s.updated_at DESC"
            rows = connection.execute(sql, (project_id,)).fetchall()
            return [SourceRecord(**dict(row)) for row in rows]
        finally:
            connection.close()

    def list_all_sources(self, *, project_id: str | None = None, include_archived: bool = False) -> list[SourceRecord]:
        connection = get_connection()
        try:
            sql = """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.source_type,
                  s.title,
                  s.canonical_uri,
                  s.original_filename,
                  s.mime_type,
                  s.content_hash,
                  s.ingestion_status,
                  s.quality_level,
                  s.refresh_strategy,
                  s.last_refreshed_at,
                  s.error_code,
                  s.error_message,
                  s.created_at,
                  s.updated_at,
                  s.archived_at,
                  s.deleted_at
                FROM sources s
                JOIN projects p ON p.id = s.project_id
                WHERE s.deleted_at IS NULL
            """
            params: list[object] = []
            if project_id is not None:
                sql += " AND s.project_id = ?"
                params.append(project_id)
            if not include_archived:
                sql += " AND s.ingestion_status != 'archived'"
            sql += " ORDER BY p.last_activity_at DESC, s.updated_at DESC"
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [SourceRecord(**dict(row)) for row in rows]
        finally:
            connection.close()

    def get_source(self, source_id: str) -> SourceRecord | None:
        connection = get_connection()
        try:
            row = connection.execute(
                """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.source_type,
                  s.title,
                  s.canonical_uri,
                  s.original_filename,
                  s.mime_type,
                  s.content_hash,
                  s.ingestion_status,
                  s.quality_level,
                  s.refresh_strategy,
                  s.last_refreshed_at,
                  s.error_code,
                  s.error_message,
                  s.created_at,
                  s.updated_at,
                  s.archived_at,
                  s.deleted_at
                FROM sources s
                JOIN projects p ON p.id = s.project_id
                WHERE s.id = ?
                """,
                (source_id,),
            ).fetchone()
            if row is None:
                return None
            return SourceRecord(**dict(row))
        finally:
            connection.close()

    def get_source_preview_chunks(self, source_id: str, *, limit: int = 8) -> list[SourcePreviewChunkRecord]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  WHERE sc.source_id = ?
                  GROUP BY sc.source_id
                )
                SELECT
                  sc.id,
                  sc.section_label,
                  sc.section_type,
                  sc.heading_path,
                  sc.field_label,
                  sc.table_origin,
                  sc.proposition_type,
                  sc.chunk_index,
                  sc.excerpt,
                  sc.normalized_text,
                  sc.char_count
                FROM source_chunks sc
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot latest
                  ON latest.source_id = sc.source_id
                 AND latest.latest_snapshot_number = ps.snapshot_number
                WHERE sc.source_id = ?
                ORDER BY sc.chunk_index ASC
                LIMIT ?
                """,
                (source_id, source_id, limit),
            ).fetchall()
            return [SourcePreviewChunkRecord(**dict(row)) for row in rows]
        finally:
            connection.close()

    def get_latest_source_chunks_for_indexing(self, source_id: str) -> list[dict]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  WHERE sc.source_id = ?
                  GROUP BY sc.source_id
                )
                SELECT
                  sc.id AS chunk_id,
                  sc.source_id,
                  sc.project_id,
                  p.name AS project_name,
                  sc.snapshot_id,
                  sc.qdrant_point_id,
                  sc.section_label,
                  sc.section_type,
                  sc.heading_path,
                  sc.field_label,
                  sc.table_origin,
                  sc.proposition_type,
                  sc.chunk_index,
                  sc.normalized_text,
                  sc.excerpt,
                  s.title AS source_title,
                  s.source_type,
                  s.canonical_uri,
                  s.quality_level
                FROM source_chunks sc
                JOIN sources s ON s.id = sc.source_id
                JOIN projects p ON p.id = sc.project_id
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot latest
                  ON latest.source_id = sc.source_id
                 AND latest.latest_snapshot_number = ps.snapshot_number
                WHERE sc.source_id = ?
                ORDER BY sc.chunk_index ASC
                """,
                (source_id, source_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def create_web_source(self, project_id: str, url: str) -> SourceRecord:
        return self.create_source(
            project_id=project_id,
            source_type="web_page",
            title=url,
            canonical_uri=url,
            original_filename=None,
            mime_type="text/html",
            refresh_strategy="manual",
        )

    def create_file_source(
        self,
        *,
        project_id: str,
        source_type: str,
        title: str,
        canonical_uri: str,
        original_filename: str,
        mime_type: str,
    ) -> SourceRecord:
        return self.create_source(
            project_id=project_id,
            source_type=source_type,
            title=title,
            canonical_uri=canonical_uri,
            original_filename=original_filename,
            mime_type=mime_type,
            refresh_strategy="none",
        )

    def create_source(
        self,
        *,
        project_id: str,
        source_type: str,
        title: str,
        canonical_uri: str,
        original_filename: str | None,
        mime_type: str | None,
        refresh_strategy: str,
    ) -> SourceRecord:
        now = datetime.now(UTC).isoformat()
        source_id = str(uuid4())
        connection = get_connection()
        try:
            connection.execute(
                """
                INSERT INTO sources (
                  id, project_id, source_type, title, canonical_uri, original_filename, mime_type,
                  content_hash, ingestion_status, quality_level, refresh_strategy, last_refreshed_at,
                  error_code, error_message, created_at, updated_at, archived_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'processing', 'normal', ?, NULL, NULL, NULL, ?, ?, NULL, NULL)
                """,
                (
                    source_id,
                    project_id,
                    source_type,
                    title,
                    canonical_uri,
                    original_filename,
                    mime_type,
                    refresh_strategy,
                    now,
                    now,
                ),
            )
            self._touch_project_activity(connection=connection, project_id=project_id, timestamp=now)
            connection.commit()
        finally:
            connection.close()

        source = self.get_source(source_id)
        if source is None:
            raise RuntimeError("Source creation failed unexpectedly.")
        return source

    def mark_source_processing(self, source_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sources
                SET ingestion_status = 'processing',
                    error_code = NULL,
                    error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, source_id),
            )
            connection.commit()
        finally:
            connection.close()

    def complete_source_ingestion(
        self,
        *,
        source_id: str,
        project_id: str,
        title: str,
        quality_level: str,
        chunks: list[dict],
        reason: str = "source_ingested",
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            snapshot_id = self._advance_project_snapshot(connection=connection, project_id=project_id, reason=reason)
            for index, chunk in enumerate(chunks):
                chunk_id = str(uuid4())
                point_id = str(uuid4())
                normalized_text = chunk["normalized_text"]
                connection.execute(
                    """
                    INSERT INTO source_chunks (
                      id, source_id, project_id, snapshot_id, qdrant_point_id,
                      section_label, section_type, heading_path, field_label, table_origin, proposition_type,
                      chunk_index, token_count, char_count,
                      normalized_text, excerpt, retrieval_enabled, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        source_id,
                        project_id,
                        snapshot_id,
                        point_id,
                        chunk["section_label"],
                        chunk["section_type"],
                        chunk.get("heading_path"),
                        chunk.get("field_label"),
                        chunk.get("table_origin"),
                        chunk.get("proposition_type"),
                        index,
                        max(1, len(normalized_text) // 4),
                        len(normalized_text),
                        normalized_text,
                        chunk["excerpt"],
                        1,
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO source_chunk_fts (chunk_id, project_id, snapshot_id, title, normalized_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, project_id, snapshot_id, title, normalized_text),
                )

            status = "ready" if quality_level == "normal" else "ready_low_quality"
            connection.execute(
                """
                UPDATE sources
                SET title = ?,
                    ingestion_status = ?,
                    quality_level = ?,
                    last_refreshed_at = ?,
                    error_code = NULL,
                    error_message = NULL,
                    archived_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (title, status, quality_level, created_at, created_at, source_id),
            )
            self._touch_project_activity(connection=connection, project_id=project_id, timestamp=created_at)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finalize_source_failure(self, *, source_id: str, error_code: str, error_message: str) -> None:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            row = connection.execute("SELECT project_id FROM sources WHERE id = ?", (source_id,)).fetchone()
            connection.execute(
                """
                UPDATE sources
                SET ingestion_status = 'failed',
                    error_code = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (error_code, error_message, now, source_id),
            )
            if row is not None:
                self._touch_project_activity(connection=connection, project_id=row["project_id"], timestamp=now)
            connection.commit()
        finally:
            connection.close()

    def update_web_source_url(self, source_id: str, url: str) -> SourceRecord | None:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            row = connection.execute("SELECT project_id, source_type FROM sources WHERE id = ?", (source_id,)).fetchone()
            if row is None:
                return None
            if row["source_type"] != "web_page":
                raise ValueError("Only web sources can update their URL.")
            connection.execute(
                """
                UPDATE sources
                SET canonical_uri = ?, title = ?, updated_at = ?
                WHERE id = ?
                """,
                (url, url, now, source_id),
            )
            self._touch_project_activity(connection=connection, project_id=row["project_id"], timestamp=now)
            connection.commit()
        finally:
            connection.close()
        return self.get_source(source_id)

    def archive_source(self, source_id: str) -> SourceRecord | None:
        source = self.get_source(source_id)
        if source is None:
            return None
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sources
                SET ingestion_status = 'archived',
                    archived_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, source_id),
            )
            self._advance_project_snapshot(connection=connection, project_id=source.project_id, reason="source_archived")
            connection.commit()
        finally:
            connection.close()
        return self.get_source(source_id)

    def restore_source(self, source_id: str) -> SourceRecord | None:
        source = self.get_source(source_id)
        if source is None:
            return None
        if source.deleted_at is not None:
            return None
        if source.ingestion_status != "archived":
            return source
        now = datetime.now(UTC).isoformat()
        restored_status = "ready" if source.quality_level == "normal" else "ready_low_quality"
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sources
                SET ingestion_status = ?,
                    archived_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (restored_status, now, source_id),
            )
            self._advance_project_snapshot(connection=connection, project_id=source.project_id, reason="source_refreshed")
            connection.commit()
        finally:
            connection.close()
        return self.get_source(source_id)

    def delete_source(self, source_id: str) -> SourceRecord | None:
        source = self.get_source(source_id)
        if source is None:
            return None
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sources
                SET deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, source_id),
            )
            self._advance_project_snapshot(connection=connection, project_id=source.project_id, reason="source_deleted")
            connection.commit()
        finally:
            connection.close()
        return self.get_source(source_id)

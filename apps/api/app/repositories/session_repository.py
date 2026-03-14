from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.database import get_connection


@dataclass
class SessionRecord:
    id: str
    project_id: str
    project_name: str
    title: str | None
    title_source: str
    status: str
    latest_message_at: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None
    message_count: int

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "title": self.title or "新会话",
            "title_source": self.title_source,
            "status": self.status,
            "latest_message_at": self.latest_message_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted_at": self.deleted_at,
            "message_count": self.message_count,
        }


class SessionRepository:
    def _touch_project_activity(self, *, connection, project_id: str, timestamp: str) -> None:
        connection.execute(
            """
            UPDATE projects
            SET last_activity_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, project_id),
        )

    def _touch_session_activity(self, *, connection, session_id: str, timestamp: str) -> None:
        connection.execute(
            """
            UPDATE sessions
            SET latest_message_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, session_id),
        )

    def create_session(self, project_id: str) -> dict:
        now = datetime.now(UTC).isoformat()
        session_id = str(uuid4())
        connection = get_connection()
        try:
            connection.execute(
                """
                INSERT INTO sessions (
                  id, project_id, title, title_source, status, latest_message_at, created_at, updated_at, deleted_at
                )
                VALUES (?, ?, NULL, 'pending', 'active', NULL, ?, ?, NULL)
                """,
                (session_id, project_id, now, now),
            )
            self._touch_project_activity(connection=connection, project_id=project_id, timestamp=now)
            connection.commit()
        finally:
            connection.close()
        detail = self.get_session_detail(session_id)
        if detail is None:
            raise RuntimeError("Session creation failed unexpectedly.")
        return detail

    def list_project_sessions(self, project_id: str) -> list[dict]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.title,
                  s.title_source,
                  s.status,
                  s.latest_message_at,
                  s.created_at,
                  s.updated_at,
                  s.deleted_at,
                  (
                    SELECT COUNT(*)
                    FROM session_messages sm
                    WHERE sm.session_id = s.id
                      AND sm.deleted_at IS NULL
                  ) AS message_count
                FROM sessions s
                JOIN projects p ON p.id = s.project_id
                WHERE s.project_id = ?
                  AND s.deleted_at IS NULL
                ORDER BY COALESCE(s.latest_message_at, s.created_at) DESC, s.created_at DESC
                """,
                (project_id,),
            ).fetchall()
            return [SessionRecord(**dict(row)).to_summary() for row in rows]
        finally:
            connection.close()

    def list_all_sessions(self) -> list[dict]:
        connection = get_connection()
        try:
            rows = connection.execute(
                """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.title,
                  s.title_source,
                  s.status,
                  s.latest_message_at,
                  s.created_at,
                  s.updated_at,
                  s.deleted_at,
                  (
                    SELECT COUNT(*)
                    FROM session_messages sm
                    WHERE sm.session_id = s.id
                      AND sm.deleted_at IS NULL
                  ) AS message_count
                FROM sessions s
                JOIN projects p ON p.id = s.project_id
                WHERE s.deleted_at IS NULL
                ORDER BY p.last_activity_at DESC, COALESCE(s.latest_message_at, s.created_at) DESC
                """,
            ).fetchall()
            return [SessionRecord(**dict(row)).to_summary() for row in rows]
        finally:
            connection.close()

    def get_session_detail(self, session_id: str) -> dict | None:
        connection = get_connection()
        try:
            session_row = connection.execute(
                """
                SELECT
                  s.id,
                  s.project_id,
                  p.name AS project_name,
                  s.title,
                  s.title_source,
                  s.status,
                  s.latest_message_at,
                  s.created_at,
                  s.updated_at,
                  s.deleted_at,
                  (
                    SELECT COUNT(*)
                    FROM session_messages sm
                    WHERE sm.session_id = s.id
                      AND sm.deleted_at IS NULL
                  ) AS message_count
                FROM sessions s
                JOIN projects p ON p.id = s.project_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                return None

            message_rows = connection.execute(
                """
                SELECT
                  id,
                  session_id,
                  project_id,
                  seq_no,
                  role,
                  message_type,
                  title,
                  content_md,
                  source_mode,
                  evidence_status,
                  disclosure_note,
                  status_label,
                  supports_summary,
                  supports_report,
                  related_message_id,
                  created_at,
                  updated_at,
                  deleted_at
                FROM session_messages
                WHERE session_id = ?
                  AND deleted_at IS NULL
                ORDER BY seq_no ASC
                """,
                (session_id,),
            ).fetchall()

            messages: list[dict] = []
            for row in message_rows:
                message = {
                    **dict(row),
                    "supports_summary": bool(row["supports_summary"]),
                    "supports_report": bool(row["supports_report"]),
                    "sources": [],
                }
                source_rows = connection.execute(
                    """
                    SELECT
                      id,
                      source_id,
                      source_kind,
                      chunk_id,
                      source_rank,
                      source_type,
                      source_title,
                      canonical_uri,
                      external_uri,
                      location_label,
                      excerpt,
                      relevance_score
                    FROM message_sources
                    WHERE message_id = ?
                    ORDER BY source_rank ASC
                    """,
                    (row["id"],),
                ).fetchall()
                message["sources"] = [dict(source_row) for source_row in source_rows]
                messages.append(message)

            detail = SessionRecord(**dict(session_row)).to_summary()
            detail["messages"] = messages
            return detail
        finally:
            connection.close()

    def rename_session(self, session_id: str, title: str) -> dict | None:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, title_source = 'manual', updated_at = ?
                WHERE id = ?
                  AND deleted_at IS NULL
                """,
                (title, now, session_id),
            )
            connection.commit()
        finally:
            connection.close()
        return self.get_session_detail(session_id)

    def delete_session(self, session_id: str) -> dict | None:
        detail = self.get_session_detail(session_id)
        if detail is None:
            return None
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE sessions
                SET status = 'deleted', deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, session_id),
            )
            connection.execute(
                """
                UPDATE session_messages
                SET deleted_at = ?, updated_at = ?
                WHERE session_id = ?
                  AND deleted_at IS NULL
                """,
                (now, now, session_id),
            )
            self._touch_project_activity(connection=connection, project_id=detail["project_id"], timestamp=now)
            connection.commit()
        finally:
            connection.close()
        return self.get_session_detail(session_id)

    def create_message(
        self,
        *,
        session_id: str,
        project_id: str,
        role: str,
        message_type: str,
        content_md: str,
        title: str | None = None,
        source_mode: str | None = None,
        evidence_status: str | None = None,
        disclosure_note: str | None = None,
        status_label: str | None = None,
        supports_summary: bool = False,
        supports_report: bool = False,
        related_message_id: str | None = None,
        sources: list[dict] | None = None,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        message_id = str(uuid4())
        connection = get_connection()
        try:
            seq_row = connection.execute(
                "SELECT COALESCE(MAX(seq_no), 0) AS max_seq FROM session_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            next_seq = int(seq_row["max_seq"]) + 1
            connection.execute(
                """
                INSERT INTO session_messages (
                  id, session_id, project_id, seq_no, role, message_type, title, content_md, source_mode,
                  evidence_status, disclosure_note, status_label, supports_summary, supports_report, related_message_id,
                  created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    message_id,
                    session_id,
                    project_id,
                    next_seq,
                    role,
                    message_type,
                    title,
                    content_md,
                    source_mode,
                    evidence_status,
                    disclosure_note,
                    status_label,
                    1 if supports_summary else 0,
                    1 if supports_report else 0,
                    related_message_id,
                    now,
                    now,
                ),
            )

            for index, source in enumerate(sources or [], start=1):
                connection.execute(
                    """
                    INSERT INTO message_sources (
                      id, message_id, session_id, project_id, source_id, source_kind, chunk_id, source_rank,
                      source_type, source_title, canonical_uri, external_uri, location_label, excerpt, relevance_score, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        message_id,
                        session_id,
                        project_id,
                        source.get("source_id"),
                        source.get("source_kind", "project_source"),
                        source.get("chunk_id"),
                        index,
                        source["source_type"],
                        source["source_title"],
                        source["canonical_uri"],
                        source.get("external_uri"),
                        source["location_label"],
                        source["excerpt"],
                        float(source["relevance_score"]),
                        now,
                    ),
                )

            self._touch_session_activity(connection=connection, session_id=session_id, timestamp=now)
            self._touch_project_activity(connection=connection, project_id=project_id, timestamp=now)
            connection.commit()
        finally:
            connection.close()

        detail = self.get_session_detail(session_id)
        if detail is None:
            raise RuntimeError("Message creation failed unexpectedly.")
        for message in reversed(detail["messages"]):
            if message["id"] == message_id:
                return message
        raise RuntimeError("Message creation failed unexpectedly.")

    def assign_auto_title(self, session_id: str, input_text: str) -> None:
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT title_source FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None or row["title_source"] != "pending":
                return
            title = " ".join(input_text.split())
            if len(title) > 36:
                title = f"{title[:33]}..."
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                UPDATE sessions
                SET title = ?, title_source = 'auto', updated_at = ?
                WHERE id = ?
                """,
                (title, now, session_id),
            )
            connection.commit()
        finally:
            connection.close()

    def get_latest_actionable_message(self, session_id: str) -> dict | None:
        connection = get_connection()
        try:
            row = connection.execute(
                """
                SELECT
                  id,
                  session_id,
                  project_id,
                  seq_no,
                  role,
                  message_type,
                  title,
                  content_md,
                  source_mode,
                  evidence_status,
                  disclosure_note,
                  status_label,
                  supports_summary,
                  supports_report,
                  related_message_id,
                  created_at,
                  updated_at,
                  deleted_at
                FROM session_messages
                WHERE session_id = ?
                  AND deleted_at IS NULL
                  AND message_type = 'assistant_answer'
                  AND supports_report = 1
                ORDER BY seq_no DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            source_rows = connection.execute(
                """
                SELECT
                  id,
                  source_id,
                  source_kind,
                  chunk_id,
                  source_rank,
                  source_type,
                  source_title,
                  canonical_uri,
                  external_uri,
                  location_label,
                  excerpt,
                  relevance_score
                FROM message_sources
                WHERE message_id = ?
                ORDER BY source_rank ASC
                """,
                (row["id"],),
            ).fetchall()
            item = {
                **dict(row),
                "supports_summary": bool(row["supports_summary"]),
                "supports_report": bool(row["supports_report"]),
                "sources": [dict(source_row) for source_row in source_rows],
            }
            return item
        finally:
            connection.close()

    def delete_result_card(self, message_id: str) -> dict | None:
        connection = get_connection()
        try:
            row = connection.execute(
                """
                SELECT session_id, message_type
                FROM session_messages
                WHERE id = ?
                  AND deleted_at IS NULL
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                return None
            if row["message_type"] not in {"summary_card", "report_card"}:
                raise ValueError("Only summary or report cards can be deleted.")
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """
                UPDATE session_messages
                SET deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, message_id),
            )
            connection.commit()
            return self.get_session_detail(row["session_id"])
        finally:
            connection.close()

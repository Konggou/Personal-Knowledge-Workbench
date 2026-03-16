from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.database import get_connection


@dataclass
class ProjectRecord:
    id: str
    name: str
    description: str
    default_external_policy: str
    status: str
    current_snapshot_id: str | None
    last_activity_at: str
    created_at: str
    updated_at: str
    archived_at: str | None
    active_session_count: int
    active_source_count: int
    latest_session_id: str | None
    latest_session_title: str | None

    def to_summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_external_policy": self.default_external_policy,
            "status": self.status,
            "current_snapshot_id": self.current_snapshot_id,
            "last_activity_at": self.last_activity_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "active_session_count": self.active_session_count,
            "active_source_count": self.active_source_count,
            "latest_session_id": self.latest_session_id,
            "latest_session_title": self.latest_session_title,
        }


class ProjectRepository:
    def list_projects(self, *, include_archived: bool = False, query: str | None = None) -> list[ProjectRecord]:
        connection = get_connection()
        try:
            sql = """
                WITH source_counts AS (
                  SELECT project_id, COUNT(*) AS active_source_count
                  FROM sources
                  WHERE deleted_at IS NULL
                    AND ingestion_status != 'archived'
                  GROUP BY project_id
                ),
                session_counts AS (
                  SELECT project_id, COUNT(*) AS active_session_count
                  FROM sessions
                  WHERE deleted_at IS NULL
                  GROUP BY project_id
                ),
                latest_session AS (
                  SELECT s.project_id, s.id AS latest_session_id, COALESCE(s.title, '新会话') AS latest_session_title
                  FROM sessions s
                  INNER JOIN (
                    SELECT project_id, MAX(COALESCE(latest_message_at, created_at)) AS max_activity
                    FROM sessions
                    WHERE deleted_at IS NULL
                    GROUP BY project_id
                  ) latest
                    ON latest.project_id = s.project_id
                   AND latest.max_activity = COALESCE(s.latest_message_at, s.created_at)
                  WHERE s.deleted_at IS NULL
                )
                SELECT
                  p.id,
                  p.name,
                  p.description,
                  p.default_external_policy,
                  p.status,
                  p.current_snapshot_id,
                  p.last_activity_at,
                  p.created_at,
                  p.updated_at,
                  p.archived_at,
                  COALESCE(sc.active_session_count, 0) AS active_session_count,
                  COALESCE(src.active_source_count, 0) AS active_source_count,
                  ls.latest_session_id,
                  ls.latest_session_title
                FROM projects p
                LEFT JOIN session_counts sc ON sc.project_id = p.id
                LEFT JOIN source_counts src ON src.project_id = p.id
                LEFT JOIN latest_session ls ON ls.project_id = p.id
                WHERE 1 = 1
            """
            params: list[object] = []

            if not include_archived:
                sql += " AND p.status = 'active'"

            if query:
                sql += " AND lower(p.name) LIKE ?"
                params.append(f"%{query.lower()}%")

            sql += " ORDER BY p.last_activity_at DESC, p.created_at DESC"
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [ProjectRecord(**dict(row)) for row in rows]
        finally:
            connection.close()

    def get_project(self, project_id: str) -> ProjectRecord | None:
        connection = get_connection()
        try:
            row = connection.execute(
                """
                WITH source_counts AS (
                  SELECT project_id, COUNT(*) AS active_source_count
                  FROM sources
                  WHERE deleted_at IS NULL
                    AND ingestion_status != 'archived'
                  GROUP BY project_id
                ),
                session_counts AS (
                  SELECT project_id, COUNT(*) AS active_session_count
                  FROM sessions
                  WHERE deleted_at IS NULL
                  GROUP BY project_id
                ),
                latest_session AS (
                  SELECT s.project_id, s.id AS latest_session_id, COALESCE(s.title, '新会话') AS latest_session_title
                  FROM sessions s
                  INNER JOIN (
                    SELECT project_id, MAX(COALESCE(latest_message_at, created_at)) AS max_activity
                    FROM sessions
                    WHERE deleted_at IS NULL
                    GROUP BY project_id
                  ) latest
                    ON latest.project_id = s.project_id
                   AND latest.max_activity = COALESCE(s.latest_message_at, s.created_at)
                  WHERE s.deleted_at IS NULL
                )
                SELECT
                  p.id,
                  p.name,
                  p.description,
                  p.default_external_policy,
                  p.status,
                  p.current_snapshot_id,
                  p.last_activity_at,
                  p.created_at,
                  p.updated_at,
                  p.archived_at,
                  COALESCE(sc.active_session_count, 0) AS active_session_count,
                  COALESCE(src.active_source_count, 0) AS active_source_count,
                  ls.latest_session_id,
                  ls.latest_session_title
                FROM projects p
                LEFT JOIN session_counts sc ON sc.project_id = p.id
                LEFT JOIN source_counts src ON src.project_id = p.id
                LEFT JOIN latest_session ls ON ls.project_id = p.id
                WHERE p.id = ?
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            return ProjectRecord(**dict(row))
        finally:
            connection.close()

    def create_project(
        self,
        *,
        name: str,
        description: str,
        default_external_policy: str,
    ) -> ProjectRecord:
        now = datetime.now(UTC).isoformat()
        snapshot_id = str(uuid4())
        project_id = str(uuid4())

        connection = get_connection()
        try:
            connection.execute(
                """
                INSERT INTO projects (
                  id,
                  name,
                  description,
                  default_external_policy,
                  status,
                  current_snapshot_id,
                  last_activity_at,
                  created_at,
                  updated_at,
                  archived_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, NULL)
                """,
                (
                    project_id,
                    name,
                    description,
                    default_external_policy,
                    snapshot_id,
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO project_snapshots (
                  id, project_id, snapshot_number, reason, status,
                  source_count, indexed_source_count, low_quality_source_count, created_at
                ) VALUES (?, ?, 1, 'manual_rebuild', 'ready', 0, 0, 0, ?)
                """,
                (snapshot_id, project_id, now),
            )
            connection.commit()
        finally:
            connection.close()

        project = self.get_project(project_id)
        if project is None:
            raise RuntimeError("Project creation failed unexpectedly.")
        return project

    def touch_project_activity(self, project_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            connection.execute(
                """
                UPDATE projects
                SET last_activity_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, project_id),
            )
            connection.commit()
        finally:
            connection.close()

    def delete_project(self, project_id: str) -> ProjectRecord | None:
        """Soft delete a project by setting status to 'archived' and archived_at timestamp.
        
        Returns None if project doesn't exist or is already archived.
        """
        now = datetime.now(UTC).isoformat()
        connection = get_connection()
        try:
            # Check if project exists and is not already archived
            existing = self.get_project(project_id)
            if existing is None or existing.status == "archived":
                return None

            connection.execute(
                """
                UPDATE projects
                SET status = 'archived', updated_at = ?, archived_at = ?
                WHERE id = ? AND status != 'archived'
                """,
                (now, now, project_id),
            )
            connection.commit()
            return self.get_project(project_id)
        finally:
            connection.close()

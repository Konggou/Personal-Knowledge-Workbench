"""Cleanup service for permanently deleting old soft-deleted data."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import get_connection
from app.core.qdrant import get_qdrant_client


class CleanupService:
    """Service for cleaning up old soft-deleted data."""

    def __init__(self, retention_days: int = 30) -> None:
        self.retention_days = retention_days

    def _build_in_clause(self, ids: list[str]) -> tuple[str, list[str]]:
        """Build safe IN clause with proper parameterization."""
        if not ids:
            return "", []
        placeholders = ",".join(["?" for _ in ids])
        return placeholders, ids

    def cleanup_all(self) -> dict[str, Any]:
        """
        Clean up all soft-deleted data older than retention_days.
        Returns cleanup statistics.
        """
        cutoff_date = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()
        stats = {
            "cutoff_date": cutoff_date,
            "projects_deleted": 0,
            "sessions_deleted": 0,
            "messages_deleted": 0,
            "sources_deleted": 0,
            "chunks_deleted": 0,
            "qdrant_points_deleted": 0,
        }

        connection = get_connection()
        try:
            # 1. Find projects to hard delete (archived more than 30 days ago)
            # Projects marked as 'archived' with archived_at older than retention_days are considered deleted
            projects_to_delete = connection.execute(
                """
                SELECT id FROM projects
                WHERE status = 'archived' AND archived_at < ?
                """,
                (cutoff_date,),
            ).fetchall()
            project_ids = [row[0] for row in projects_to_delete]

            if not project_ids:
                return stats

            stats["projects_deleted"] = len(project_ids)

            # 2. Delete sessions and their messages for these projects
            for project_id in project_ids:
                # Get session IDs for this project
                sessions = connection.execute(
                    "SELECT id FROM sessions WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
                session_ids = [row[0] for row in sessions]

                if session_ids:
                    session_placeholders, _ = self._build_in_clause(session_ids)
                    
                    # Delete message_sources first (foreign key constraints)
                    connection.execute(
                        f"""
                        DELETE FROM message_sources
                        WHERE session_id IN ({session_placeholders})
                        """,
                        session_ids,
                    )

                    # Delete messages
                    cursor = connection.execute(
                        f"""
                        DELETE FROM session_messages
                        WHERE session_id IN ({session_placeholders})
                        """,
                        session_ids,
                    )
                    stats["messages_deleted"] += cursor.rowcount

                    # Delete sessions
                    cursor = connection.execute(
                        f"""
                        DELETE FROM sessions
                        WHERE id IN ({session_placeholders})
                        """,
                        session_ids,
                    )
                    stats["sessions_deleted"] += cursor.rowcount

            # 3. Delete sources and chunks for these projects
            for project_id in project_ids:
                # Get source IDs
                sources = connection.execute(
                    "SELECT id FROM sources WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
                source_ids = [row[0] for row in sources]

                if source_ids:
                    source_placeholders, _ = self._build_in_clause(source_ids)
                    
                    # Get chunk IDs and qdrant point IDs for vector deletion
                    chunk_data = connection.execute(
                        f"""
                        SELECT id, qdrant_point_id FROM source_chunks
                        WHERE source_id IN ({source_placeholders})
                        """,
                        source_ids,
                    ).fetchall()
                    chunk_ids = [row[0] for row in chunk_data]
                    qdrant_point_ids = [row[1] for row in chunk_data if row[1]]

                    # Delete from Qdrant
                    if qdrant_point_ids:
                        try:
                            qdrant_client = get_qdrant_client()
                            qdrant_client.delete(
                                collection_name="knowledge_chunks_v1",
                                points_selector=qdrant_point_ids,
                            )
                            stats["qdrant_points_deleted"] += len(qdrant_point_ids)
                        except Exception as e:
                            # Log error but continue with database cleanup
                            print(f"Warning: Failed to delete some Qdrant points: {e}")

                    # Delete source_chunk_fts entries
                    if chunk_ids:
                        chunk_placeholders, _ = self._build_in_clause(chunk_ids)
                        
                        connection.execute(
                            f"""
                            DELETE FROM source_chunk_fts
                            WHERE chunk_id IN ({chunk_placeholders})
                            """,
                            chunk_ids,
                        )

                        # Delete chunks
                        cursor = connection.execute(
                            f"""
                            DELETE FROM source_chunks
                            WHERE id IN ({chunk_placeholders})
                            """,
                            chunk_ids,
                        )
                        stats["chunks_deleted"] += cursor.rowcount

                    # Delete sources
                    cursor = connection.execute(
                        f"""
                        DELETE FROM sources
                        WHERE id IN ({source_placeholders})
                        """,
                        source_ids,
                    )
                    stats["sources_deleted"] += cursor.rowcount

            # 4. Delete snapshots and finally projects
            for project_id in project_ids:
                # Delete snapshots
                connection.execute(
                    "DELETE FROM project_snapshots WHERE project_id = ?",
                    (project_id,),
                )

                # Delete project
                connection.execute(
                    "DELETE FROM projects WHERE id = ?",
                    (project_id,),
                )

            connection.commit()
            return stats

        except Exception as e:
            connection.rollback()
            raise e
        finally:
            connection.close()

    def cleanup_old_deleted_sessions(self) -> int:
        """
        Clean up old soft-deleted sessions (not associated with deleted projects).
        Returns number of sessions deleted.
        """
        cutoff_date = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()

        connection = get_connection()
        try:
            # Find sessions to delete
            sessions = connection.execute(
                """
                SELECT id FROM sessions
                WHERE deleted_at IS NOT NULL AND deleted_at < ?
                """,
                (cutoff_date,),
            ).fetchall()
            session_ids = [row[0] for row in sessions]

            if not session_ids:
                return 0

            session_placeholders, _ = self._build_in_clause(session_ids)

            # Delete message_sources
            connection.execute(
                f"""
                DELETE FROM message_sources
                WHERE session_id IN ({session_placeholders})
                """,
                session_ids,
            )

            # Delete messages
            connection.execute(
                f"""
                DELETE FROM session_messages
                WHERE session_id IN ({session_placeholders})
                """,
                session_ids,
            )

            # Delete sessions
            cursor = connection.execute(
                f"""
                DELETE FROM sessions
                WHERE id IN ({session_placeholders})
                """,
                session_ids,
            )

            connection.commit()
            return cursor.rowcount
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            connection.close()

    def cleanup_old_deleted_sources(self) -> int:
        """
        Clean up old soft-deleted sources (not associated with deleted projects).
        Returns number of sources deleted.
        """
        cutoff_date = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()

        connection = get_connection()
        try:
            # Find sources with deleted_at set (hard deleted)
            sources = connection.execute(
                """
                SELECT id FROM sources
                WHERE deleted_at IS NOT NULL AND deleted_at < ?
                """,
                (cutoff_date,),
            ).fetchall()
            source_ids = [row[0] for row in sources]

            if not source_ids:
                return 0

            source_placeholders, _ = self._build_in_clause(source_ids)

            # Get chunk data for Qdrant cleanup
            chunk_data = connection.execute(
                f"""
                SELECT id, qdrant_point_id FROM source_chunks
                WHERE source_id IN ({source_placeholders})
                """,
                source_ids,
            ).fetchall()
            chunk_ids = [row[0] for row in chunk_data]
            qdrant_point_ids = [row[1] for row in chunk_data if row[1]]

            # Delete from Qdrant
            if qdrant_point_ids:
                try:
                    qdrant_client = get_qdrant_client()
                    qdrant_client.delete(
                        collection_name="knowledge_chunks_v1",
                        points_selector=qdrant_point_ids,
                    )
                except Exception as e:
                    print(f"Warning: Failed to delete some Qdrant points: {e}")

            # Delete chunks and FTS
            if chunk_ids:
                chunk_placeholders, _ = self._build_in_clause(chunk_ids)
                
                connection.execute(
                    f"""
                    DELETE FROM source_chunk_fts
                    WHERE chunk_id IN ({chunk_placeholders})
                    """,
                    chunk_ids,
                )
                connection.execute(
                    f"""
                    DELETE FROM source_chunks
                    WHERE id IN ({chunk_placeholders})
                    """,
                    chunk_ids,
                )

            # Delete sources
            cursor = connection.execute(
                f"""
                DELETE FROM sources
                WHERE id IN ({source_placeholders})
                """,
                source_ids,
            )

            connection.commit()
            return cursor.rowcount
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            connection.close()

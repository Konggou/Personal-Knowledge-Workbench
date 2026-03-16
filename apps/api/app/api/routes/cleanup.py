"""Cleanup API routes for manual and scheduled data cleanup."""

from fastapi import APIRouter

from app.services.cleanup_service import CleanupService

router = APIRouter()


@router.post("/cleanup", tags=["cleanup"])
def run_cleanup(retention_days: int = 30) -> dict:
    """
    Manually trigger cleanup of old soft-deleted data.
    Only for admin/maintenance use.
    """
    service = CleanupService(retention_days=retention_days)

    # Clean up deleted projects (with all related data)
    project_stats = service.cleanup_all()

    # Clean up orphaned sessions and sources
    sessions_deleted = service.cleanup_old_deleted_sessions()
    sources_deleted = service.cleanup_old_deleted_sources()

    return {
        "status": "success",
        "retention_days": retention_days,
        "project_cleanup": project_stats,
        "orphaned_sessions_deleted": sessions_deleted,
        "orphaned_sources_deleted": sources_deleted,
    }


@router.get("/cleanup/preview", tags=["cleanup"])
def preview_cleanup(retention_days: int = 30) -> dict:
    """
    Preview what would be deleted without actually deleting.
    """
    from datetime import UTC, datetime, timedelta
    from app.core.database import get_connection

    cutoff_date = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()

    connection = get_connection()
    try:
        # Count projects to be deleted (archived status means soft-deleted)
        projects = connection.execute(
            """
            SELECT COUNT(*) FROM projects
            WHERE status = 'archived' AND archived_at < ?
            """,
            (cutoff_date,),
        ).fetchone()[0]

        # Count old deleted sessions
        sessions = connection.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE deleted_at IS NOT NULL AND deleted_at < ?
            """,
            (cutoff_date,),
        ).fetchone()[0]

        # Count old deleted sources
        sources = connection.execute(
            """
            SELECT COUNT(*) FROM sources
            WHERE deleted_at IS NOT NULL AND deleted_at < ?
            """,
            (cutoff_date,),
        ).fetchone()[0]

        return {
            "cutoff_date": cutoff_date,
            "retention_days": retention_days,
            "would_delete": {
                "projects": projects,
                "sessions": sessions,
                "sources": sources,
            },
        }
    finally:
        connection.close()

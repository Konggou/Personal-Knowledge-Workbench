import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import initialize_database
from app.core.settings import get_settings
from app.repositories.search_repository import SearchRepository
from app.services.cleanup_service import CleanupService
from app.services.vector_store import VectorStore

# Store background task references to prevent garbage collection
_background_tasks: set[asyncio.Task[Any]] = set()


async def _run_cleanup_in_background() -> None:
    """Run cleanup task in background without blocking startup."""
    try:
        service = CleanupService(retention_days=30)

        # Clean up deleted projects and related data
        stats = service.cleanup_all()
        if stats["projects_deleted"] > 0:
            print(f"[Cleanup] Deleted {stats['projects_deleted']} old projects")

        # Clean up orphaned sessions
        sessions = service.cleanup_old_deleted_sessions()
        if sessions > 0:
            print(f"[Cleanup] Deleted {sessions} old sessions")

        # Clean up orphaned sources
        sources = service.cleanup_old_deleted_sources()
        if sources > 0:
            print(f"[Cleanup] Deleted {sources} old sources")

    except Exception as e:
        print(f"[Cleanup] Error during cleanup: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    try:
        SearchRepository().ensure_retrieval_index()
    except Exception:
        pass
    try:
        VectorStore().ensure_collection()
    except Exception:
        pass

    # Run cleanup in background without blocking
    task = asyncio.create_task(_run_cleanup_in_background())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    yield


settings = get_settings()

app = FastAPI(
    title="Personal Knowledge Workbench API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)

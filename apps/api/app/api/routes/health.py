from fastapi import APIRouter

from app.core.settings import get_settings
from app.services.vector_store import VectorStore

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict:
    settings = get_settings()
    vector_backend = VectorStore().describe_backend()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "api_prefix": settings.api_prefix,
        "sqlite_path": str(settings.sqlite_path),
        "qdrant_collection": settings.qdrant_collection,
        "qdrant_backend": vector_backend,
    }

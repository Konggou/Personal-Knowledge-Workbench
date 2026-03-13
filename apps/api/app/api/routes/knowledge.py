from fastapi import APIRouter, Query

from app.services.knowledge_service import KnowledgeService

router = APIRouter()
service = KnowledgeService()


@router.get("/knowledge")
def list_knowledge(
    query: str = Query(""),
    project_id: str | None = Query(None),
    include_archived: bool = Query(False),
) -> dict:
    return service.list_knowledge(query=query, project_id=project_id, include_archived=include_archived)

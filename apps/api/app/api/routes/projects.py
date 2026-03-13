from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.projects import ProjectCreateRequest
from app.services.project_service import ProjectService

router = APIRouter()
service = ProjectService()


@router.get("")
def list_projects(
    include_archived: bool = Query(False),
    query: str = Query(""),
) -> dict:
    items = service.list_projects(include_archived=include_archived, query=query.strip() or None)
    return {"items": items, "total": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest) -> dict:
    name = payload.name.strip()
    description = payload.description.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Project name must not be blank.")
    if not description:
        raise HTTPException(status_code=422, detail="Project description must not be blank.")

    item = service.create_project(
        name=name,
        description=description,
        default_external_policy=payload.default_external_policy,
    )
    return {"item": item}


@router.get("/{project_id}")
def get_project(project_id: str) -> dict:
    item = service.get_project(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return {"item": item}

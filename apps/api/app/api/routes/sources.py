from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.schemas.sources import WebSourceCreateRequest, WebSourceUpdateRequest
from app.services.source_service import SourceService

router = APIRouter()
service = SourceService()


@router.get("/projects/{project_id}/sources")
def list_sources(project_id: str, include_archived: bool = Query(False)) -> dict:
    return {"items": service.list_sources(project_id, include_archived=include_archived)}


@router.get("/sources/{source_id}")
def get_source_preview(source_id: str) -> dict:
    return {"item": service.get_source_preview(source_id)}


@router.post("/projects/{project_id}/sources/files", status_code=status.HTTP_201_CREATED)
async def create_file_sources(
    project_id: str,
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(None),
) -> dict:
    items = await service.create_file_sources(project_id, files, session_id=session_id)
    return {"items": items}


@router.post("/projects/{project_id}/sources/web", status_code=status.HTTP_201_CREATED)
def create_web_source(project_id: str, payload: WebSourceCreateRequest) -> dict:
    item = service.create_web_source(project_id=project_id, url=str(payload.url), session_id=payload.session_id)
    return {"item": item}


@router.patch("/sources/{source_id}/web")
def update_web_source(source_id: str, payload: WebSourceUpdateRequest) -> dict:
    return {"item": service.update_web_source(source_id, str(payload.url))}


@router.post("/sources/{source_id}/refresh")
def refresh_source(source_id: str) -> dict:
    return {"item": service.refresh_source(source_id)}


@router.post("/sources/{source_id}/archive")
def archive_source(source_id: str) -> dict:
    return {"item": service.archive_source(source_id)}


@router.post("/sources/{source_id}/restore")
def restore_source(source_id: str) -> dict:
    return {"item": service.restore_source(source_id)}


@router.delete("/sources/{source_id}")
def delete_source(source_id: str) -> dict:
    return {"item": service.delete_source(source_id)}

from fastapi import APIRouter, HTTPException, status

from app.schemas.sessions import SessionMessageCreateRequest, SessionRenameRequest
from app.services.session_service import SessionService

router = APIRouter()
service = SessionService()


@router.get("/sessions")
def list_sessions() -> dict:
    return {"groups": service.list_sessions_grouped()}


@router.get("/projects/{project_id}/sessions")
def list_project_sessions(project_id: str) -> dict:
    return {"items": service.list_project_sessions(project_id)}


@router.post("/projects/{project_id}/sessions", status_code=status.HTTP_201_CREATED)
def create_session(project_id: str) -> dict:
    return {"item": service.create_session(project_id)}


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    item = service.get_session(session_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return {"item": item}


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: SessionRenameRequest) -> dict:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Session title must not be blank.")
    return {"item": service.rename_session(session_id, title)}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str):
    service.delete_session(session_id)


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: str, payload: SessionMessageCreateRequest) -> dict:
    return {"item": service.send_message(session_id=session_id, content=payload.content, deep_research=payload.deep_research)}


@router.post("/sessions/{session_id}/messages/stream")
def stream_message(session_id: str, payload: SessionMessageCreateRequest):
    return service.stream_send_message(session_id=session_id, content=payload.content, deep_research=payload.deep_research)


@router.post("/sessions/{session_id}/summary")
def create_summary(session_id: str) -> dict:
    return {"item": service.create_summary_card(session_id)}


@router.post("/sessions/{session_id}/report")
def create_report(session_id: str) -> dict:
    return {"item": service.create_report_card(session_id)}


@router.delete("/messages/{message_id}")
def delete_result_card(message_id: str) -> dict:
    return {"item": service.delete_result_card(message_id)}


@router.get("/sessions/{session_id}/events")
def stream_session_events(session_id: str):
    return service.stream_session_events(session_id)

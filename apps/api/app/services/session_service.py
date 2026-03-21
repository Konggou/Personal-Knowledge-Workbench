from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.services.agent_orchestrator_service import AgentOrchestratorService
from app.services.grounded_generation_service import GroundedGenerationService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService
from app.services.session_turn_service import SessionTurnService


class SessionService:
    def __init__(self) -> None:
        self.projects = ProjectRepository()
        self.sessions = SessionRepository()
        self.llm = LLMService()
        self.search = SearchService(llm_service=self.llm)
        self.grounded_generation = GroundedGenerationService(
            search_service=self.search,
            llm_service=self.llm,
        )
        self.agent = AgentOrchestratorService(
            llm_service=self.llm,
            search_service=self.search,
            grounded_generation_service=self.grounded_generation,
        )
        self.turns = SessionTurnService(
            sessions=self.sessions,
            llm_service=self.llm,
            search_service=self.search,
            grounded_generation_service=self.grounded_generation,
            agent_service=self.agent,
        )

    def list_project_sessions(self, project_id: str) -> list[dict]:
        self._get_project_or_404(project_id)
        return self.sessions.list_project_sessions(project_id)

    def list_sessions_grouped(self) -> list[dict]:
        items = self.sessions.list_all_sessions()
        groups: dict[str, dict] = {}
        for item in items:
            group = groups.setdefault(
                item["project_id"],
                {
                    "project_id": item["project_id"],
                    "project_name": item["project_name"],
                    "items": [],
                },
            )
            group["items"].append(item)
        return list(groups.values())

    def create_session(self, project_id: str) -> dict:
        self._get_project_or_404(project_id)
        return self.sessions.create_session(project_id)

    def get_session(self, session_id: str) -> dict | None:
        detail = self.sessions.get_session_detail(session_id)
        if detail is None or detail["deleted_at"] is not None:
            return None
        return detail

    def rename_session(self, session_id: str, title: str) -> dict:
        item = self.sessions.rename_session(session_id, title)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return item

    def delete_session(self, session_id: str) -> None:
        item = self.sessions.delete_session(session_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    def delete_result_card(self, message_id: str) -> dict:
        try:
            item = self.sessions.delete_result_card(message_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail=f"Message not found: {message_id}")
        return item

    def stream_session_events(self, session_id: str) -> StreamingResponse:
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        def event_stream():
            for message in detail["messages"]:
                payload = {"session_id": session_id, "message": message}
                event_name = "source_update" if message["message_type"] == "source_update" else "message"
                yield self.turns.sse_event(event_name, payload)

            status_payload = {
                "session_id": session_id,
                "message_count": len(detail["messages"]),
                "latest_message_at": detail["latest_message_at"],
            }
            yield self.turns.sse_event("status", status_payload)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    def send_message(self, *, session_id: str, content: str, deep_research: bool, web_browsing: bool = False) -> dict:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)
        self.turns.run_turn(
            session_id=session_id,
            project_id=session["project_id"],
            project_name=session["project_name"],
            query=normalized_content,
            history=current_session["messages"],
            deep_research=deep_research,
            web_browsing=web_browsing,
        )
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Message send failed unexpectedly.")
        return detail

    def stream_send_message(
        self,
        *,
        session_id: str,
        content: str,
        deep_research: bool,
        web_browsing: bool = False,
    ) -> StreamingResponse:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)
        return self.turns.stream_turn(
            session_id=session_id,
            project_id=session["project_id"],
            project_name=session["project_name"],
            query=normalized_content,
            history=current_session["messages"],
            deep_research=deep_research,
            web_browsing=web_browsing,
            refresh_session=self.get_session,
        )

    def create_summary_card(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        latest = self.sessions.get_latest_actionable_message(session_id)
        if latest is None:
            raise HTTPException(status_code=422, detail="No actionable conclusion is available yet.")

        summary_body = self._summarize_content(self._compose_message_markdown(latest))
        self.sessions.create_message(
            session_id=session_id,
            project_id=session["project_id"],
            role="assistant",
            message_type="summary_card",
            title=f"摘要：{latest['title'] or '最近结论'}",
            content_md=summary_body,
            related_message_id=latest["id"],
            source_mode=latest.get("source_mode"),
            evidence_status=latest.get("evidence_status"),
            disclosure_note=latest.get("disclosure_note"),
            sources=latest.get("sources") or [],
        )
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Summary creation failed unexpectedly.")
        return detail

    def create_report_card(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        latest = self.sessions.get_latest_actionable_message(session_id)
        if latest is None:
            raise HTTPException(status_code=422, detail="No actionable conclusion is available yet.")

        sources_md = "\n".join(
            f"- {source['source_title']}（{source['location_label']}）"
            for source in (latest.get("sources") or [])
        ) or "- 当前结论没有命中项目内来源。"
        report_body = (
            f"# {latest['title'] or '最近结论'}\n\n"
            f"{self._compose_message_markdown(latest)}\n\n"
            f"## 来源说明\n\n{sources_md}"
        )
        self.sessions.create_message(
            session_id=session_id,
            project_id=session["project_id"],
            role="assistant",
            message_type="report_card",
            title=f"报告：{latest['title'] or '最近结论'}",
            content_md=report_body,
            related_message_id=latest["id"],
            source_mode=latest.get("source_mode"),
            evidence_status=latest.get("evidence_status"),
            disclosure_note=latest.get("disclosure_note"),
            sources=latest.get("sources") or [],
        )
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Report creation failed unexpectedly.")
        return detail

    def _prepare_user_turn(self, *, session_id: str, content: str) -> tuple[dict, str, dict]:
        session = self.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        normalized_content = content.strip()
        if not normalized_content:
            raise HTTPException(status_code=422, detail="Message content must not be blank.")

        self.sessions.create_message(
            session_id=session_id,
            project_id=session["project_id"],
            role="user",
            message_type="user_prompt",
            content_md=normalized_content,
        )
        self.sessions.assign_auto_title(session_id, normalized_content)

        current_session = self.get_session(session_id)
        if current_session is None:
            raise HTTPException(status_code=500, detail="Message send failed unexpectedly.")
        return session, normalized_content, current_session

    def _compose_message_markdown(self, message: dict) -> str:
        content = message["content_md"].strip()
        disclosure_note = (message.get("disclosure_note") or "").strip()
        if disclosure_note:
            return f"{content}\n\n> {disclosure_note}"
        return content

    def _get_project_or_404(self, project_id: str):
        project = self.projects.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return project

    def _summarize_content(self, content_md: str) -> str:
        normalized = " ".join(content_md.replace("\n", " ").split())
        if len(normalized) <= 240:
            return normalized
        return f"{normalized[:237]}..."

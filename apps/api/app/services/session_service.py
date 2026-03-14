from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.core.settings import get_settings
from app.repositories.project_repository import ProjectRepository
from app.repositories.session_repository import SessionRepository
from app.services.agent_orchestrator_service import AgentOrchestratorService
from app.services.grounded_generation_service import GroundedGenerationService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService


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
                yield self._sse_event(event_name, payload)

            status_payload = {
                "session_id": session_id,
                "message_count": len(detail["messages"]),
                "latest_message_at": detail["latest_message_at"],
            }
            yield self._sse_event("status", status_payload)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    def send_message(self, *, session_id: str, content: str, deep_research: bool, web_browsing: bool = False) -> dict:
        if self._runtime_version() == "v2":
            return self._send_message_v2(
                session_id=session_id,
                content=content,
                deep_research=deep_research,
            )
        return self._send_message_v3(
            session_id=session_id,
            content=content,
            deep_research=deep_research,
            web_browsing=web_browsing,
        )

    def stream_send_message(
        self,
        *,
        session_id: str,
        content: str,
        deep_research: bool,
        web_browsing: bool = False,
    ) -> StreamingResponse:
        if self._runtime_version() == "v2":
            return self._stream_send_message_v2(
                session_id=session_id,
                content=content,
                deep_research=deep_research,
            )
        return self._stream_send_message_v3(
            session_id=session_id,
            content=content,
            deep_research=deep_research,
            web_browsing=web_browsing,
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
            [f"- {source['source_title']}（{source['location_label']}）" for source in latest["sources"]]
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
        )
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Report creation failed unexpectedly.")
        return detail

    def _send_message_v2(self, *, session_id: str, content: str, deep_research: bool) -> dict:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)
        research_mode = deep_research

        if research_mode:
            self._create_status_message(
                session_id=session_id,
                project_id=session["project_id"],
                title="调研中",
                body="正在整理证据并生成更完整的结论。",
                status_label="researching",
            )

        evidences = self.grounded_generation.retrieve_evidence(
            project_id=session["project_id"],
            query=normalized_content,
            research_mode=research_mode,
            history=current_session["messages"],
        )
        answer = self._generate_answer(
            history=current_session["messages"],
            query=normalized_content,
            evidences=evidences,
            research_mode=research_mode,
            context_notes=None,
        )
        if not answer["answer_md"].strip():
            raise HTTPException(status_code=500, detail="Assistant response was empty.")

        self._persist_assistant_answer(
            session_id=session_id,
            project_id=session["project_id"],
            query=normalized_content,
            answer=answer,
            evidences=evidences,
        )

        if research_mode:
            self._create_status_message(
                session_id=session_id,
                project_id=session["project_id"],
                title="调研完成",
                body="已基于当前会话状态生成一版可继续讨论的结论。",
                status_label="completed",
            )

        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Message send failed unexpectedly.")
        return detail

    def _send_message_v3(self, *, session_id: str, content: str, deep_research: bool, web_browsing: bool) -> dict:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)
        turn = self.agent.orchestrate_turn(
            session_id=session_id,
            project_id=session["project_id"],
            project_name=session["project_name"],
            query=normalized_content,
            history=current_session["messages"],
            research_mode=deep_research,
            web_browsing=web_browsing,
        )
        self._persist_status_messages(
            session_id=session_id,
            project_id=session["project_id"],
            statuses=turn.status_messages,
        )
        answer = self._generate_answer(
            history=self.get_session(session_id)["messages"],
            query=normalized_content,
            evidences=turn.evidence_pack,
            research_mode=deep_research,
            context_notes=turn.context_notes,
        )
        if not answer["answer_md"].strip():
            raise HTTPException(status_code=500, detail="Assistant response was empty.")

        self._persist_assistant_answer(
            session_id=session_id,
            project_id=session["project_id"],
            query=normalized_content,
            answer=answer,
            evidences=turn.evidence_pack,
        )
        detail = self.get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=500, detail="Message send failed unexpectedly.")
        return detail

    def _stream_send_message_v2(self, *, session_id: str, content: str, deep_research: bool) -> StreamingResponse:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)
        research_mode = deep_research

        def event_stream() -> Iterator[str]:
            try:
                if research_mode:
                    status_message = self._create_status_message(
                        session_id=session_id,
                        project_id=session["project_id"],
                        title="调研中",
                        body="正在整理证据并生成更完整的结论。",
                        status_label="researching",
                    )
                    yield self._sse_event("status", {"message": status_message})

                evidences = self.grounded_generation.retrieve_evidence(
                    project_id=session["project_id"],
                    query=normalized_content,
                    research_mode=research_mode,
                    history=current_session["messages"],
                )

                stream = self._stream_generate_answer(
                    history=current_session["messages"],
                    query=normalized_content,
                    evidences=evidences,
                    research_mode=research_mode,
                    context_notes=None,
                )
                while True:
                    try:
                        chunk = next(stream)
                    except StopIteration as stop:
                        answer = stop.value
                        break
                    yield self._sse_event("delta", {"delta": chunk})

                if not answer["answer_md"].strip():
                    raise RuntimeError("Assistant response was empty.")

                assistant_message = self._persist_assistant_answer(
                    session_id=session_id,
                    project_id=session["project_id"],
                    query=normalized_content,
                    answer=answer,
                    evidences=evidences,
                )
                yield self._sse_event("done", {"message": assistant_message})

                if research_mode:
                    status_message = self._create_status_message(
                        session_id=session_id,
                        project_id=session["project_id"],
                        title="调研完成",
                        body="已基于当前会话状态生成一版可继续讨论的结论。",
                        status_label="completed",
                    )
                    yield self._sse_event("status", {"message": status_message})
            except Exception as exc:
                yield self._sse_event("error", {"message": str(exc)})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    def _stream_send_message_v3(
        self,
        *,
        session_id: str,
        content: str,
        deep_research: bool,
        web_browsing: bool,
    ) -> StreamingResponse:
        session, normalized_content, current_session = self._prepare_user_turn(session_id=session_id, content=content)

        def event_stream() -> Iterator[str]:
            try:
                turn = self.agent.orchestrate_turn(
                    session_id=session_id,
                    project_id=session["project_id"],
                    project_name=session["project_name"],
                    query=normalized_content,
                    history=current_session["messages"],
                    research_mode=deep_research,
                    web_browsing=web_browsing,
                )
                for status in turn.status_messages:
                    status_message = self._create_status_message(
                        session_id=session_id,
                        project_id=session["project_id"],
                        title=status["title"],
                        body=status["content_md"],
                        status_label=None,
                    )
                    yield self._sse_event("status", {"message": status_message})

                refreshed = self.get_session(session_id)
                if refreshed is None:
                    raise RuntimeError("Session refresh failed unexpectedly.")

                stream = self._stream_generate_answer(
                    history=refreshed["messages"],
                    query=normalized_content,
                    evidences=turn.evidence_pack,
                    research_mode=deep_research,
                    context_notes=turn.context_notes,
                )
                while True:
                    try:
                        chunk = next(stream)
                    except StopIteration as stop:
                        answer = stop.value
                        break
                    yield self._sse_event("delta", {"delta": chunk})

                if not answer["answer_md"].strip():
                    raise RuntimeError("Assistant response was empty.")

                assistant_message = self._persist_assistant_answer(
                    session_id=session_id,
                    project_id=session["project_id"],
                    query=normalized_content,
                    answer=answer,
                    evidences=turn.evidence_pack,
                )
                yield self._sse_event("done", {"message": assistant_message})
            except Exception as exc:
                yield self._sse_event("error", {"message": str(exc)})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

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

    def _generate_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
        context_notes: list[str] | None,
    ) -> dict:
        if evidences:
            return self.grounded_generation.generate_answer(
                history=history,
                query=query,
                evidences=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
            )

        weak = self._build_weak_mode_answer(history, research_mode, context_notes=context_notes)
        return {
            "title": weak["title"],
            "answer_md": weak["body_md"].strip(),
            "source_mode": "weak_source_mode",
            "evidence_status": None,
            "disclosure_note": None,
        }

    def _stream_generate_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
        context_notes: list[str] | None,
    ) -> Iterator[str]:
        if evidences:
            stream = self.grounded_generation.stream_generate_answer(
                history=history,
                query=query,
                evidences=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
            )
            while True:
                try:
                    chunk = next(stream)
                except StopIteration as stop:
                    return stop.value
                yield chunk

        streamed_chunks: list[str] = []
        weak_stream = self._stream_weak_mode_answer(history, research_mode, context_notes=context_notes)
        while True:
            try:
                chunk = next(weak_stream)
            except StopIteration as stop:
                weak = stop.value
                break
            streamed_chunks.append(chunk)
            yield chunk
        return {
            "title": weak["title"],
            "answer_md": weak["body_md"].strip(),
            "source_mode": "weak_source_mode",
            "evidence_status": None,
            "disclosure_note": None,
        }

    def _persist_assistant_answer(
        self,
        *,
        session_id: str,
        project_id: str,
        query: str,
        answer: dict,
        evidences: list[dict],
    ) -> dict:
        message = self.sessions.create_message(
            session_id=session_id,
            project_id=project_id,
            role="assistant",
            message_type="assistant_answer",
            title=answer["title"],
            content_md=answer["answer_md"],
            source_mode=answer["source_mode"],
            evidence_status=answer["evidence_status"],
            disclosure_note=answer["disclosure_note"],
            supports_summary=True,
            supports_report=True,
            sources=evidences,
        )
        self.agent.persist_answer_memory(
            project_id=project_id,
            session_id=session_id,
            query=query,
            answer_md=answer["answer_md"],
            evidences=evidences,
            message_id=message["id"],
        )
        return message

    def _persist_status_messages(self, *, session_id: str, project_id: str, statuses: list[dict]) -> None:
        for status in statuses:
            self._create_status_message(
                session_id=session_id,
                project_id=project_id,
                title=status["title"],
                body=status["content_md"],
                status_label=None,
            )

    def _create_status_message(
        self,
        *,
        session_id: str,
        project_id: str,
        title: str,
        body: str,
        status_label: str | None,
    ) -> dict:
        return self.sessions.create_message(
            session_id=session_id,
            project_id=project_id,
            role="system",
            message_type="status_card",
            title=title,
            content_md=body,
            status_label=status_label,
        )

    def _build_weak_mode_answer(
        self,
        history: list[dict],
        research_mode: bool,
        *,
        context_notes: list[str] | None,
    ) -> dict:
        title = "调研结论" if research_mode else None
        try:
            if not self.llm.is_configured():
                raise RuntimeError("LLM is not configured.")
            reply = self.llm.generate_chat_reply(
                conversation=history,
                research_mode=research_mode,
                context_notes=context_notes,
            )
        except RuntimeError as exc:
            message = str(exc)
            if message == "LLM is not configured.":
                fallback = (
                    "当前项目还没有命中可用资料。我本应继续按通用大模型对话模式回答，"
                    "但当前没有可用的模型配置。请先配置 `WORKBENCH_LLM_API_KEY`、"
                    "`WORKBENCH_LLM_BASE_URL` 和 `WORKBENCH_LLM_MODEL`，或者先补充项目资料。"
                )
            else:
                fallback = (
                    "当前项目还没有命中可用资料，所以这次回答切换到了通用大模型对话模式。"
                    f"不过这次调用模型时失败了：{message}"
                )
            if research_mode:
                fallback += "\n\n如果你只是想直接聊天，不必开启深度调研。"
            return {"title": title, "body_md": fallback}
        return {"title": title, "body_md": reply}

    def _stream_weak_mode_answer(
        self,
        history: list[dict],
        research_mode: bool,
        *,
        context_notes: list[str] | None,
    ) -> Iterator[str]:
        title = "调研结论" if research_mode else None
        if not self.llm.is_configured():
            fallback = (
                "当前项目还没有命中可用资料。我本应继续按通用大模型对话模式回答，"
                "但当前没有可用的模型配置。请先配置 `WORKBENCH_LLM_API_KEY`、"
                "`WORKBENCH_LLM_BASE_URL` 和 `WORKBENCH_LLM_MODEL`，或者先补充项目资料。"
            )
            if research_mode:
                fallback += "\n\n如果你只是想直接聊天，不必开启深度调研。"
            for chunk in self._chunk_text(fallback):
                yield chunk
            return {"title": title, "body_md": fallback}

        body_chunks: list[str] = []
        try:
            for chunk in self.llm.stream_chat_reply(
                conversation=history,
                research_mode=research_mode,
                context_notes=context_notes,
            ):
                body_chunks.append(chunk)
                yield chunk
            body_md = "".join(body_chunks).strip()
            if not body_md:
                raise RuntimeError("LLM returned an empty streamed response.")
            return {"title": title, "body_md": body_md}
        except RuntimeError as exc:
            if body_chunks:
                return {"title": title, "body_md": "".join(body_chunks).strip()}
            fallback = (
                "当前项目还没有命中可用资料，所以这次回答切换到了通用大模型对话模式。"
                f"不过这次调用模型时失败了：{exc}"
            )
            if research_mode:
                fallback += "\n\n如果你只是想直接聊天，不必开启深度调研。"
            for chunk in self._chunk_text(fallback):
                yield chunk
            return {"title": title, "body_md": fallback}

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

    def _runtime_version(self) -> str:
        version = get_settings().agent_runtime_version.strip().lower()
        return "v2" if version == "v2" else "v3"

    def _chunk_text(self, text: str, size: int = 48) -> Iterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]

    def _sse_event(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

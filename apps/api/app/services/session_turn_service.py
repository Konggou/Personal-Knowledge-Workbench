from __future__ import annotations

import json
from collections.abc import Callable, Iterator

from fastapi.responses import StreamingResponse

from app.repositories.session_repository import SessionRepository
from app.services.agent_orchestrator_service import AgentOrchestratorService
from app.services.grounded_generation_service import GroundedGenerationService
from app.services.llm_service import LLMService
from app.services.search_service import SearchService


class SessionTurnService:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        llm_service: LLMService,
        search_service: SearchService,
        grounded_generation_service: GroundedGenerationService,
        agent_service: AgentOrchestratorService,
    ) -> None:
        self.sessions = sessions
        self.llm = llm_service
        self.search = search_service
        self.grounded_generation = grounded_generation_service
        self.agent = agent_service

    def run_turn(
        self,
        *,
        session_id: str,
        project_id: str,
        project_name: str,
        query: str,
        history: list[dict],
        deep_research: bool,
        web_browsing: bool,
    ) -> dict:
        turn = self.agent.orchestrate_turn(
            session_id=session_id,
            project_id=project_id,
            project_name=project_name,
            query=query,
            history=history,
            research_mode=deep_research,
            web_browsing=web_browsing,
        )
        self.create_status_messages(
            session_id=session_id,
            project_id=project_id,
            statuses=turn.status_messages,
        )
        answer = self.generate_answer(
            history=self.sessions.get_session_detail(session_id)["messages"],
            query=query,
            evidences=turn.evidence_pack,
            research_mode=deep_research,
            context_notes=turn.context_notes,
        )
        return self.persist_assistant_answer(
            session_id=session_id,
            project_id=project_id,
            query=query,
            answer=answer,
            evidences=turn.evidence_pack,
        )

    def stream_turn(
        self,
        *,
        session_id: str,
        project_id: str,
        project_name: str,
        query: str,
        history: list[dict],
        deep_research: bool,
        web_browsing: bool,
        refresh_session: Callable[[str], dict | None],
    ) -> StreamingResponse:
        def event_stream() -> Iterator[str]:
            try:
                turn = self.agent.orchestrate_turn(
                    session_id=session_id,
                    project_id=project_id,
                    project_name=project_name,
                    query=query,
                    history=history,
                    research_mode=deep_research,
                    web_browsing=web_browsing,
                )
                status_messages = self.create_status_messages(
                    session_id=session_id,
                    project_id=project_id,
                    statuses=turn.status_messages,
                )
                for status_message in status_messages:
                    yield self.sse_event("status", {"message": status_message})

                refreshed = refresh_session(session_id)
                if refreshed is None:
                    raise RuntimeError("Session refresh failed unexpectedly.")

                stream = self.stream_generate_answer(
                    history=refreshed["messages"],
                    query=query,
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
                    yield self.sse_event("delta", {"delta": chunk})

                if not answer["answer_md"].strip():
                    raise RuntimeError("Assistant response was empty.")

                assistant_message = self.persist_assistant_answer(
                    session_id=session_id,
                    project_id=project_id,
                    query=query,
                    answer=answer,
                    evidences=turn.evidence_pack,
                )
                yield self.sse_event("done", {"message": assistant_message})
            except Exception as exc:
                yield self.sse_event("error", {"message": str(exc)})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    def generate_answer(
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

    def stream_generate_answer(
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

        weak_stream = self._stream_weak_mode_answer(history, research_mode, context_notes=context_notes)
        while True:
            try:
                chunk = next(weak_stream)
            except StopIteration as stop:
                weak = stop.value
                break
            yield chunk
        return {
            "title": weak["title"],
            "answer_md": weak["body_md"].strip(),
            "source_mode": "weak_source_mode",
            "evidence_status": None,
            "disclosure_note": None,
        }

    def persist_assistant_answer(
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

    def create_status_messages(self, *, session_id: str, project_id: str, statuses: list[dict]) -> list[dict]:
        messages: list[dict] = []
        for status in statuses:
            messages.append(
                self.sessions.create_message(
                    session_id=session_id,
                    project_id=project_id,
                    role="system",
                    message_type="status_card",
                    title=status["title"],
                    content_md=status["content_md"],
                    status_label=None,
                )
            )
        return messages

    def _build_weak_mode_answer(
        self,
        history: list[dict],
        research_mode: bool,
        *,
        context_notes: list[str] | None,
    ) -> dict:
        title = "深度调研" if research_mode else None
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
                    "当前还没有可用的大模型配置，因此我暂时无法继续生成回答。"
                    "请先在设置页补充 `WORKBENCH_LLM_API_KEY`、`WORKBENCH_LLM_BASE_URL` "
                    "和 `WORKBENCH_LLM_MODEL` 对应的配置。"
                )
            else:
                fallback = (
                    "当前这次回答在调用大模型时失败了，我先保留现有会话内容。"
                    f"错误信息：{message}"
                )
            if research_mode:
                fallback += "\n\n深度调研模式没有拿到新结论，你可以检查模型配置后重新发起请求。"
            return {"title": title, "body_md": fallback}
        return {"title": title, "body_md": reply}

    def _stream_weak_mode_answer(
        self,
        history: list[dict],
        research_mode: bool,
        *,
        context_notes: list[str] | None,
    ) -> Iterator[str]:
        title = "深度调研" if research_mode else None
        if not self.llm.is_configured():
            fallback = (
                "当前还没有可用的大模型配置，因此我暂时无法继续生成回答。"
                "请先在设置页补充 `WORKBENCH_LLM_API_KEY`、`WORKBENCH_LLM_BASE_URL` "
                "和 `WORKBENCH_LLM_MODEL` 对应的配置。"
            )
            if research_mode:
                fallback += "\n\n深度调研模式没有拿到新结论，你可以检查模型配置后重新发起请求。"
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
                "当前这次回答在调用大模型时失败了，我先保留现有会话内容。"
                f"错误信息：{exc}"
            )
            if research_mode:
                fallback += "\n\n深度调研模式没有拿到新结论，你可以检查模型配置后重新发起请求。"
            for chunk in self._chunk_text(fallback):
                yield chunk
            return {"title": title, "body_md": fallback}

    def _chunk_text(self, text: str, size: int = 48) -> Iterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]

    def sse_event(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

from __future__ import annotations

from collections.abc import Iterator

from app.services.llm_service import GROUNDING_DISCLOSURE_NOTE, LLMService
from app.services.search_service import SearchService


NORMAL_GROUNDED_EVIDENCE_LIMIT = 3
RESEARCH_GROUNDED_EVIDENCE_LIMIT = 5
GROUNDING_STREAM_INTERRUPTED_NOTE = "补充说明：本次基于项目资料的生成在中途被中断，以上内容可能不完整。"


class GroundedGenerationService:
    def __init__(
        self,
        *,
        search_service: SearchService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.search = search_service or SearchService()
        self.llm = llm_service or LLMService()

    def retrieve_evidence(self, *, project_id: str, query: str, research_mode: bool) -> list[dict]:
        apply_rerank = True if research_mode else self.search.should_rerank_query(query)
        limit = RESEARCH_GROUNDED_EVIDENCE_LIMIT if research_mode else NORMAL_GROUNDED_EVIDENCE_LIMIT
        retrieved = self.search.retrieve_project_evidence(
            project_id,
            query,
            limit=limit,
            apply_rerank=apply_rerank,
        )
        return self._build_evidence_pack(retrieved)

    def generate_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
    ) -> dict:
        try:
            grounded = self.llm.generate_grounded_reply(
                conversation=history,
                evidence_pack=evidences,
                research_mode=research_mode,
            )
        except RuntimeError:
            grounded = self._build_grounded_failure_answer(query=query, evidences=evidences)
        return self._build_answer_payload(grounded=grounded, research_mode=research_mode)

    def stream_generate_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
    ) -> Iterator[str]:
        streamed_chunks: list[str] = []
        try:
            iterator = self.llm.stream_grounded_reply(
                conversation=history,
                evidence_pack=evidences,
                research_mode=research_mode,
            )
            while True:
                try:
                    chunk = next(iterator)
                except StopIteration as stop:
                    grounded = stop.value
                    break
                streamed_chunks.append(chunk)
                yield chunk
        except RuntimeError:
            if streamed_chunks:
                partial_answer = "".join(streamed_chunks).strip()
                interrupted_answer = self._append_stream_interruption_note(partial_answer)
                delta = interrupted_answer[len(partial_answer) :]
                for chunk in self._chunk_text(delta):
                    yield chunk
                grounded = {
                    "answer_md": interrupted_answer,
                    "used_general_knowledge": False,
                    "evidence_status": "grounded",
                }
            else:
                grounded = self._build_grounded_failure_answer(query=query, evidences=evidences)
                for chunk in self._chunk_text(grounded["answer_md"]):
                    yield chunk
        return self._build_answer_payload(grounded=grounded, research_mode=research_mode)

    def _build_evidence_pack(self, evidences: list[dict]) -> list[dict]:
        return [
            {
                **item,
                "evidence_index": index,
            }
            for index, item in enumerate(evidences, start=1)
        ]

    def _build_answer_payload(self, *, grounded: dict, research_mode: bool) -> dict:
        return {
            "title": "调研结论" if research_mode else None,
            "answer_md": grounded["answer_md"].strip(),
            "source_mode": "project_grounded",
            "evidence_status": grounded["evidence_status"],
            "disclosure_note": self._build_disclosure_note(grounded),
        }

    def _build_grounded_failure_answer(self, *, query: str, evidences: list[dict]) -> dict:
        return {
            "answer_md": (
                f"当前项目已命中 {len(evidences)} 条与“{query}”相关的资料，"
                "但这次基于证据的生成失败了。你可以先查看下方来源，或稍后重试。"
            ),
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        }

    def _append_stream_interruption_note(self, answer_md: str) -> str:
        normalized = answer_md.rstrip()
        separator = "\n\n" if normalized else ""
        return f"{normalized}{separator}{GROUNDING_STREAM_INTERRUPTED_NOTE}".strip()

    def _build_disclosure_note(self, grounded: dict) -> str | None:
        if grounded.get("used_general_knowledge"):
            return GROUNDING_DISCLOSURE_NOTE
        return None

    def _chunk_text(self, text: str, size: int = 48) -> Iterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]

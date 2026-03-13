from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar

from app.services.llm_service import GROUNDING_DISCLOSURE_NOTE, LLMService
from app.services.search_service import SearchService


NORMAL_GROUNDED_EVIDENCE_LIMIT = 3
RESEARCH_GROUNDED_EVIDENCE_LIMIT = 5
GROUNDING_STREAM_INTERRUPTED_NOTE = (
    "\u8865\u5145\u8bf4\u660e\uff1a\u672c\u6b21\u57fa\u4e8e\u9879\u76ee\u8d44\u6599\u7684\u751f\u6210"
    "\u5728\u4e2d\u9014\u88ab\u4e2d\u65ad\uff0c\u4ee5\u4e0a\u5185\u5bb9\u53ef\u80fd\u4e0d\u5b8c\u6574\u3002"
)


class GroundedGenerationService:
    def __init__(
        self,
        *,
        search_service: SearchService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.search = search_service or SearchService()
        self.llm = llm_service or LLMService()
        self._last_retrieval_diagnostics: ContextVar[dict | None] = ContextVar(
            "grounded_generation_last_retrieval_diagnostics",
            default=None,
        )

    def retrieve_evidence(
        self,
        *,
        project_id: str,
        query: str,
        research_mode: bool,
        history: list[dict] | None = None,
    ) -> list[dict]:
        apply_rerank = True if research_mode else self.search.should_rerank_query(query)
        limit = RESEARCH_GROUNDED_EVIDENCE_LIMIT if research_mode else NORMAL_GROUNDED_EVIDENCE_LIMIT
        retrieved, diagnostics = self.search.retrieve_project_evidence_with_diagnostics(
            project_id,
            query,
            limit=limit,
            apply_rerank=apply_rerank,
            history=history,
        )
        self._last_retrieval_diagnostics.set(diagnostics)
        return self._build_evidence_pack(retrieved)

    @property
    def last_retrieval_diagnostics(self) -> dict | None:
        return self._last_retrieval_diagnostics.get()

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
            "title": "\u8c03\u7814\u7ed3\u8bba" if research_mode else None,
            "answer_md": grounded["answer_md"].strip(),
            "source_mode": "project_grounded",
            "evidence_status": grounded["evidence_status"],
            "disclosure_note": self._build_disclosure_note(grounded),
        }

    def _build_grounded_failure_answer(self, *, query: str, evidences: list[dict]) -> dict:
        return {
            "answer_md": (
                f"\u5f53\u524d\u9879\u76ee\u5df2\u547d\u4e2d {len(evidences)} \u6761\u4e0e"
                f"\u201c{query}\u201d\u76f8\u5173\u7684\u8d44\u6599\uff0c"
                "\u4f46\u8fd9\u6b21\u57fa\u4e8e\u8bc1\u636e\u7684\u751f\u6210\u5931\u8d25\u4e86\u3002"
                "\u4f60\u53ef\u4ee5\u5148\u67e5\u770b\u4e0b\u65b9\u6765\u6e90\uff0c\u6216\u7a0d\u540e\u91cd\u8bd5\u3002"
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

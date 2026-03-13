from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar
import re

from app.services.llm_service import GROUNDING_DISCLOSURE_NOTE, LLMService
from app.services.search_service import SearchService


NORMAL_GROUNDED_EVIDENCE_LIMIT = 3
RESEARCH_GROUNDED_EVIDENCE_LIMIT = 5
EVIDENCE_SELECTION_MULTIPLIER = 2
MAX_COMPRESSED_EXCERPT_LENGTH = 280
MIN_ACCEPTED_TOP_SCORE = 2.2
MIN_ACCEPTED_SECOND_PASS_TOP_SCORE = 3.0
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
        final_limit = RESEARCH_GROUNDED_EVIDENCE_LIMIT if research_mode else NORMAL_GROUNDED_EVIDENCE_LIMIT
        retrieval_limit = max(final_limit * EVIDENCE_SELECTION_MULTIPLIER, final_limit + 2)
        retrieved, diagnostics = self.search.retrieve_project_evidence_with_diagnostics(
            project_id,
            query,
            limit=retrieval_limit,
            apply_rerank=apply_rerank,
            history=history,
        )
        if not self._should_accept_grounded_candidate(query=query, evidences=retrieved, diagnostics=diagnostics):
            empty_selection = {
                "input_candidate_count": len(retrieved),
                "selected_candidate_count": 0,
                "selector_applied": False,
                "rejection_reason": "low_confidence_delivery_candidate",
                "items": [],
            }
            empty_compression = {
                "input_evidence_count": 0,
                "compressed_evidence_count": 0,
                "items": [],
            }
            augmented_diagnostics = self._augment_retrieval_diagnostics(
                diagnostics=diagnostics,
                selected=[],
                selection_diagnostics=empty_selection,
                compression_diagnostics=empty_compression,
            )
            self._last_retrieval_diagnostics.set(augmented_diagnostics)
            return []
        selected, selection_diagnostics = self._select_evidence_candidates(
            query=query,
            evidences=retrieved,
            limit=final_limit,
        )
        packed, compression_diagnostics = self._build_evidence_pack(query=query, evidences=selected)
        augmented_diagnostics = self._augment_retrieval_diagnostics(
            diagnostics=diagnostics,
            selected=selected,
            selection_diagnostics=selection_diagnostics,
            compression_diagnostics=compression_diagnostics,
        )
        self._last_retrieval_diagnostics.set(augmented_diagnostics)
        return packed

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

    def _build_evidence_pack(self, *, query: str, evidences: list[dict]) -> tuple[list[dict], dict]:
        packed: list[dict] = []
        compressed_items: list[dict] = []
        for index, item in enumerate(evidences, start=1):
            compressed_excerpt, compression_reason = self._compress_evidence_excerpt(query=query, item=item)
            packed.append(
                {
                    **item,
                    "excerpt": compressed_excerpt,
                    "source_excerpt": item.get("excerpt", ""),
                    "compression_reason": compression_reason,
                    "evidence_index": index,
                }
            )
            compressed_items.append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "section_type": item.get("section_type", "body"),
                    "compression_reason": compression_reason,
                    "original_excerpt_length": len(item.get("excerpt", "")),
                    "compressed_excerpt_length": len(compressed_excerpt),
                }
            )
        return (
            packed,
            {
                "input_evidence_count": len(evidences),
                "compressed_evidence_count": len(packed),
                "items": compressed_items,
            },
        )

    def _augment_retrieval_diagnostics(
        self,
        *,
        diagnostics: dict,
        selected: list[dict],
        selection_diagnostics: dict,
        compression_diagnostics: dict,
    ) -> dict:
        final = dict(diagnostics.get("final", {}))
        final.update(
            {
                "selected_evidence_count": len(selected),
                "source_count": len({item["source_id"] for item in selected}),
                "returned_hit_count": len(selected),
            }
        )
        return {
            **diagnostics,
            "final": final,
            "selection": selection_diagnostics,
            "compression": compression_diagnostics,
        }

    def _select_evidence_candidates(self, *, query: str, evidences: list[dict], limit: int) -> tuple[list[dict], dict]:
        if len(evidences) <= limit:
            return (
                evidences[:limit],
                {
                    "input_candidate_count": len(evidences),
                    "selected_candidate_count": min(len(evidences), limit),
                    "selector_applied": False,
                    "items": [
                        {
                            "chunk_id": item.get("chunk_id"),
                            "selector_score": round(float(item.get("relevance_score", 0.0)), 3),
                            "section_type": item.get("section_type", "body"),
                        }
                        for item in evidences[:limit]
                    ],
                },
            )

        ranked = []
        for item in evidences:
            ranked.append(
                {
                    **item,
                    "_selector_score": self._selector_score(query=query, item=item),
                }
            )
        ranked.sort(key=lambda item: (item["_selector_score"], float(item.get("relevance_score", 0.0))), reverse=True)

        selected: list[dict] = []
        used_chunk_ids: set[str] = set()
        used_context_keys: set[tuple[str, str, str]] = set()
        for item in ranked:
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id and chunk_id in used_chunk_ids:
                continue
            if selected:
                context_key = (
                    str(item.get("source_id") or ""),
                    str(item.get("heading_path") or ""),
                    str(item.get("section_type") or "body"),
                )
                if context_key in used_context_keys and len(selected) + 1 < limit:
                    continue
            selected.append({key: value for key, value in item.items() if key != "_selector_score"})
            if chunk_id:
                used_chunk_ids.add(chunk_id)
            used_context_keys.add(
                (
                    str(item.get("source_id") or ""),
                    str(item.get("heading_path") or ""),
                    str(item.get("section_type") or "body"),
                )
            )
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            for item in ranked:
                if len(selected) >= limit:
                    break
                chunk_id = str(item.get("chunk_id") or "")
                if chunk_id and chunk_id in used_chunk_ids:
                    continue
                selected.append({key: value for key, value in item.items() if key != "_selector_score"})
                if chunk_id:
                    used_chunk_ids.add(chunk_id)

        return (
            selected[:limit],
            {
                "input_candidate_count": len(evidences),
                "selected_candidate_count": min(len(selected), limit),
                "selector_applied": True,
                "items": [
                    {
                        "chunk_id": item.get("chunk_id"),
                        "selector_score": round(float(item["_selector_score"]), 3),
                        "section_type": item.get("section_type", "body"),
                    }
                    for item in ranked[:limit]
                ],
            },
        )

    def _should_accept_grounded_candidate(self, *, query: str, evidences: list[dict], diagnostics: dict) -> bool:
        if not evidences:
            return False

        top_score = max(float(item.get("relevance_score", 0.0)) for item in evidences)
        first_pass = diagnostics.get("first_pass", {})
        term_coverage_ratio = float(first_pass.get("term_coverage_ratio", 0.0) or 0.0)
        field_or_proposition_hits = any(
            str(item.get("section_type") or "body") in {"field", "proposition"} for item in evidences[:5]
        )

        if top_score < MIN_ACCEPTED_TOP_SCORE:
            return False
        if diagnostics.get("triggered_second_pass") and top_score < MIN_ACCEPTED_SECOND_PASS_TOP_SCORE and not field_or_proposition_hits:
            return False
        if term_coverage_ratio == 0 and top_score < (MIN_ACCEPTED_TOP_SCORE + 0.4) and not field_or_proposition_hits:
            return False
        if self.search._query_looks_contextual(query) and top_score < MIN_ACCEPTED_SECOND_PASS_TOP_SCORE and not field_or_proposition_hits:
            return False
        return True

    def _selector_score(self, *, query: str, item: dict) -> float:
        terms = [term for term in self.search.repository.build_query_terms(query) if len(term) >= 2]
        normalized_query = " ".join(query.split()).lower()
        section_type = str(item.get("section_type") or "body")
        heading_path = str(item.get("heading_path") or "").lower()
        field_label = str(item.get("field_label") or "").lower()
        proposition_type = str(item.get("proposition_type") or "").lower()
        normalized_text = str(item.get("normalized_text") or item.get("excerpt") or "").lower()
        excerpt = str(item.get("excerpt") or "").lower()

        score = float(item.get("relevance_score", 0.0))
        score += 0.45 * sum(1 for term in terms if term in normalized_text)
        score += 0.2 * sum(1 for term in terms if term in excerpt)

        if heading_path:
            score += 0.35 * sum(1 for term in terms if term in heading_path)
        if field_label:
            score += 0.65 * sum(1 for term in terms if term in field_label)

        if section_type == "field":
            score += 2.0
            if field_label and field_label in normalized_query:
                score += 1.2
        elif section_type == "proposition":
            score += 1.5
            if proposition_type and proposition_type in normalized_query:
                score += 0.6
        elif section_type == "body" and heading_path:
            score += 0.4
        elif section_type == "heading":
            score += 0.2

        if normalized_query and normalized_query in normalized_text:
            score += 1.2

        return round(score, 3)

    def _compress_evidence_excerpt(self, *, query: str, item: dict) -> tuple[str, str]:
        normalized_text = str(item.get("normalized_text") or item.get("excerpt") or "").strip()
        if not normalized_text:
            return "", "empty"

        section_type = str(item.get("section_type") or "body")
        if section_type in {"field", "proposition"}:
            return self._trim_excerpt(normalized_text), section_type

        sentences = self._split_sentences(normalized_text)
        if not sentences:
            return self._trim_excerpt(normalized_text), "raw_excerpt"

        scored_sentences = [
            (
                self._sentence_relevance(query=query, sentence=sentence, item=item),
                sentence,
            )
            for sentence in sentences
        ]
        scored_sentences.sort(key=lambda entry: (entry[0], len(entry[1])), reverse=True)

        selected: list[str] = []
        total_length = 0
        for score, sentence in scored_sentences:
            if score <= 0 and selected:
                continue
            sentence_length = len(sentence)
            if selected and total_length + sentence_length + 1 > MAX_COMPRESSED_EXCERPT_LENGTH:
                continue
            selected.append(sentence)
            total_length += sentence_length + 1
            if len(selected) >= 2:
                break

        if not selected:
            return self._trim_excerpt(normalized_text), "raw_excerpt"
        return self._trim_excerpt(" ".join(selected)), "sentence_focus"

    def _sentence_relevance(self, *, query: str, sentence: str, item: dict) -> float:
        terms = [term for term in self.search.repository.build_query_terms(query) if len(term) >= 2]
        normalized_sentence = sentence.lower()
        normalized_query = " ".join(query.split()).lower()
        score = 0.0
        score += 1.0 * sum(1 for term in terms if term in normalized_sentence)
        if normalized_query and normalized_query in normalized_sentence:
            score += 2.0

        heading_path = str(item.get("heading_path") or "").lower()
        if heading_path:
            score += 0.3 * sum(1 for term in terms if term in heading_path)
        if item.get("field_label"):
            score += 0.25
        if item.get("proposition_type"):
            score += 0.2
        return round(score, 3)

    def _split_sentences(self, text: str) -> list[str]:
        normalized = " ".join(text.split()).strip()
        if not normalized:
            return []
        parts = re.split(r"(?<=[。！？；;.!?])\s+|(?<=[。！？；;.!?])", normalized)
        sentences: list[str] = []
        for part in parts:
            sentence = part.strip()
            if len(sentence) < 12:
                continue
            sentences.append(sentence)
        return sentences

    def _trim_excerpt(self, text: str) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= MAX_COMPRESSED_EXCERPT_LENGTH:
            return normalized
        return f"{normalized[: MAX_COMPRESSED_EXCERPT_LENGTH - 1].rstrip()}…"

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

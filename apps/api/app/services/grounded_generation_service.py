from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar
import logging
import re

from app.services.llm_service import GROUNDING_DISCLOSURE_NOTE, LLMService
from app.services.search_service import SearchService


NORMAL_GROUNDED_EVIDENCE_LIMIT = 3
RESEARCH_GROUNDED_EVIDENCE_LIMIT = 5
FACTOID_GROUNDED_EVIDENCE_LIMIT = 2
EVIDENCE_SELECTION_MULTIPLIER = 2
MAX_COMPRESSED_EXCERPT_LENGTH = 280
MIN_ACCEPTED_TOP_SCORE = 2.2
MIN_ACCEPTED_SECOND_PASS_TOP_SCORE = 3.0
GROUNDING_STREAM_INTERRUPTED_NOTE = (
    "\u8865\u5145\u8bf4\u660e\uff1a\u672c\u6b21\u57fa\u4e8e\u9879\u76ee\u8d44\u6599\u7684\u751f\u6210"
    "\u5728\u4e2d\u9014\u88ab\u4e2d\u65ad\uff0c\u4ee5\u4e0a\u5185\u5bb9\u53ef\u80fd\u4e0d\u5b8c\u6574\u3002"
)

logger = logging.getLogger(__name__)


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
        final_limit = self._target_evidence_limit(query=query, research_mode=research_mode)
        retrieval_limit = max(final_limit * EVIDENCE_SELECTION_MULTIPLIER, final_limit + 2)
        retrieved, diagnostics = self.search.retrieve_project_evidence_with_diagnostics(
            project_id,
            query,
            limit=retrieval_limit,
            apply_rerank=apply_rerank,
            history=history,
        )
        packed, augmented_diagnostics = self.prepare_agent_evidence(
            query=query,
            project_hits=retrieved,
            project_diagnostics=diagnostics,
            research_mode=research_mode,
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
        context_notes: list[str] | None = None,
    ) -> dict:
        evidence_mode = self._classify_evidence_mode(evidences)
        try:
            grounded = self.llm.generate_grounded_reply(
                conversation=history,
                evidence_pack=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
                evidence_mode=evidence_mode,
            )
        except RuntimeError as exc:
            logger.warning("Grounded answer generation failed: %s", exc)
            grounded = self._recover_grounded_answer(
                history=history,
                query=query,
                evidences=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
                evidence_mode=evidence_mode,
            )
        return self._build_answer_payload(
            grounded=grounded,
            research_mode=research_mode,
            evidences=evidences,
        )

    def stream_generate_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
        context_notes: list[str] | None = None,
    ) -> Iterator[str]:
        evidence_mode = self._classify_evidence_mode(evidences)
        streamed_chunks: list[str] = []
        try:
            iterator = self.llm.stream_grounded_reply(
                conversation=history,
                evidence_pack=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
                evidence_mode=evidence_mode,
            )
            while True:
                try:
                    chunk = next(iterator)
                except StopIteration as stop:
                    grounded = stop.value
                    break
                streamed_chunks.append(chunk)
                yield chunk
        except RuntimeError as exc:
            logger.warning("Grounded streamed generation failed: %s", exc)
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
                grounded = self._recover_grounded_answer(
                    history=history,
                    query=query,
                    evidences=evidences,
                    research_mode=research_mode,
                    context_notes=context_notes,
                    evidence_mode=evidence_mode,
                )
                for chunk in self._chunk_text(grounded["answer_md"]):
                    yield chunk
        return self._build_answer_payload(
            grounded=grounded,
            research_mode=research_mode,
            evidences=evidences,
        )

    def prepare_agent_evidence(
        self,
        *,
        query: str,
        project_hits: list[dict],
        project_diagnostics: dict,
        research_mode: bool,
        external_hits: list[dict] | None = None,
    ) -> tuple[list[dict], dict]:
        final_limit = self._target_evidence_limit(query=query, research_mode=research_mode)
        accepted_project_hits = project_hits
        selection_diagnostics: dict
        compression_diagnostics: dict

        if project_hits and not self._should_accept_grounded_candidate(
            query=query,
            evidences=project_hits,
            diagnostics=project_diagnostics,
        ):
            accepted_project_hits = []
            selection_diagnostics = {
                "input_candidate_count": len(project_hits),
                "selected_candidate_count": 0,
                "selector_applied": False,
                "rejection_reason": "low_confidence_delivery_candidate",
                "items": [],
            }
            compression_diagnostics = {
                "input_evidence_count": 0,
                "compressed_evidence_count": 0,
                "items": [],
            }
        else:
            selection_diagnostics = {}
            compression_diagnostics = {}

        external_candidates = self._limit_external_candidates(
            query=query,
            project_hits=accepted_project_hits,
            external_hits=external_hits or [],
            limit=final_limit,
            research_mode=research_mode,
        )
        candidate_pool = [*accepted_project_hits, *external_candidates]
        if not candidate_pool:
            if not selection_diagnostics:
                selection_diagnostics = {
                    "input_candidate_count": 0,
                    "selected_candidate_count": 0,
                    "selector_applied": False,
                    "items": [],
                }
            if not compression_diagnostics:
                compression_diagnostics = {
                    "input_evidence_count": 0,
                    "compressed_evidence_count": 0,
                    "items": [],
                }
            return (
                [],
                self._augment_retrieval_diagnostics(
                    diagnostics=project_diagnostics,
                    selected=[],
                    selection_diagnostics=selection_diagnostics,
                    compression_diagnostics=compression_diagnostics,
                ),
            )

        selected, selection_diagnostics = self._select_evidence_candidates(
            query=query,
            evidences=candidate_pool,
            limit=final_limit,
        )
        packed, compression_diagnostics = self._build_evidence_pack(query=query, evidences=selected)
        augmented = self._augment_retrieval_diagnostics(
            diagnostics=project_diagnostics,
            selected=selected,
            selection_diagnostics=selection_diagnostics,
            compression_diagnostics=compression_diagnostics,
        )
        augmented["final"]["external_source_count"] = len(
            {item["canonical_uri"] for item in selected if item.get("source_kind") == "external_web"}
        )
        return packed, augmented

    def _limit_external_candidates(
        self,
        *,
        query: str,
        project_hits: list[dict],
        external_hits: list[dict],
        limit: int,
        research_mode: bool,
    ) -> list[dict]:
        if not external_hits:
            return []
        if not project_hits:
            return external_hits[:limit]

        project_haystack = " ".join(
            " ".join(
                str(value or "")
                for value in (
                    item.get("source_title"),
                    item.get("heading_path"),
                    item.get("field_label"),
                    item.get("normalized_text"),
                    item.get("excerpt"),
                )
            ).lower()
            for item in project_hits[:4]
        )
        ranked_external: list[dict] = []
        for item in external_hits:
            overlap = 0
            for term in [term for term in self.search.repository.build_query_terms(query) if len(term) >= 2]:
                if term in project_haystack and term in str(item.get("normalized_text") or "").lower():
                    overlap += 1
            ranked_external.append({**item, "_project_overlap": overlap})
        ranked_external.sort(
            key=lambda item: (float(item.get("relevance_score", 0.0)), -int(item["_project_overlap"])),
            reverse=True,
        )
        external_budget = 1 if not research_mode else 2
        if len(project_hits) >= limit:
            external_budget = 0
        elif len(project_hits) >= max(2, limit - 1):
            external_budget = 0 if not research_mode else 1
        trimmed: list[dict] = []
        for item in ranked_external:
            if len(trimmed) >= external_budget:
                break
            trimmed.append({key: value for key, value in item.items() if key != "_project_overlap"})
        return trimmed

    def _build_evidence_pack(self, *, query: str, evidences: list[dict]) -> tuple[list[dict], dict]:
        packed: list[dict] = []
        compressed_items: list[dict] = []
        for index, item in enumerate(evidences, start=1):
            compressed_excerpt, compression_reason = self._compress_evidence_excerpt(query=query, item=item)
            llm_excerpt = self._build_llm_excerpt(query=query, item=item, compressed_excerpt=compressed_excerpt)
            packed.append(
                {
                    **item,
                    "excerpt": compressed_excerpt,
                    "source_excerpt": item.get("excerpt", ""),
                    "llm_excerpt": llm_excerpt,
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
                    "llm_excerpt_length": len(llm_excerpt),
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
                "source_count": len(
                    {
                        item["source_id"] if item.get("source_kind") != "external_web" else item.get("canonical_uri")
                        for item in selected
                    }
                ),
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
        pass_diagnostics = diagnostics.get("effective_pass") or diagnostics.get("first_pass", {})
        term_coverage_ratio = float(pass_diagnostics.get("term_coverage_ratio", 0.0) or 0.0)
        field_or_proposition_hits = any(
            str(item.get("section_type") or "body") in {"field", "proposition"} for item in evidences[:5]
        )
        evidence_haystack = " ".join(
            " ".join(
                str(value or "")
                for value in (
                    item.get("source_title"),
                    item.get("heading_path"),
                    item.get("field_label"),
                    item.get("normalized_text"),
                    item.get("excerpt"),
                )
            ).lower()
            for item in evidences[:5]
        )
        query_terms = [term for term in self.search.repository.build_query_terms(query) if len(term) >= 4]
        matched_terms = {term for term in query_terms if term in evidence_haystack}
        strong_semantic_overlap = (
            term_coverage_ratio >= 0.45
            and top_score >= 0.5
            and len(matched_terms) >= min(3, max(2, len(query_terms) // 2 or 2))
        )
        if field_or_proposition_hits and top_score >= 1.8:
            return True

        if top_score < MIN_ACCEPTED_TOP_SCORE:
            if strong_semantic_overlap:
                return True
            return False
        if diagnostics.get("triggered_second_pass") and top_score < MIN_ACCEPTED_SECOND_PASS_TOP_SCORE and not field_or_proposition_hits:
            if strong_semantic_overlap:
                return True
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
        if item.get("source_kind") != "external_web":
            score += 1.0
        else:
            score -= 0.35
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
            return self._trim_excerpt(normalized_text, max_length=self._excerpt_character_limit(query=query, item=item)), section_type

        sentences = self._split_sentences(normalized_text)
        if not sentences:
            return self._trim_excerpt(normalized_text, max_length=self._excerpt_character_limit(query=query, item=item)), "raw_excerpt"

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
            max_length = self._excerpt_character_limit(query=query, item=item)
            if selected and total_length + sentence_length + 1 > max_length:
                continue
            selected.append(sentence)
            total_length += sentence_length + 1
            if len(selected) >= self._target_sentence_count(query=query, item=item):
                break

        if not selected:
            return self._trim_excerpt(normalized_text, max_length=self._excerpt_character_limit(query=query, item=item)), "raw_excerpt"
        return self._trim_excerpt(" ".join(selected), max_length=self._excerpt_character_limit(query=query, item=item)), "sentence_focus"

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

    def _trim_excerpt(self, text: str, *, max_length: int = MAX_COMPRESSED_EXCERPT_LENGTH) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 1].rstrip()}…"

    def _build_llm_excerpt(self, *, query: str, item: dict, compressed_excerpt: str) -> str:
        section_type = str(item.get("section_type") or "body")
        field_label = " ".join(str(item.get("field_label") or "").split()).strip()
        if section_type == "field" and field_label:
            if compressed_excerpt.startswith(field_label):
                return self._trim_excerpt(compressed_excerpt, max_length=140)
            return self._trim_excerpt(f"{field_label}: {compressed_excerpt}", max_length=140)
        return self._trim_excerpt(compressed_excerpt, max_length=self._llm_excerpt_character_limit(query=query, item=item))

    def _target_evidence_limit(self, *, query: str, research_mode: bool) -> int:
        if research_mode:
            return RESEARCH_GROUNDED_EVIDENCE_LIMIT
        if self._query_looks_factoid(query) and not self.search.should_rerank_query(query):
            return FACTOID_GROUNDED_EVIDENCE_LIMIT
        return NORMAL_GROUNDED_EVIDENCE_LIMIT

    def _target_sentence_count(self, *, query: str, item: dict) -> int:
        if str(item.get("section_type") or "body") in {"field", "proposition"}:
            return 1
        if self._query_looks_factoid(query):
            return 1
        return 2

    def _excerpt_character_limit(self, *, query: str, item: dict) -> int:
        section_type = str(item.get("section_type") or "body")
        if section_type == "field":
            return 120
        if section_type == "proposition":
            return 150
        if self._query_looks_factoid(query):
            return 160
        return 220

    def _llm_excerpt_character_limit(self, *, query: str, item: dict) -> int:
        if str(item.get("section_type") or "body") in {"field", "proposition"}:
            return 140
        if self._query_looks_factoid(query):
            return 130
        return 180

    def _query_looks_factoid(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        if not normalized:
            return False

        complex_markers = (
            "\u4e3a\u4ec0\u4e48",
            "\u4e3a\u4f55",
            "\u539f\u56e0",
            "\u5982\u4f55",
            "\u600e\u4e48",
            "\u600e\u6837",
            "\u6bd4\u8f83",
            "\u533a\u522b",
            "\u5dee\u5f02",
            "\u4f18\u7f3a\u70b9",
            "\u53ef\u884c",
            "\u5efa\u8bae",
            "\u5206\u6790",
            "\u603b\u7ed3",
            "\u89e3\u91ca",
            "\u65b9\u6848",
            "\u601d\u8def",
        )
        if any(marker in normalized for marker in complex_markers):
            return False

        strong_factoid_markers = (
            "\u540d\u79f0",
            "\u9898\u76ee",
            "\u6807\u9898",
            "\u4f5c\u8005",
            "\u65f6\u95f4",
            "\u65e5\u671f",
            "\u9ed8\u8ba4",
            "\u7248\u672c",
            "\u7f16\u53f7",
            "\u5730\u5740",
            "\u5730\u70b9",
            "\u4f4d\u7f6e",
            "\u8c01",
            "\u4f55\u65f6",
            "\u54ea\u91cc",
            "\u591a\u5c11",
            "\u54ea\u4e2a",
            "\u54ea\u79cd",
        )
        if any(marker in normalized for marker in strong_factoid_markers):
            return True

        if "\u4ec0\u4e48" in normalized:
            return len(normalized) <= 12 and "\u4ec0\u4e48\u662f" not in normalized

        return False

    def _build_answer_payload(
        self,
        *,
        grounded: dict,
        research_mode: bool,
        evidences: list[dict],
    ) -> dict:
        return {
            "title": "\u8c03\u7814\u7ed3\u8bba" if research_mode else None,
            "answer_md": grounded["answer_md"].strip(),
            "source_mode": "project_grounded",
            "evidence_status": grounded["evidence_status"],
            "disclosure_note": self._build_disclosure_note(grounded, evidences=evidences),
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
            "generation_failed": True,
        }

    def _append_stream_interruption_note(self, answer_md: str) -> str:
        normalized = answer_md.rstrip()
        separator = "\n\n" if normalized else ""
        return f"{normalized}{separator}{GROUNDING_STREAM_INTERRUPTED_NOTE}".strip()

    def _recover_grounded_answer(
        self,
        *,
        history: list[dict],
        query: str,
        evidences: list[dict],
        research_mode: bool,
        context_notes: list[str] | None,
        evidence_mode: str,
    ) -> dict:
        try:
            recovered = self.llm.generate_grounded_reply_fallback(
                conversation=history,
                evidence_pack=evidences,
                research_mode=research_mode,
                context_notes=context_notes,
                evidence_mode=evidence_mode,
            )
        except RuntimeError as fallback_exc:
            logger.warning("Grounded fallback generation failed: %s", fallback_exc)
            return self._build_grounded_failure_answer(query=query, evidences=evidences)
        recovered["recovered_from_generation_failure"] = True
        return recovered

    def _build_disclosure_note(self, grounded: dict, *, evidences: list[dict]) -> str | None:
        notes: list[str] = []
        if grounded.get("generation_failed"):
            return None
        evidence_mode = self._classify_evidence_mode(evidences)
        if evidence_mode == "web":
            notes.append("\u8865\u5145\u8bf4\u660e\uff1a\u4ee5\u4e0b\u7ed3\u8bba\u4e3b\u8981\u57fa\u4e8e\u8054\u7f51\u8865\u5145\u6765\u6e90\uff0c\u5e76\u7ed3\u5408\u5f53\u524d\u4f1a\u8bdd\u4e0a\u4e0b\u6587\u6574\u7406\u3002")
        elif evidence_mode == "hybrid":
            notes.append("\u8865\u5145\u8bf4\u660e\uff1a\u4ee5\u4e0b\u7ed3\u8bba\u7efc\u5408\u4e86\u9879\u76ee\u8d44\u6599\u4e0e\u8054\u7f51\u8865\u5145\u6765\u6e90\u3002")
        if grounded.get("used_general_knowledge"):
            notes.append(GROUNDING_DISCLOSURE_NOTE)
        if not notes:
            return None
        return "\n".join(notes)

    def _classify_evidence_mode(self, evidences: list[dict]) -> str:
        has_project_evidence = any(item.get("source_kind") != "external_web" for item in evidences)
        has_web_evidence = any(item.get("source_kind") == "external_web" for item in evidences)
        if has_project_evidence and has_web_evidence:
            return "hybrid"
        if has_web_evidence:
            return "web"
        return "project"

    def _chunk_text(self, text: str, size: int = 48) -> Iterator[str]:
        for index in range(0, len(text), size):
            yield text[index : index + size]

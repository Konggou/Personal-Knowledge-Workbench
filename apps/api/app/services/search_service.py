from __future__ import annotations

import logging
from contextvars import ContextVar

from app.repositories.search_repository import SearchRepository
from app.services.llm_service import LLMService
from app.services.vector_store import VectorStore


COMPLEX_QUERY_KEYWORDS = (
    "\u6bd4\u8f83",
    "\u533a\u522b",
    "\u4f18\u7f3a\u70b9",
    "\u65b9\u6848",
    "\u8bc4\u4f30",
    "\u4e3a\u4ec0\u4e48",
    "\u5982\u4f55",
    "\u603b\u7ed3",
    "\u68b3\u7406",
    "\u63a8\u8350",
    "\u9002\u5408",
)
LOW_CONFIDENCE_TOP_SCORE = 2.2
VERY_LOW_CONFIDENCE_TOP_SCORE = 1.2
GENERIC_QUERY_TERMS = {
    "\u4ec0\u4e48",
    "\u600e\u4e48",
    "\u5982\u4f55",
    "\u73b0\u5728",
    "\u77e5\u9053",
    "\u6211\u7684",
    "\u4e86\u5417",
    "\u5462",
    "\u5417",
    "\u62a5\u544a",
}
QUERY_EXPANSION_RULES = {
    "\u9898\u76ee": (
        "\u5f00\u9898\u62a5\u544a \u9898\u76ee \u8bfe\u9898\u540d\u79f0 \u9879\u76ee\u540d\u79f0",
        "\u8bfe\u9898\u540d\u79f0 \u9879\u76ee\u540d\u79f0 \u9898\u76ee",
    ),
    "\u6807\u9898": ("\u9898\u76ee \u8bfe\u9898\u540d\u79f0 \u9879\u76ee\u540d\u79f0",),
    "\u9879\u76ee": ("\u9879\u76ee\u540d\u79f0 \u8bfe\u9898\u540d\u79f0 \u7814\u7a76\u4e3b\u9898",),
    "\u4f18\u5316": (
        "\u4f18\u5316\u5efa\u8bae \u53ef\u4ee5\u6539\u8fdb\u7684\u5730\u65b9 \u4e0d\u8db3 \u5b8c\u5584\u5efa\u8bae",
    ),
    "\u6539\u8fdb": (
        "\u4f18\u5316\u5efa\u8bae \u53ef\u4ee5\u6539\u8fdb\u7684\u5730\u65b9 \u4e0d\u8db3 \u5b8c\u5584\u5efa\u8bae",
    ),
}
FIELD_LABEL_HINTS = (
    "\u9898\u76ee",
    "\u6807\u9898",
    "\u9879\u76ee",
    "\u9879\u76ee\u540d\u79f0",
    "\u8bfe\u9898",
    "\u8bfe\u9898\u540d\u79f0",
    "\u7814\u7a76\u5185\u5bb9",
    "\u521b\u65b0\u70b9",
    "\u9884\u671f\u6210\u679c",
    "\u7ed3\u8bba",
    "\u5efa\u8bae",
)
FIELD_QUERY_GROUPS = {
    "\u9898\u76ee": ("\u9898\u76ee", "\u6807\u9898", "\u8bfe\u9898", "\u8bfe\u9898\u540d\u79f0", "\u9879\u76ee\u540d\u79f0"),
    "\u6807\u9898": ("\u9898\u76ee", "\u6807\u9898", "\u8bfe\u9898", "\u8bfe\u9898\u540d\u79f0", "\u9879\u76ee\u540d\u79f0"),
    "\u9879\u76ee": ("\u9879\u76ee", "\u9879\u76ee\u540d\u79f0", "\u8bfe\u9898", "\u8bfe\u9898\u540d\u79f0", "\u9898\u76ee"),
    "\u7814\u7a76\u5185\u5bb9": ("\u7814\u7a76\u5185\u5bb9",),
    "\u521b\u65b0\u70b9": ("\u521b\u65b0\u70b9",),
    "\u9884\u671f\u6210\u679c": ("\u9884\u671f\u6210\u679c",),
    "\u7ed3\u8bba": ("\u7ed3\u8bba",),
    "\u5efa\u8bae": ("\u5efa\u8bae", "\u4f18\u5316", "\u6539\u8fdb"),
    "\u4f18\u5316": ("\u5efa\u8bae", "\u4f18\u5316", "\u6539\u8fdb"),
    "\u6539\u8fdb": ("\u5efa\u8bae", "\u4f18\u5316", "\u6539\u8fdb"),
}
PROPOSITION_QUERY_GROUPS = {
    "identity": ("\u9898\u76ee", "\u6807\u9898", "\u9879\u76ee", "\u8bfe\u9898", "project name", "title"),
    "suggestion": ("\u5efa\u8bae", "\u4f18\u5316", "\u6539\u8fdb", "suggest", "recommend", "improve"),
    "conclusion": ("\u7ed3\u8bba", "\u603b\u7ed3", "\u53ef\u884c", "conclusion", "summary", "feasible"),
    "innovation": ("\u521b\u65b0", "\u521b\u65b0\u70b9", "innovation", "novel"),
    "outcome": ("\u9884\u671f\u6210\u679c", "\u6210\u679c", "outcome", "deliverable", "result"),
    "method": ("\u7814\u7a76\u5185\u5bb9", "\u5b9e\u65bd\u8ba1\u5212", "\u65b9\u6cd5", "\u65b9\u6848", "implementation", "method", "plan"),
}
FOLLOW_UP_QUERY_TERMS = {
    "\u73b0\u5728",
    "\u8fd9\u4e2a",
    "\u90a3\u4e2a",
    "\u8fd9\u4efd",
    "\u90a3\u4efd",
    "\u77e5\u9053",
    "\u4e86\u5417",
    "\u5b83",
    "\u8fd9\u9879",
    "\u90a3\u9879",
}
RETRIEVAL_CONTEXT_WINDOW = 3

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, *, llm_service: LLMService | None = None) -> None:
        self.repository = SearchRepository()
        self.vector_store = VectorStore()
        self.llm = llm_service or LLMService()
        self._last_retrieval_diagnostics: ContextVar[dict | None] = ContextVar(
            "search_last_retrieval_diagnostics",
            default=None,
        )

    def get_project_current_snapshot_id(self, project_id: str) -> str | None:
        return self.repository.get_project_current_snapshot_id(project_id)

    def should_rerank_query(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        if len(normalized) >= 40:
            return True
        return any(keyword in normalized for keyword in COMPLEX_QUERY_KEYWORDS)

    def retrieve_project_evidence(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 3,
        apply_rerank: bool = False,
        history: list[dict] | None = None,
    ) -> list[dict]:
        results, diagnostics = self.retrieve_project_evidence_with_diagnostics(
            project_id,
            query,
            limit=limit,
            apply_rerank=apply_rerank,
            history=history,
        )
        self._last_retrieval_diagnostics.set(diagnostics)
        return results

    def retrieve_project_evidence_with_diagnostics(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 3,
        apply_rerank: bool = False,
        history: list[dict] | None = None,
    ) -> tuple[list[dict], dict]:
        candidate_limit = max(limit * 4, 12)
        context_clues = self._collect_context_clues(query=query, history=history)
        merged = self._retrieve_ranked_hits(project_id=project_id, query=query, limit=candidate_limit)
        first_pass = self._analyze_hits(
            query=query,
            hits=merged,
            limit=limit,
            context_clues=context_clues,
        )
        retry_steps: list[dict] = []

        if first_pass["is_low_confidence"]:
            for strategy, retry_query in self._build_retry_queries(
                query=query,
                research_mode=limit > 3,
                context_clues=context_clues,
            ):
                retry_hits = self._retrieve_ranked_hits(
                    project_id=project_id,
                    query=retry_query,
                    limit=candidate_limit,
                )
                retry_analysis = self._analyze_hits(
                    query=retry_query,
                    hits=retry_hits,
                    limit=limit,
                    context_clues=context_clues,
                )
                retry_steps.append(
                    {
                        "strategy": strategy,
                        "query": retry_query,
                        "hit_count": retry_analysis["hit_count"],
                        "top_score": retry_analysis["top_score"],
                    }
                )
                merged = self._merge_hit_batches(
                    primary=merged,
                    secondary=retry_hits,
                    limit=candidate_limit,
                )

        if apply_rerank:
            results = self._rerank_hits(query=query, hits=merged, limit=limit)
        else:
            results = merged[:limit]

        diagnostics = {
            "original_query": query,
            "context_clues": context_clues,
            "first_pass": first_pass,
            "triggered_second_pass": bool(retry_steps),
            "retry_steps": retry_steps,
            "final": {
                "hit_count": len(merged),
                "source_count": len({item["source_id"] for item in results}),
                "grounded_candidate": bool(results),
                "returned_hit_count": len(results),
            },
        }
        logger.debug("retrieval diagnostics: %s", diagnostics)
        self._last_retrieval_diagnostics.set(diagnostics)
        return results, diagnostics

    @property
    def last_retrieval_diagnostics(self) -> dict | None:
        return self._last_retrieval_diagnostics.get()

    def search(self, *, scope: str, query: str, project_id: str | None = None, limit: int = 10) -> dict:
        lexical_results = self._score_chunks(
            chunks=self.repository.get_latest_chunks(scope=scope, project_id=project_id),
            query=query,
            limit=max(limit * 3, 18),
        )
        semantic_results = self.vector_store.search(
            query=query,
            project_id=project_id if scope == "project" else None,
            limit=max(limit * 3, 18),
        )
        results = self._merge_ranked_hits(
            semantic_results=semantic_results,
            lexical_results=lexical_results,
            limit=limit,
        )
        return {
            "scope": scope,
            "query": query,
            "results": results,
        }

    def _score_chunks(self, *, chunks: list[dict], query: str, limit: int) -> list[dict]:
        terms = self.repository.build_query_terms(query)
        query_seeks_field_answer = self._query_seeks_field_answer(query)

        scored: list[dict] = []
        for chunk in chunks:
            metadata_haystack = " ".join(
                value
                for value in (
                    chunk["source_title"],
                    chunk.get("section_label"),
                    chunk.get("heading_path"),
                    chunk.get("field_label"),
                    chunk.get("table_origin"),
                    chunk["normalized_text"],
                )
                if value
            ).lower()
            score = 0.0
            for term in terms:
                if term in metadata_haystack:
                    score += metadata_haystack.count(term)

            if score <= 0:
                continue

            if chunk["quality_level"] == "low":
                score -= 0.15
            if chunk.get("section_type") == "field":
                score += 0.55
                score += self._field_label_query_boost(query=query, field_label=chunk.get("field_label"))
            elif chunk.get("section_type") == "proposition":
                score += 0.45
                score += self._proposition_query_boost(query=query, proposition_type=chunk.get("proposition_type"))
            elif chunk.get("section_type") == "heading":
                score += 0.25
                if query_seeks_field_answer:
                    score -= 3.0

            scored.append(
                {
                    "project_id": chunk["project_id"],
                    "project_name": chunk["project_name"],
                    "chunk_id": chunk["chunk_id"],
                    "source_id": chunk["source_id"],
                    "source_title": chunk["source_title"],
                    "source_type": chunk["source_type"],
                    "canonical_uri": chunk["canonical_uri"],
                    "location_label": f"{chunk['section_label']} #{chunk['chunk_index'] + 1}",
                    "excerpt": chunk["excerpt"],
                    "relevance_score": round(score, 3),
                    "normalized_text": chunk["normalized_text"],
                    "section_type": chunk.get("section_type", "body"),
                    "heading_path": chunk.get("heading_path"),
                    "field_label": chunk.get("field_label"),
                    "table_origin": chunk.get("table_origin"),
                    "proposition_type": chunk.get("proposition_type"),
                }
            )

        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        return scored[:limit]

    def _retrieve_ranked_hits(self, *, project_id: str, query: str, limit: int) -> list[dict]:
        available_chunks = self.repository.get_latest_chunks_for_project(project_id)
        lexical_results = self._score_chunks(
            chunks=available_chunks,
            query=query,
            limit=limit,
        )
        semantic_results = self.vector_store.search(
            query=query,
            project_id=project_id,
            limit=limit,
        )
        merged = self._merge_ranked_hits(
            semantic_results=semantic_results,
            lexical_results=lexical_results,
            limit=limit,
        )
        return self._expand_structured_hits(
            query=query,
            hits=merged,
            available_chunks=available_chunks,
            limit=limit,
        )

    def _merge_ranked_hits(
        self,
        *,
        semantic_results: list[dict],
        lexical_results: list[dict],
        limit: int,
    ) -> list[dict]:
        merged: dict[str, dict] = {}

        for item in semantic_results:
            merged[item["chunk_id"]] = {
                **item,
                "relevance_score": round(float(item["relevance_score"]) * 1.25, 3),
            }

        for item in lexical_results:
            existing = merged.get(item["chunk_id"])
            if existing is None:
                merged[item["chunk_id"]] = item
                continue

            existing["relevance_score"] = round(
                float(existing["relevance_score"]) + float(item["relevance_score"]),
                3,
            )
            if not existing.get("project_name"):
                existing["project_name"] = item["project_name"]

        ranked = sorted(merged.values(), key=lambda item: item["relevance_score"], reverse=True)
        return ranked[:limit]

    def _merge_hit_batches(self, *, primary: list[dict], secondary: list[dict], limit: int) -> list[dict]:
        merged: dict[str, dict] = {item["chunk_id"]: dict(item) for item in primary}
        for item in secondary:
            existing = merged.get(item["chunk_id"])
            if existing is None:
                merged[item["chunk_id"]] = dict(item)
                continue
            existing["relevance_score"] = round(
                float(existing["relevance_score"]) + (float(item["relevance_score"]) * 0.65),
                3,
            )
            if len(item.get("excerpt", "")) > len(existing.get("excerpt", "")):
                existing["excerpt"] = item["excerpt"]
            if len(item.get("normalized_text", "")) > len(existing.get("normalized_text", "")):
                existing["normalized_text"] = item["normalized_text"]
        ranked = sorted(merged.values(), key=lambda item: item["relevance_score"], reverse=True)
        return ranked[:limit]

    def _expand_structured_hits(
        self,
        *,
        query: str,
        hits: list[dict],
        available_chunks: list[dict],
        limit: int,
    ) -> list[dict]:
        if not hits:
            return hits

        expanded: dict[str, dict] = {item["chunk_id"]: dict(item) for item in hits}
        for anchor in hits[: min(4, len(hits))]:
            for candidate in self._collect_structured_body_candidates(
                query=query,
                anchor=anchor,
                available_chunks=available_chunks,
            ):
                existing = expanded.get(candidate["chunk_id"])
                if existing is None or float(candidate["relevance_score"]) > float(existing["relevance_score"]):
                    expanded[candidate["chunk_id"]] = candidate

        ranked = sorted(expanded.values(), key=lambda item: item["relevance_score"], reverse=True)
        return ranked[:limit]

    def _collect_structured_body_candidates(
        self,
        *,
        query: str,
        anchor: dict,
        available_chunks: list[dict],
    ) -> list[dict]:
        anchor_type = anchor.get("section_type")
        anchor_heading = anchor.get("heading_path")
        if anchor_type == "heading" and not anchor_heading:
            anchor_heading = anchor.get("normalized_text")

        if anchor_type not in {"heading", "field"}:
            return []
        if anchor_type == "field" and not anchor_heading:
            return []

        candidates: list[dict] = []
        for chunk in available_chunks:
            if chunk["source_id"] != anchor["source_id"]:
                continue
            if chunk["chunk_id"] == anchor["chunk_id"]:
                continue
            if chunk.get("section_type") != "body":
                continue
            if anchor_heading and chunk.get("heading_path") != anchor_heading:
                continue

            score = self._hierarchical_body_score(query=query, anchor=anchor, chunk=chunk)
            if score <= 0:
                continue
            candidates.append(self._chunk_row_to_result(chunk=chunk, relevance_score=score))

        candidates.sort(key=lambda item: item["relevance_score"], reverse=True)
        return candidates[:2]

    def _hierarchical_body_score(self, *, query: str, anchor: dict, chunk: dict) -> float:
        normalized_query = " ".join(query.split()).lower()
        terms = [term for term in self.repository.build_query_terms(query) if len(term) >= 2]
        heading_path = (chunk.get("heading_path") or "").lower()
        normalized_text = chunk["normalized_text"].lower()
        score = 0.0

        if heading_path:
            if heading_path in normalized_query:
                score += 1.4
            score += 0.35 * sum(1 for term in terms if term in heading_path)

        score += 0.2 * sum(1 for term in terms if term in normalized_text)

        anchor_type = anchor.get("section_type")
        anchor_score = float(anchor.get("relevance_score", 0.0))
        if anchor_type == "heading":
            score += max(anchor_score * 0.72, 1.8)
        elif anchor_type == "field":
            score += max(anchor_score * 0.58, 1.2)

        if self._query_seeks_field_answer(query) and heading_path:
            score += 0.35

        return round(score, 3)

    def _chunk_row_to_result(self, *, chunk: dict, relevance_score: float) -> dict:
        return {
            "project_id": chunk["project_id"],
            "project_name": chunk["project_name"],
            "chunk_id": chunk["chunk_id"],
            "source_id": chunk["source_id"],
            "source_title": chunk["source_title"],
            "source_type": chunk["source_type"],
            "canonical_uri": chunk["canonical_uri"],
            "location_label": f"{chunk['section_label']} #{chunk['chunk_index'] + 1}",
            "excerpt": chunk["excerpt"],
            "relevance_score": round(float(relevance_score), 3),
            "normalized_text": chunk["normalized_text"],
            "section_type": chunk.get("section_type", "body"),
            "heading_path": chunk.get("heading_path"),
            "field_label": chunk.get("field_label"),
            "table_origin": chunk.get("table_origin"),
            "proposition_type": chunk.get("proposition_type"),
        }

    def _should_retry_with_hyde(
        self,
        *,
        query: str,
        hits: list[dict],
        limit: int,
        context_clues: list[str] | None = None,
    ) -> bool:
        analysis = self._analyze_hits(
            query=query,
            hits=hits,
            limit=limit,
            context_clues=context_clues or [],
        )
        return analysis["is_low_confidence"]

    def _analyze_hits(
        self,
        *,
        query: str,
        hits: list[dict],
        limit: int,
        context_clues: list[str],
    ) -> dict:
        if not hits:
            return {
                "hit_count": 0,
                "top_score": 0.0,
                "title_hit_count": 0,
                "field_hit_count": 0,
                "term_coverage_ratio": 0.0,
                "is_low_confidence": True,
            }

        top_score = float(hits[0]["relevance_score"])
        strong_terms = [
            term
            for term in self.repository.build_query_terms(query)
            if len(term) >= 2 and term not in GENERIC_QUERY_TERMS
        ]

        coverage = 0
        top_hits = hits[: min(5, len(hits))]
        for term in strong_terms[:8]:
            if any(term in self._hit_haystack(item) for item in top_hits):
                coverage += 1

        title_hit_count = sum(1 for item in top_hits if self._hit_title_matches_terms(item, strong_terms))
        field_hit_count = sum(1 for item in top_hits if self._hit_field_like_section(item))
        coverage_ratio = round(coverage / max(len(strong_terms[:8]), 1), 3) if strong_terms else 0.0
        query_looks_contextual = self._query_looks_contextual(query)

        is_low_confidence = False
        if top_score <= VERY_LOW_CONFIDENCE_TOP_SCORE:
            is_low_confidence = True
        elif not strong_terms:
            is_low_confidence = len(hits) < limit and top_score < LOW_CONFIDENCE_TOP_SCORE
        elif coverage == 0:
            is_low_confidence = True
        elif coverage_ratio < 0.34 and (top_score < LOW_CONFIDENCE_TOP_SCORE or title_hit_count == 0):
            is_low_confidence = True
        elif len(hits) < limit and top_score < LOW_CONFIDENCE_TOP_SCORE:
            is_low_confidence = True

        if field_hit_count > 0 and top_score >= LOW_CONFIDENCE_TOP_SCORE:
            is_low_confidence = False

        if (
            query_looks_contextual
            and context_clues
            and (coverage_ratio < 0.5 or title_hit_count == 0)
            and top_score < (LOW_CONFIDENCE_TOP_SCORE + 0.5)
        ):
            is_low_confidence = True

        return {
            "hit_count": len(hits),
            "top_score": round(top_score, 3),
            "title_hit_count": title_hit_count,
            "field_hit_count": field_hit_count,
            "term_coverage_ratio": coverage_ratio,
            "is_low_confidence": is_low_confidence,
        }

    def _build_retry_queries(
        self,
        *,
        query: str,
        research_mode: bool,
        context_clues: list[str],
    ) -> list[tuple[str, str]]:
        normalized = " ".join(query.split())
        retry_queries: list[tuple[str, str]] = []
        seen: set[str] = {normalized}
        context_seed = self._build_contextual_query(query=normalized, context_clues=context_clues)

        def append(strategy: str, candidate: str) -> None:
            cleaned = " ".join(candidate.split()).strip()
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            retry_queries.append((strategy, cleaned))

        if context_seed and context_seed != normalized:
            append("context_rewrite", context_seed)

        for term, variants in QUERY_EXPANSION_RULES.items():
            if term in normalized:
                for variant in variants:
                    append("field_alias_expansion", f"{context_seed or normalized} {variant}")

        expanded_terms = [term for term in self.repository.build_query_terms(query) if len(term) >= 2]
        if expanded_terms:
            append("term_compaction", " ".join(expanded_terms[:6]))

        hypothetical_passage = self.llm.generate_hypothetical_passage(
            query=context_seed or normalized,
            research_mode=research_mode,
        )
        if hypothetical_passage:
            append("hyde_passage", hypothetical_passage)

        return retry_queries[:4]

    def _rerank_hits(self, *, query: str, hits: list[dict], limit: int) -> list[dict]:
        terms = self.repository.build_query_terms(query)
        normalized_query = " ".join(query.split()).lower()
        reranked: list[dict] = []

        for item in hits:
            title = item["source_title"].lower()
            haystack = f"{title} {item['excerpt']} {item.get('normalized_text', '')}".lower()
            score = float(item["relevance_score"])

            score += 0.8 * sum(1 for term in terms if term in title)
            score += 0.35 * sum(1 for term in terms if term in haystack)
            if normalized_query and normalized_query in haystack:
                score += 2.2
            if item["source_type"] in {"file_pdf", "file_docx"}:
                score += 0.1

            reranked.append(
                {
                    **item,
                    "relevance_score": round(score, 3),
                }
            )

        reranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return reranked[:limit]

    def _collect_context_clues(self, *, query: str, history: list[dict] | None) -> list[str]:
        if not history:
            return []

        normalized_query = " ".join(query.split()).strip().lower()
        clues: list[str] = []
        seen: set[str] = set()
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            content = " ".join((item.get("content_md") or "").split()).strip()
            if not content:
                continue
            lowered = content.lower()
            if lowered == normalized_query or lowered in seen:
                continue
            seen.add(lowered)
            clues.append(content)
            if len(clues) >= RETRIEVAL_CONTEXT_WINDOW:
                break
        return clues

    def _build_contextual_query(self, *, query: str, context_clues: list[str]) -> str | None:
        if not context_clues:
            return None

        if self._query_looks_contextual(query):
            return f"{context_clues[0]} {query}"

        recent_context = context_clues[0]
        recent_terms = [term for term in self.repository.build_query_terms(recent_context) if len(term) >= 2]
        if not recent_terms:
            return None

        query_terms = set(self.repository.build_query_terms(query))
        bridge_terms = [term for term in recent_terms if term not in query_terms]
        if not bridge_terms:
            return None
        return f"{query} {' '.join(bridge_terms[:4])}"

    def _query_looks_contextual(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        if len(normalized) <= 14:
            return True
        return any(term in normalized for term in FOLLOW_UP_QUERY_TERMS)

    def _hit_haystack(self, item: dict) -> str:
        return (
            f"{item['source_title']} "
            f"{item.get('location_label', '')} "
            f"{item.get('heading_path', '')} "
            f"{item.get('field_label', '')} "
            f"{item.get('table_origin', '')} "
            f"{item.get('excerpt', '')} "
            f"{item.get('normalized_text', '')}"
        ).lower()

    def _hit_title_matches_terms(self, item: dict, strong_terms: list[str]) -> bool:
        if not strong_terms:
            return False
        title = item["source_title"].lower()
        return any(term in title for term in strong_terms[:8])

    def _hit_field_like_section(self, item: dict) -> bool:
        field_haystack = (
            f"{item.get('location_label', '')} "
            f"{item.get('field_label', '')} "
            f"{item.get('excerpt', '')}"
        ).lower()
        return any(label in field_haystack for label in FIELD_LABEL_HINTS)

    def _field_label_query_boost(self, *, query: str, field_label: str | None) -> float:
        if not field_label:
            return 0.0

        normalized_query = " ".join(query.split()).lower()
        normalized_label = field_label.lower()
        boost = 0.0

        if normalized_label in normalized_query:
            boost += 1.2

        for trigger, labels in FIELD_QUERY_GROUPS.items():
            if trigger not in normalized_query:
                continue
            if any(label in normalized_label for label in labels):
                boost += 4.0

        return boost

    def _query_seeks_field_answer(self, query: str) -> bool:
        normalized_query = " ".join(query.split()).lower()
        return any(trigger in normalized_query for trigger in FIELD_QUERY_GROUPS)

    def _proposition_query_boost(self, *, query: str, proposition_type: str | None) -> float:
        if not proposition_type:
            return 0.0

        normalized_query = " ".join(query.split()).lower()
        triggers = PROPOSITION_QUERY_GROUPS.get(proposition_type)
        if not triggers:
            return 0.0
        if any(trigger in normalized_query for trigger in triggers):
            return 2.2
        return 0.0

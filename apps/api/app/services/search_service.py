from __future__ import annotations

import logging
from contextvars import ContextVar

from app.repositories.search_repository import SearchRepository
from app.services.llm_service import LLMService
from app.services.reranker_service import RerankerService
from app.services.vector_store import VectorStore


COMPLEX_QUERY_KEYWORDS = (
    "比较",
    "区别",
    "优缺点",
    "方案",
    "评估",
    "为什么",
    "如何",
    "总结",
    "梳理",
    "推荐",
    "适合",
)
LOW_CONFIDENCE_TOP_SCORE = 2.2
VERY_LOW_CONFIDENCE_TOP_SCORE = 1.2
GENERIC_QUERY_TERMS = {
    "什么",
    "怎么",
    "如何",
    "现在",
    "知道",
    "我的",
    "了吗",
    "呢",
    "吗",
    "报告",
}
QUERY_EXPANSION_RULES = {
    "题目": (
        "开题报告 题目 课题名称 项目名称",
        "课题名称 项目名称 题目",
    ),
    "标题": ("题目 课题名称 项目名称",),
    "项目": ("项目名称 课题名称 研究主题",),
    "优化": (
        "优化建议 可以改进的地方 不足 完善建议",
    ),
    "改进": (
        "优化建议 可以改进的地方 不足 完善建议",
    ),
}
FIELD_LABEL_HINTS = (
    "题目",
    "标题",
    "项目",
    "项目名称",
    "课题",
    "课题名称",
    "研究内容",
    "创新点",
    "预期成果",
    "结论",
    "建议",
)
FIELD_QUERY_GROUPS = {
    "题目": ("题目", "标题", "课题", "课题名称", "项目名称"),
    "标题": ("题目", "标题", "课题", "课题名称", "项目名称"),
    "项目": ("项目", "项目名称", "课题", "课题名称", "题目"),
    "研究内容": ("研究内容",),
    "创新点": ("创新点",),
    "预期成果": ("预期成果",),
    "结论": ("结论",),
    "建议": ("建议", "优化", "改进"),
    "优化": ("建议", "优化", "改进"),
    "改进": ("建议", "优化", "改进"),
}
PROPOSITION_QUERY_GROUPS = {
    "identity": ("题目", "标题", "项目", "课题", "project name", "title"),
    "suggestion": ("建议", "优化", "改进", "suggest", "recommend", "improve"),
    "conclusion": ("结论", "总结", "可行", "conclusion", "summary", "feasible"),
    "innovation": ("创新", "创新点", "innovation", "novel"),
    "outcome": ("预期成果", "成果", "outcome", "deliverable", "result"),
    "method": ("研究内容", "实施计划", "方法", "方案", "implementation", "method", "plan"),
}
FOLLOW_UP_QUERY_TERMS = {
    "现在",
    "这个",
    "那个",
    "这份",
    "那份",
    "知道",
    "了吗",
    "它",
    "这项",
    "那项",
}
RETRIEVAL_CONTEXT_WINDOW = 3

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, *, llm_service: LLMService | None = None) -> None:
        self.repository = SearchRepository()
        self.vector_store = VectorStore()
        self.llm = llm_service or LLMService()
        self.reranker = RerankerService()
        self._last_retrieval_diagnostics: ContextVar[dict | None] = ContextVar(
            "search_last_retrieval_diagnostics",
            default=None,
        )

    @property
    def settings(self):
        return self.repository.settings

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

        rerank_applied = apply_rerank or first_pass["is_low_confidence"]
        if rerank_applied:
            results, rerank_diagnostics = self._rerank_hits(query=query, hits=merged, limit=limit)
        else:
            results = merged[:limit]
            rerank_diagnostics = {"backend": "skipped", "applied": False, "fallback_reason": None}

        effective_pass = self._analyze_hits(
            query=query,
            hits=results or merged,
            limit=limit,
            context_clues=context_clues,
        )

        diagnostics = {
            "original_query": query,
            "context_clues": context_clues,
            "first_pass": first_pass,
            "effective_pass": effective_pass,
            "triggered_second_pass": bool(retry_steps),
            "retry_steps": retry_steps,
            "rerank": rerank_diagnostics,
            "final": {
                "hit_count": len(merged),
                "source_count": len({item["source_id"] for item in results if item.get("source_id")}),
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
        available_chunks = self.repository.get_latest_chunks(scope=scope, project_id=project_id)
        lexical_results = []
        if available_chunks or scope != "project":
            lexical_results = self._score_chunks(
                chunks=available_chunks,
                query=query,
                limit=max(limit * 3, self.settings.retrieval_lexical_candidate_limit),
            )
        semantic_results = self.vector_store.search(
            query=query,
            project_id=project_id if scope == "project" else None,
            limit=max(limit * 3, self.settings.retrieval_semantic_candidate_limit),
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

    def _score_chunks(
        self,
        *,
        chunks: list[dict],
        query: str,
        limit: int,
    ) -> list[dict]:
        project_id = chunks[0]["project_id"] if chunks and chunks[0].get("project_id") else None
        scope = "project" if project_id else "all"
        lexical_results = self.repository.search_lexical_chunks(
            scope=scope,
            query=query,
            project_id=project_id,
            limit=limit,
        )
        if not lexical_results and chunks:
            return self._fallback_score_chunks(chunks=chunks, query=query, limit=limit)
        query_seeks_field_answer = self._query_seeks_field_answer(query)
        scored: list[dict] = []
        for item in lexical_results:
            score = self._lexical_score_from_bm25(item["bm25_score"])
            if item["quality_level"] == "low":
                score -= 0.12
            if item.get("section_type") == "field":
                score += 0.7
                score += self._field_label_query_boost(query=query, field_label=item.get("field_label"))
            elif item.get("section_type") == "proposition":
                score += 0.5
                score += self._proposition_query_boost(query=query, proposition_type=item.get("proposition_type"))
            elif item.get("section_type") == "heading":
                score += 0.22
                if query_seeks_field_answer:
                    score -= 0.6

            scored.append(
                {
                    "project_id": item["project_id"],
                    "project_name": item["project_name"],
                    "chunk_id": item["chunk_id"],
                    "source_id": item["source_id"],
                    "source_title": item["source_title"],
                    "source_type": item["source_type"],
                    "canonical_uri": item["canonical_uri"],
                    "location_label": f"{item['section_label']} #{item['chunk_index'] + 1}",
                    "excerpt": item["excerpt"],
                    "normalized_text": item["normalized_text"],
                    "relevance_score": round(score, 6),
                    "bm25_score": item["bm25_score"],
                    "lexical_rank": item.get("lexical_rank"),
                    "quality_level": item["quality_level"],
                    "section_type": item.get("section_type", "body"),
                    "heading_path": item.get("heading_path"),
                    "field_label": item.get("field_label"),
                    "table_origin": item.get("table_origin"),
                    "proposition_type": item.get("proposition_type"),
                }
            )

        scored.sort(key=lambda hit: hit["relevance_score"], reverse=True)
        return scored[:limit]

    def _fallback_score_chunks(self, *, chunks: list[dict], query: str, limit: int) -> list[dict]:
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
                    "relevance_score": round(score, 6),
                    "normalized_text": chunk["normalized_text"],
                    "section_type": chunk.get("section_type", "body"),
                    "heading_path": chunk.get("heading_path"),
                    "field_label": chunk.get("field_label"),
                    "table_origin": chunk.get("table_origin"),
                    "proposition_type": chunk.get("proposition_type"),
                    "quality_level": chunk["quality_level"],
                    "fusion_sources": ["lexical_fallback"],
                }
            )

        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        return scored[:limit]

    def _lexical_score_from_bm25(self, bm25_score: float) -> float:
        bounded = max(0.0, -float(bm25_score))
        return min(1.5, bounded / 8.0)

    def _retrieve_ranked_hits(self, *, project_id: str, query: str, limit: int) -> list[dict]:
        available_chunks = self.repository.get_latest_chunks_for_project(project_id)
        lexical_results = []
        if available_chunks:
            lexical_results = self._score_chunks(
                chunks=available_chunks,
                query=query,
                limit=max(limit, self.settings.retrieval_lexical_candidate_limit),
            )
        semantic_results = self.vector_store.search(
            query=query,
            project_id=project_id,
            limit=max(limit, self.settings.retrieval_semantic_candidate_limit),
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
        rrf_k = max(1, self.settings.retrieval_rrf_k)

        for rank, item in enumerate(lexical_results, start=1):
            chunk_id = item["chunk_id"]
            existing = merged.setdefault(chunk_id, dict(item))
            existing["lexical_rank"] = rank
            existing["semantic_rank"] = existing.get("semantic_rank")
            existing["fusion_sources"] = sorted(set(existing.get("fusion_sources", [])) | {"lexical"})
            existing["relevance_score"] = round(
                float(existing.get("relevance_score", 0.0)) + (100.0 / (rrf_k + rank)),
                6,
            )

        for rank, item in enumerate(semantic_results, start=1):
            chunk_id = item["chunk_id"]
            existing = merged.get(chunk_id)
            if existing is None:
                existing = dict(item)
                existing["relevance_score"] = 0.0
                merged[chunk_id] = existing
            existing["semantic_rank"] = rank
            existing["fusion_sources"] = sorted(set(existing.get("fusion_sources", [])) | {"semantic"})
            existing["relevance_score"] = round(
                float(existing.get("relevance_score", 0.0)) + (100.0 / (rrf_k + rank)),
                6,
            )
            for key in ("project_name", "normalized_text", "excerpt", "heading_path", "field_label", "table_origin", "proposition_type"):
                if not existing.get(key) and item.get(key):
                    existing[key] = item[key]

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                item["relevance_score"],
                -min(
                    item.get("lexical_rank") or 10**6,
                    item.get("semantic_rank") or 10**6,
                ),
            ),
            reverse=True,
        )
        return ranked[:limit]

    def _merge_hit_batches(self, *, primary: list[dict], secondary: list[dict], limit: int) -> list[dict]:
        merged: dict[str, dict] = {}
        rrf_k = max(1, self.settings.retrieval_rrf_k)

        for batch_name, hits in (("first_pass", primary), ("second_pass", secondary)):
            for rank, item in enumerate(hits, start=1):
                chunk_id = item["chunk_id"]
                existing = merged.get(chunk_id)
                if existing is None:
                    existing = dict(item)
                    existing["relevance_score"] = 0.0
                    merged[chunk_id] = existing
                existing["batch_sources"] = sorted(set(existing.get("batch_sources", [])) | {batch_name})
                existing["relevance_score"] = round(
                    float(existing["relevance_score"]) + (100.0 / (rrf_k + rank)),
                    6,
                )
                if batch_name == "first_pass":
                    existing["primary_rank"] = rank
                else:
                    existing["secondary_rank"] = rank
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
                score += 0.45
            score += 0.12 * sum(1 for term in terms if term in heading_path)

        score += 0.05 * sum(1 for term in terms if term in normalized_text)

        anchor_type = anchor.get("section_type")
        anchor_score = float(anchor.get("relevance_score", 0.0))
        if anchor_type == "heading":
            score += max(anchor_score * 0.72, 0.04)
        elif anchor_type == "field":
            score += max(anchor_score * 0.58, 0.03)

        if self._query_seeks_field_answer(query) and heading_path:
            score += 0.04

        return round(score, 6)

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
            "relevance_score": round(float(relevance_score), 6),
            "normalized_text": chunk["normalized_text"],
            "quality_level": chunk.get("quality_level", "normal"),
            "section_type": chunk.get("section_type", "body"),
            "heading_path": chunk.get("heading_path"),
            "field_label": chunk.get("field_label"),
            "table_origin": chunk.get("table_origin"),
            "proposition_type": chunk.get("proposition_type"),
            "fusion_sources": ["hierarchical"],
        }

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
            and top_score < (LOW_CONFIDENCE_TOP_SCORE + 0.015)
        ):
            is_low_confidence = True

        return {
            "hit_count": len(hits),
            "top_score": round(top_score, 6),
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

        should_try_hyde = (
            research_mode
            or self.should_rerank_query(query)
            or (not self._query_seeks_field_answer(query) and not self._query_looks_contextual(query))
        )
        if should_try_hyde:
            hypothetical_passage = self.llm.generate_hypothetical_passage(
                query=context_seed or normalized,
                research_mode=research_mode,
            )
            if hypothetical_passage:
                append("hyde_passage", hypothetical_passage)

        return retry_queries[: self.settings.retrieval_second_pass_limit]

    def _rerank_hits(self, *, query: str, hits: list[dict], limit: int) -> tuple[list[dict], dict]:
        reranked, diagnostics = self.reranker.rerank(query=query, hits=hits, top_n=min(len(hits), self.settings.reranker_top_n))
        return reranked[:limit], diagnostics

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
            boost += 0.35

        for trigger, labels in FIELD_QUERY_GROUPS.items():
            if trigger not in normalized_query:
                continue
            if any(label in normalized_label for label in labels):
                boost += 0.9

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
            return 0.45
        return 0.0

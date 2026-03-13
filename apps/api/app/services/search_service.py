from __future__ import annotations

from app.repositories.search_repository import SearchRepository
from app.services.llm_service import LLMService
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
GENERIC_QUERY_TERMS = {"什么", "怎么", "如何", "现在", "知道", "我的", "了吗", "呢", "吗", "报告"}
QUERY_EXPANSION_RULES = {
    "题目": ("开题报告 题目 课题名称 项目名称", "课题名称 项目名称 题目"),
    "标题": ("题目 课题名称 项目名称",),
    "项目": ("项目名称 课题名称 研究主题",),
    "优化": ("优化建议 可以改进的地方 不足 完善建议",),
    "改进": ("优化建议 可以改进的地方 不足 完善建议",),
}


class SearchService:
    def __init__(self, *, llm_service: LLMService | None = None) -> None:
        self.repository = SearchRepository()
        self.vector_store = VectorStore()
        self.llm = llm_service or LLMService()

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
    ) -> list[dict]:
        candidate_limit = max(limit * 4, 12)
        merged = self._retrieve_ranked_hits(project_id=project_id, query=query, limit=candidate_limit)
        if self._should_retry_with_hyde(query=query, hits=merged, limit=limit):
            for retry_query in self._build_retry_queries(query=query, research_mode=limit > 3):
                retry_hits = self._retrieve_ranked_hits(project_id=project_id, query=retry_query, limit=candidate_limit)
                merged = self._merge_hit_batches(primary=merged, secondary=retry_hits, limit=candidate_limit)
        if apply_rerank:
            return self._rerank_hits(query=query, hits=merged, limit=limit)
        return merged[:limit]

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
        results = self._merge_ranked_hits(semantic_results=semantic_results, lexical_results=lexical_results, limit=limit)
        return {
            "scope": scope,
            "query": query,
            "results": results,
        }

    def _score_chunks(self, *, chunks: list[dict], query: str, limit: int) -> list[dict]:
        terms = self.repository.build_query_terms(query)

        scored: list[dict] = []
        for chunk in chunks:
            haystack = f"{chunk['source_title']} {chunk['normalized_text']}".lower()
            score = 0.0
            for term in terms:
                if term in haystack:
                    score += haystack.count(term)

            if score <= 0:
                continue

            if chunk["quality_level"] == "low":
                score -= 0.15

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
                }
            )

        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        return scored[:limit]

    def _retrieve_ranked_hits(self, *, project_id: str, query: str, limit: int) -> list[dict]:
        lexical_results = self._score_chunks(
            chunks=self.repository.get_latest_chunks_for_project(project_id),
            query=query,
            limit=limit,
        )
        semantic_results = self.vector_store.search(
            query=query,
            project_id=project_id,
            limit=limit,
        )
        return self._merge_ranked_hits(
            semantic_results=semantic_results,
            lexical_results=lexical_results,
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

    def _should_retry_with_hyde(self, *, query: str, hits: list[dict], limit: int) -> bool:
        if not hits:
            return True

        top_score = float(hits[0]["relevance_score"])
        if top_score <= VERY_LOW_CONFIDENCE_TOP_SCORE:
            return True

        strong_terms = [
            term
            for term in self.repository.build_query_terms(query)
            if len(term) >= 2 and term not in GENERIC_QUERY_TERMS
        ]
        if not strong_terms:
            return len(hits) < limit and top_score < LOW_CONFIDENCE_TOP_SCORE

        coverage = 0
        top_hits = hits[: min(3, len(hits))]
        for term in strong_terms[:8]:
            if any(term in f"{item['source_title']} {item.get('excerpt', '')} {item.get('normalized_text', '')}".lower() for item in top_hits):
                coverage += 1

        if coverage == 0:
            return True
        if coverage == 1 and (len(hits) < limit or top_score < LOW_CONFIDENCE_TOP_SCORE):
            return True
        return len(hits) < limit and top_score < LOW_CONFIDENCE_TOP_SCORE

    def _build_retry_queries(self, *, query: str, research_mode: bool) -> list[str]:
        normalized = " ".join(query.split())
        retry_queries: list[str] = []
        seen: set[str] = {normalized}

        def append(candidate: str) -> None:
            cleaned = " ".join(candidate.split()).strip()
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            retry_queries.append(cleaned)

        for term, variants in QUERY_EXPANSION_RULES.items():
            if term in normalized:
                for variant in variants:
                    append(f"{normalized} {variant}")

        expanded_terms = [term for term in self.repository.build_query_terms(query) if len(term) >= 2]
        if expanded_terms:
            append(" ".join(expanded_terms[:6]))

        hypothetical_passage = self.llm.generate_hypothetical_passage(query=normalized, research_mode=research_mode)
        if hypothetical_passage:
            append(hypothetical_passage)

        return retry_queries[:3]

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

from pathlib import Path

from app.repositories.search_repository import SearchRepository
from app.services.retrieval_benchmark_service import compute_case_metrics, run_offline_retrieval_benchmark


def _fake_semantic_search(self, *, query, project_id, limit):
    repository = SearchRepository()
    chunks = repository.get_latest_chunks_for_project(project_id)
    terms = repository.build_query_terms(query)
    scored = []
    for chunk in chunks:
        haystack = " ".join(
            value
            for value in (
                chunk.get("source_title"),
                chunk.get("heading_path"),
                chunk.get("field_label"),
                chunk.get("normalized_text"),
                chunk.get("excerpt"),
            )
            if value
        ).lower()
        score = 0.0
        for term in terms:
            if term in haystack:
                score += 1.2
        if "总结" in query or "概括" in query:
            if chunk["source_title"] in {
                "benchmark-overview.docx",
                "benchmark-optimization.docx",
                "benchmark-feasibility.docx",
            }:
                score += 1.5
        if "可行" in query and "可行性" in haystack:
            score += 1.8
        if score <= 0:
            continue
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
                "section_type": chunk.get("section_type", "body"),
                "heading_path": chunk.get("heading_path"),
                "field_label": chunk.get("field_label"),
                "table_origin": chunk.get("table_origin"),
                "proposition_type": chunk.get("proposition_type"),
                "excerpt": chunk["excerpt"],
                "normalized_text": chunk["normalized_text"],
                "relevance_score": round(score, 6),
                "quality_level": chunk["quality_level"],
            }
        )
    scored.sort(key=lambda item: item["relevance_score"], reverse=True)
    return scored[:limit]


def _fake_hyde(self, *, query, research_mode):
    if any(token in query for token in ("总结", "概括", "高层", "可行")):
        return "系统具备实现可行性 多传感器融合 研究内容 优化建议 补充实验验证"
    return ""


def test_compute_case_metrics_supports_chunk_and_source_truth():
    chunk_metrics = compute_case_metrics(
        retrieved_chunk_ids=["chunk-a", "chunk-b"],
        retrieved_source_ids=["source-a"],
        relevant_chunk_ids=("chunk-b",),
        relevant_source_ids=(),
    )
    assert chunk_metrics["truth_type"] == "chunk"
    assert chunk_metrics["recall_at"]["1"] == 0.0
    assert chunk_metrics["recall_at"]["3"] == 1.0
    assert chunk_metrics["mrr_10"] == 0.5

    source_metrics = compute_case_metrics(
        retrieved_chunk_ids=[],
        retrieved_source_ids=["source-a", "source-b"],
        relevant_chunk_ids=(),
        relevant_source_ids=("source-b",),
    )
    assert source_metrics["truth_type"] == "source"
    assert source_metrics["top1_correct"] is False
    assert source_metrics["ndcg_10"] > 0


def test_offline_retrieval_benchmark_smoke_writes_artifacts(client, monkeypatch):
    monkeypatch.setattr("app.services.vector_store.VectorStore.search", _fake_semantic_search)
    monkeypatch.setattr("app.services.llm_service.LLMService.generate_hypothetical_passage", _fake_hyde)

    report = run_offline_retrieval_benchmark(client, matrix="smoke")

    assert report["summary"]["suite"] == "offline_retrieval_benchmark"
    assert report["summary"]["case_count"] >= 40
    assert report["summary"]["config_count"] >= 10
    assert "recommendations" in report["summary"]
    assert report["summary"]["best_configs"]["hybrid"]["config"]["stage"] == "hybrid_sweep"

    artifact_dir = Path(report["artifacts_path"])
    assert artifact_dir.exists()
    assert (artifact_dir / "summary.json").exists()
    assert (artifact_dir / "per_case.json").exists()
    assert (artifact_dir / "report.md").exists()

    config_labels = {item["config"]["label"] for item in report["per_case"]}
    assert "lexical-only" in config_labels
    assert "semantic-only" in config_labels
    assert "hybrid-current" in config_labels

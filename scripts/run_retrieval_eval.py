from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def _fake_semantic_search(self, *, query, project_id, limit):
    from app.repositories.search_repository import SearchRepository

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


def _render_summary(result: dict, *, suite: str) -> str:
    if suite == "benchmark":
        summary = result.get("summary", {})
        recommendations = summary.get("recommendations", {})
        best_configs = summary.get("best_configs", {})
        lines = [
            "Offline Retrieval Benchmark Summary",
            f"- Cases: {summary.get('case_count', 0)}",
            f"- Configs: {summary.get('config_count', 0)}",
            "- Recommended parameters:",
            f"  retrieval_mode={recommendations.get('retrieval_mode')}",
            f"  lexical_candidate_limit={recommendations.get('lexical_candidate_limit')}",
            f"  semantic_candidate_limit={recommendations.get('semantic_candidate_limit')}",
            f"  rrf_k={recommendations.get('rrf_k')}",
            f"  reranker_top_n={recommendations.get('reranker_top_n')}",
            f"  hyde_policy={recommendations.get('hyde_policy')}",
            f"  final_retrieval_limit={recommendations.get('final_retrieval_limit')}",
        ]
        for label in ("hybrid", "rerank", "hyde"):
            config = best_configs.get(label, {})
            aggregate = config.get("aggregate", {}).get("overall", {})
            lines.append(
                f"- Best {label}: score={aggregate.get('score')} recall@5={aggregate.get('recall_5')} "
                f"mrr@10={aggregate.get('mrr_10')} fp_rate={aggregate.get('false_positive_rate')}"
            )
        deltas = summary.get("deltas", {})
        rerank_delta = deltas.get("rerank_vs_off")
        hyde_delta = deltas.get("hyde_vs_off")
        if rerank_delta:
            lines.append(
                f"- Rerank delta: recall@5={rerank_delta.get('recall_5_delta')} "
                f"mrr@10={rerank_delta.get('mrr_10_delta')} top1={rerank_delta.get('top1_accuracy_delta')}"
            )
        if hyde_delta:
            lines.append(
                f"- HyDE delta: recall@5={hyde_delta.get('recall_5_delta')} "
                f"fp_rate={hyde_delta.get('false_positive_rate_delta')}"
            )
        artifact_path = result.get("artifacts_path")
        if artifact_path:
            lines.append(f"- Artifacts: {artifact_path}")
        return "\n".join(lines)

    if suite == "retrieval":
        return (
            "Retrieval Eval Summary\n"
            f"- Cases: {result.get('case_count', 0)}\n"
            f"- Passed: {result.get('passed_case_count', 0)}\n"
            f"- Failed: {result.get('failed_case_count', 0)}"
        )

    if suite == "agentic":
        return (
            "Agentic Eval Summary\n"
            f"- Cases: {result.get('case_count', 0)}\n"
            f"- Passed: {result.get('passed_case_count', 0)}\n"
            f"- Failed: {result.get('failed_case_count', 0)}"
        )

    retrieval = result.get("retrieval", {})
    agentic = result.get("agentic", {})
    return (
        "Combined Eval Summary\n"
        f"- Total passed: {result.get('passed_case_count', 0)}\n"
        f"- Total failed: {result.get('failed_case_count', 0)}\n"
        f"- Retrieval cases: {retrieval.get('case_count', 0)} passed={retrieval.get('passed_case_count', 0)}\n"
        f"- Agentic cases: {agentic.get('case_count', 0)} passed={agentic.get('passed_case_count', 0)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local retrieval, benchmark, and agentic evaluation suites.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write the JSON result payload.")
    parser.add_argument(
        "--suite",
        choices=("retrieval", "agentic", "all", "benchmark"),
        default="all",
        help="Choose which evaluation suite to run.",
    )
    parser.add_argument(
        "--matrix",
        choices=("smoke", "full"),
        default="full",
        help="Benchmark sweep size. Only used with --suite benchmark.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print a concise human-readable summary instead of the full JSON payload.",
    )
    args = parser.parse_args()

    with TemporaryDirectory(prefix="workbench-retrieval-eval-") as temp_dir:
        temp_path = Path(temp_dir)
        os.environ["WORKBENCH_DATA_DIR"] = str(temp_path / "data")
        os.environ["WORKBENCH_SQLITE_PATH"] = str(temp_path / "data" / "state.db")
        os.environ["WORKBENCH_QDRANT_URL"] = ":memory:"
        os.environ["WORKBENCH_EMBEDDING_MODEL"] = ""
        os.environ["WORKBENCH_LLM_API_KEY"] = ""

        import app.core.database as database_module
        import app.core.settings as settings_module
        from app.main import app
        from app.services.retrieval_benchmark_service import run_offline_retrieval_benchmark
        from app.services.retrieval_eval_service import run_agentic_eval, run_retrieval_eval, run_v3_eval

        database_module.initialize_database()
        vector_patch = (
            patch("app.services.vector_store.VectorStore.search", _fake_semantic_search)
            if args.suite == "benchmark"
            else patch("app.services.vector_store.VectorStore.search", lambda self, *, query, project_id, limit: [])
        )
        hyde_patch = (
            patch("app.services.llm_service.LLMService.generate_hypothetical_passage", _fake_hyde)
            if args.suite == "benchmark"
            else patch("app.services.llm_service.LLMService.generate_hypothetical_passage", lambda self, *, query, research_mode: "")
        )
        with vector_patch:
            with hyde_patch:
                with TestClient(app) as client:
                    if args.suite == "retrieval":
                        result = run_retrieval_eval(client)
                    elif args.suite == "agentic":
                        result = run_agentic_eval(client)
                    elif args.suite == "benchmark":
                        result = run_offline_retrieval_benchmark(client, matrix=args.matrix)
                    else:
                        result = run_v3_eval(client)

        payload = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        if args.summary_only:
            print(_render_summary(result, suite=args.suite))
        else:
            print(payload)

        original_get_settings = settings_module.get_settings
        if hasattr(original_get_settings, "cache_clear"):
            original_get_settings.cache_clear()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

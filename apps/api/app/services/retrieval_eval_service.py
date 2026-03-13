from __future__ import annotations

from dataclasses import asdict, dataclass, field
from io import BytesIO

from docx import Document

from app.services.grounded_generation_service import GroundedGenerationService
from app.services.search_service import SearchService


@dataclass(frozen=True)
class RetrievalEvalCase:
    case_id: str
    query: str
    history: list[dict] | None = None
    limit: int = 3
    apply_rerank: bool = False
    expect_grounded_candidate: bool = True
    expect_second_pass: bool = False
    expect_min_hits: int = 1
    tags: tuple[str, ...] = field(default_factory=tuple)


def build_retrieval_eval_fixture_docx() -> bytes:
    document = Document()
    document.add_heading("开题报告", level=1)
    document.add_paragraph("该系统面向室内空气质量检测与智能控制。")
    document.add_heading("研究内容", level=1)
    document.add_paragraph("实施计划包括采集模块、控制模块、显示模块与告警模块。")
    document.add_paragraph("控制模块负责根据空气质量指标联动风扇转速。")
    document.add_heading("优化建议", level=1)
    document.add_paragraph("可以进一步优化多传感器融合、降低误报率，并补充实验验证。")
    table = document.add_table(rows=4, cols=2)
    table.cell(0, 0).text = "题目"
    table.cell(0, 1).text = "基于STM32的室内空气质量检测与智能控制系统设计"
    table.cell(1, 0).text = "项目名称"
    table.cell(1, 1).text = "室内空气质量检测与智能控制系统"
    table.cell(2, 0).text = "创新点"
    table.cell(2, 1).text = "多传感器融合与自动控制联动"
    table.cell(3, 0).text = "结论"
    table.cell(3, 1).text = "方案具备实现可行性"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_retrieval_eval_cases() -> list[RetrievalEvalCase]:
    return [
        RetrievalEvalCase(
            case_id="direct_field_title",
            query="我的题目是什么？",
            expect_grounded_candidate=True,
            expect_second_pass=False,
            tags=("field", "title"),
        ),
        RetrievalEvalCase(
            case_id="natural_follow_up",
            query="现在你知道了吗？",
            history=[{"role": "user", "content_md": "我的开题报告题目是什么？"}],
            expect_grounded_candidate=True,
            expect_second_pass=True,
            tags=("follow_up", "contextual", "chinese"),
        ),
        RetrievalEvalCase(
            case_id="chapter_plan",
            query="研究内容里的实施计划是什么？",
            expect_grounded_candidate=True,
            expect_second_pass=False,
            tags=("chapter", "plan"),
        ),
        RetrievalEvalCase(
            case_id="chapter_suggestion",
            query="你觉得报告有哪些地方可以再优化？",
            expect_grounded_candidate=True,
            expect_second_pass=False,
            tags=("chapter", "suggestion", "complex"),
        ),
        RetrievalEvalCase(
            case_id="complex_grounded_non_research",
            query="请总结研究内容并说明为什么这个方案可行。",
            expect_grounded_candidate=True,
            expect_second_pass=False,
            apply_rerank=True,
            tags=("complex", "grounded"),
        ),
        RetrievalEvalCase(
            case_id="unrelated_weather",
            query="今天北京天气如何？",
            expect_grounded_candidate=False,
            expect_second_pass=True,
            expect_min_hits=0,
            tags=("unrelated", "weak_source_mode"),
        ),
    ]


def seed_retrieval_eval_project(client, *, project_name: str = "Retrieval Eval Project") -> dict:
    project_response = client.post(
        "/api/v1/projects",
        json={
            "name": project_name,
            "description": "Structured retrieval evaluation fixtures",
            "default_external_policy": "allow_external",
        },
    )
    if project_response.status_code != 201:
        raise RuntimeError(f"Failed to create eval project: {project_response.text}")
    project = project_response.json()["item"]

    upload_response = client.post(
        f"/api/v1/projects/{project['id']}/sources/files",
        files=[
            (
                "files",
                (
                    "retrieval-eval.docx",
                    build_retrieval_eval_fixture_docx(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )
        ],
    )
    if upload_response.status_code != 201:
        raise RuntimeError(f"Failed to seed eval fixture source: {upload_response.text}")
    return project


def run_retrieval_eval(client, *, cases: list[RetrievalEvalCase] | None = None) -> dict:
    project = seed_retrieval_eval_project(client)
    service = SearchService()
    grounded_generation = GroundedGenerationService(search_service=service)
    eval_cases = cases or build_retrieval_eval_cases()
    results: list[dict] = []

    for case in eval_cases:
        evidence, diagnostics = service.retrieve_project_evidence_with_diagnostics(
            project["id"],
            case.query,
            limit=case.limit,
            apply_rerank=case.apply_rerank,
            history=case.history,
        )
        packed_evidence = grounded_generation.retrieve_evidence(
            project_id=project["id"],
            query=case.query,
            research_mode=case.limit > 3,
            history=case.history,
        )
        delivery_diagnostics = grounded_generation.last_retrieval_diagnostics
        grounded_candidate = bool(diagnostics["final"]["grounded_candidate"])
        triggered_second_pass = bool(diagnostics["triggered_second_pass"])
        labels: list[str] = []

        if grounded_candidate != case.expect_grounded_candidate:
            labels.append("grounding_mismatch")
        if triggered_second_pass != case.expect_second_pass:
            labels.append("second_pass_mismatch")
        if grounded_candidate and len(evidence) < case.expect_min_hits:
            labels.append("insufficient_hits")
        if grounded_candidate and not packed_evidence:
            labels.append("delivery_empty")
        if not grounded_candidate and case.expect_grounded_candidate:
            labels.append("missed_grounding")
        if grounded_candidate and not case.expect_grounded_candidate:
            labels.append("false_positive_grounding")

        results.append(
            {
                **asdict(case),
                "grounded_candidate": grounded_candidate,
                "triggered_second_pass": triggered_second_pass,
                "hit_count": len(evidence),
                "packed_hit_count": len(packed_evidence),
                "source_count": diagnostics["final"]["source_count"],
                "top_score": diagnostics["first_pass"]["top_score"],
                "status": "passed" if not labels else "failed",
                "diagnostic_labels": labels,
                "diagnostics": diagnostics,
                "delivery_diagnostics": delivery_diagnostics,
                "evidence_titles": [item["source_title"] for item in evidence],
            }
        )

    passed_cases = sum(1 for item in results if item["status"] == "passed")
    return {
        "project_id": project["id"],
        "case_count": len(results),
        "passed_case_count": passed_cases,
        "failed_case_count": len(results) - passed_cases,
        "results": results,
    }

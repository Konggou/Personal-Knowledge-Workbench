from io import BytesIO

from docx import Document

from app.services.search_service import SearchService


def _create_project(client, *, name: str = "Retrieval Eval Project") -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "description": "Minimal retrieval evaluation fixtures",
            "default_external_policy": "allow_external",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _build_docx_bytes(*, paragraphs: list[str] | None = None, table_rows: list[list[str]] | None = None) -> bytes:
    document = Document()
    for paragraph in paragraphs or []:
        document.add_paragraph(paragraph)

    if table_rows:
        table = document.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for row_index, row in enumerate(table_rows):
            for col_index, value in enumerate(row):
                table.cell(row_index, col_index).text = value

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_v21_minimal_retrieval_eval_set(client, monkeypatch):
    project = _create_project(client)
    docx_content = _build_docx_bytes(
        paragraphs=[
            "开题报告",
            "该系统面向室内空气质量检测与智能控制。",
            "报告还包含实施计划、创新点和优化建议。",
        ],
        table_rows=[
            ["题目", "基于STM32的室内空气质量检测与智能控制系统设计"],
            ["项目名称", "室内空气质量检测与智能控制系统"],
            ["创新点", "多传感器融合与自动控制联动"],
        ],
    )

    upload_response = client.post(
        f"/api/v1/projects/{project['id']}/sources/files",
        files=[
            (
                "files",
                (
                    "开题报告-刘艺.docx",
                    docx_content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )
        ],
    )
    assert upload_response.status_code == 201, upload_response.text

    monkeypatch.setattr("app.services.vector_store.VectorStore.search", lambda self, *, query, project_id, limit: [])

    service = SearchService()
    cases = [
        {
            "query": "我的题目是什么",
            "history": None,
            "expect_grounded": True,
            "expect_second_pass": False,
        },
        {
            "query": "现在你知道了吗",
            "history": [{"role": "user", "content_md": "我的开题报告题目是什么"}],
            "expect_grounded": True,
            "expect_second_pass": True,
        },
        {
            "query": "你觉得报告有地方可以再优化吗",
            "history": None,
            "expect_grounded": True,
            "expect_second_pass": False,
        },
        {
            "query": "今天北京天气如何",
            "history": None,
            "expect_grounded": False,
            "expect_second_pass": True,
        },
    ]

    results = []
    for case in cases:
        evidence, diagnostics = service.retrieve_project_evidence_with_diagnostics(
            project["id"],
            case["query"],
            limit=3,
            apply_rerank=False,
            history=case["history"],
        )
        results.append(
            {
                "query": case["query"],
                "grounded_candidate": diagnostics["final"]["grounded_candidate"],
                "triggered_second_pass": diagnostics["triggered_second_pass"],
                "hit_count": len(evidence),
            }
        )

    assert results[0]["grounded_candidate"] is True
    assert results[0]["hit_count"] >= 1
    assert results[1]["grounded_candidate"] is True
    assert results[1]["triggered_second_pass"] is True
    assert results[2]["grounded_candidate"] is True
    assert results[3]["triggered_second_pass"] is True

from app.api.routes.sessions import service as sessions_route_service
from app.services.llm_service import LLMService
from app.services.search_service import SearchService


def _with_diagnostics(evidence: list[dict], *, grounded_candidate: bool = True) -> tuple[list[dict], dict]:
    return (
        evidence,
        {
            "original_query": "test",
            "context_clues": [],
            "first_pass": {
                "hit_count": len(evidence),
                "top_score": evidence[0]["relevance_score"] if evidence else 0.0,
                "title_hit_count": 1 if evidence else 0,
                "field_hit_count": 0,
                "term_coverage_ratio": 1.0 if evidence else 0.0,
                "is_low_confidence": False,
            },
            "triggered_second_pass": False,
            "retry_steps": [],
            "final": {
                "hit_count": len(evidence),
                "source_count": len({item["source_id"] for item in evidence}),
                "grounded_candidate": grounded_candidate and bool(evidence),
                "returned_hit_count": len(evidence),
            },
        },
    )


def _create_project(client, *, name: str = "Grounded Project") -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "description": "Grounded RAG verification project",
            "default_external_policy": "allow_external",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _create_session(client, project_id: str) -> dict:
    response = client.post(f"/api/v1/projects/{project_id}/sessions")
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _create_html_source(html_server: dict, filename: str, body: str) -> str:
    path = html_server["root"] / filename
    path.write_text(body, encoding="utf-8")
    return f"{html_server['base_url']}/{filename}"


def _sample_evidence(source: dict, *, count: int = 1) -> list[dict]:
    return [
        {
            "project_id": source["project_id"],
            "project_name": "Grounded Project",
            "chunk_id": None,
            "source_id": source["id"],
            "source_title": source["title"],
            "source_type": source["source_type"],
            "canonical_uri": source["canonical_uri"],
            "location_label": f"Projects #{index + 1}",
            "excerpt": f"Quest 3 ships with Touch Plus controllers by default. Variant {index + 1}.",
            "relevance_score": round(4.2 - (index * 0.1), 3),
        }
        for index in range(count)
    ]


def test_grounded_message_uses_llm_markdown_and_final_sources_only(client, monkeypatch, html_server):
    project = _create_project(client)
    session = _create_session(client, project["id"])
    source_url = _create_html_source(
        html_server,
        "grounded-source.html",
        "<html><head><title>Quest 3 Notes</title></head><body><p>Quest 3 ships with Touch Plus controllers by default.</p></body></html>",
    )
    source = client.post(f"/api/v1/projects/{project['id']}/sources/web", json={"url": source_url}).json()["item"]
    evidence = _sample_evidence(source)

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda project_id, query, limit=3, apply_rerank=False, history=None: _with_diagnostics(evidence),
    )
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "Quest 3 默认配套的是 **Touch Plus** 手柄。",
            "used_general_knowledge": True,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "我用的是哪个手柄？", "deep_research": False},
    )
    assert response.status_code == 200, response.text
    detail = response.json()["item"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")

    assert answer["content_md"] == "Quest 3 默认配套的是 **Touch Plus** 手柄。"
    assert answer["title"] is None
    assert answer["source_mode"] == "project_grounded"
    assert answer["evidence_status"] == "grounded"
    assert answer["disclosure_note"]
    assert len(answer["sources"]) == 1
    assert answer["sources"][0]["source_title"] == source["title"]


def test_grounded_complex_query_enables_v1_rerank(client, monkeypatch, html_server):
    project = _create_project(client, name="Complex Query Project")
    session = _create_session(client, project["id"])
    captured: dict[str, bool] = {}
    source_url = _create_html_source(
        html_server,
        "complex-source.html",
        "<html><head><title>Quest 3 Notes</title></head><body><p>Quest 3 ships with Touch Plus controllers by default.</p></body></html>",
    )
    source = client.post(f"/api/v1/projects/{project['id']}/sources/web", json={"url": source_url}).json()["item"]

    def fake_retrieve(project_id, query, limit=3, apply_rerank=False, history=None):
        captured["apply_rerank"] = apply_rerank
        captured["history"] = history
        return _with_diagnostics(_sample_evidence(source))

    monkeypatch.setattr(sessions_route_service.search, "retrieve_project_evidence_with_diagnostics", fake_retrieve)
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "这里是基于证据整理后的回答。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "请比较不同方案的优缺点并总结为什么这样推荐。", "deep_research": False},
    )
    assert response.status_code == 200, response.text
    detail = response.json()["item"]
    assert captured["apply_rerank"] is True
    assert captured["history"][-1]["content_md"]
    assert all(item["message_type"] != "status_card" for item in detail["messages"])
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")
    assert answer["title"] is None


def test_explicit_deep_research_always_reranks_and_uses_five_evidences(client, monkeypatch, html_server):
    project = _create_project(client, name="Deep Research Budget")
    session = _create_session(client, project["id"])
    captured: dict[str, int | bool] = {}
    source_url = _create_html_source(
        html_server,
        "deep-research-source.html",
        "<html><head><title>Quest 3 Notes</title></head><body><p>Quest 3 ships with Touch Plus controllers by default.</p></body></html>",
    )
    source = client.post(f"/api/v1/projects/{project['id']}/sources/web", json={"url": source_url}).json()["item"]

    def fake_retrieve(project_id, query, limit=3, apply_rerank=False, history=None):
        captured["limit"] = limit
        captured["apply_rerank"] = apply_rerank
        captured["history"] = history
        return _with_diagnostics(_sample_evidence(source, count=5))

    monkeypatch.setattr(sessions_route_service.search, "retrieve_project_evidence_with_diagnostics", fake_retrieve)
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "这是显式深度调研生成的结论。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "请做一次深度调研。", "deep_research": True},
    )
    assert response.status_code == 200, response.text
    detail = response.json()["item"]

    assert captured["limit"] == 10
    assert captured["apply_rerank"] is True
    assert captured["history"][-1]["content_md"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")
    assert answer["title"] == "调研结论"
    assert len(answer["sources"]) == 5
    assert any(item["message_type"] == "status_card" and item["title"] == "调研中" for item in detail["messages"])
    assert any(item["message_type"] == "status_card" and item["title"] == "调研完成" for item in detail["messages"])


def test_grounded_stream_returns_llm_generated_markdown_and_metadata(client, monkeypatch, html_server):
    project = _create_project(client, name="Grounded Stream Project")
    session = _create_session(client, project["id"])
    source_url = _create_html_source(
        html_server,
        "stream-grounded-source.html",
        "<html><head><title>Quest 3 Notes</title></head><body><p>Quest 3 ships with Touch Plus controllers by default.</p></body></html>",
    )
    source = client.post(f"/api/v1/projects/{project['id']}/sources/web", json={"url": source_url}).json()["item"]
    evidence = _sample_evidence(source)

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda project_id, query, limit=3, apply_rerank=False, history=None: _with_diagnostics(evidence),
    )

    def fake_stream_grounded_reply(**kwargs):
        yield "Quest 3 默认配套的是 "
        yield "**Touch Plus** 手柄。"
        return {
            "answer_md": "Quest 3 默认配套的是 **Touch Plus** 手柄。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        }

    monkeypatch.setattr(sessions_route_service.llm, "stream_grounded_reply", fake_stream_grounded_reply)

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages/stream",
        json={"content": "我用的是哪个手柄？", "deep_research": False},
    )
    assert response.status_code == 200, response.text
    assert "event: delta" in response.text
    assert "**Touch Plus** 手柄" in response.text
    assert '"source_mode": "project_grounded"' in response.text
    assert '"source_title": "Quest 3 Notes"' in response.text


def test_grounded_stream_partial_failure_keeps_partial_output_and_appends_tail_note(client, monkeypatch, html_server):
    project = _create_project(client, name="Grounded Partial Failure")
    session = _create_session(client, project["id"])
    source_url = _create_html_source(
        html_server,
        "partial-failure-source.html",
        "<html><head><title>Quest 3 Notes</title></head><body><p>Quest 3 ships with Touch Plus controllers by default.</p></body></html>",
    )
    source = client.post(f"/api/v1/projects/{project['id']}/sources/web", json={"url": source_url}).json()["item"]
    evidence = _sample_evidence(source)

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda project_id, query, limit=3, apply_rerank=False, history=None: _with_diagnostics(evidence),
    )

    def fake_stream_grounded_reply(**kwargs):
        yield "Quest 3 默认配套的是 "
        raise RuntimeError("stream interrupted")

    monkeypatch.setattr(sessions_route_service.llm, "stream_grounded_reply", fake_stream_grounded_reply)

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages/stream",
        json={"content": "我用的是哪个手柄？", "deep_research": False},
    )
    assert response.status_code == 200, response.text
    assert "Quest 3 默认配套的是 " in response.text
    assert "本次基于项目资料的生成在中途被中断" in response.text
    assert "event: done" in response.text

    detail = client.get(f"/api/v1/sessions/{session['id']}").json()["item"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")
    assert "Quest 3 默认配套的是" in answer["content_md"]
    assert "本次基于项目资料的生成在中途被中断" in answer["content_md"]
    assert len(answer["sources"]) == 1


def test_grounded_json_parser_falls_back_to_markdown():
    service = LLMService()
    parsed = service.parse_grounded_reply("## 普通 markdown\n\n直接降级展示。")

    assert parsed["answer_md"].startswith("## 普通 markdown")
    assert parsed["used_general_knowledge"] is False
    assert parsed["evidence_status"] == "grounded"


def test_grounded_json_parser_normalizes_inline_numbered_list():
    service = LLMService()
    parsed = service.parse_grounded_reply(
        '{"answer_md":"1. 第一项 2. 第二项 3. 第三项","used_general_knowledge":false,"evidence_status":"grounded"}'
    )

    assert parsed["answer_md"] == "1. 第一项\n2. 第二项\n3. 第三项"


def test_search_service_uses_conditional_hyde_when_first_pass_is_weak(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    calls: list[str] = []

    weak_hits = [
        {
            "chunk_id": "chunk-1",
            "source_id": "source-1",
            "source_title": "开题报告-刘艺.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "正文 #1",
            "excerpt": "这是开题报告的部分说明。",
            "normalized_text": "这是开题报告的部分说明。",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 0.9,
            "quality_level": "normal",
        }
    ]
    strong_hits = [
        {
            "chunk_id": "chunk-2",
            "source_id": "source-1",
            "source_title": "开题报告-刘艺.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "课题名称 #1",
            "excerpt": "课题名称：基于STM32的室内空气质量检测与智能控制系统设计。",
            "normalized_text": "课题名称：基于STM32的室内空气质量检测与智能控制系统设计。",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 3.8,
            "quality_level": "normal",
        }
    ]

    def fake_retrieve_ranked_hits(*, project_id, query, limit):
        calls.append(query)
        if len(calls) == 1:
            return weak_hits
        return strong_hits

    monkeypatch.setattr(service, "_retrieve_ranked_hits", fake_retrieve_ranked_hits)
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", lambda **kwargs: "开题报告 课题名称 项目名称 题目")

    results = service.retrieve_project_evidence(
        "project-1",
        "现在你知道我的题目是什么了吗",
        limit=3,
        apply_rerank=False,
    )

    assert len(calls) >= 2
    assert any("开题报告" in query for query in calls[1:])
    assert results[0]["excerpt"].startswith("课题名称：")


def test_search_service_skips_hyde_when_first_pass_is_already_strong(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    calls: list[str] = []
    strong_hits = [
        {
            "chunk_id": "chunk-2",
            "source_id": "source-1",
            "source_title": "开题报告-刘艺.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "课题名称 #1",
            "excerpt": "课题名称：基于STM32的室内空气质量检测与智能控制系统设计。",
            "normalized_text": "课题名称：基于STM32的室内空气质量检测与智能控制系统设计。",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 4.6,
            "quality_level": "normal",
        }
    ]

    def fake_retrieve_ranked_hits(*, project_id, query, limit):
        calls.append(query)
        return strong_hits

    hyde_called = {"value": False}

    def fake_hyde(**kwargs):
        hyde_called["value"] = True
        return "不该触发"

    monkeypatch.setattr(service, "_retrieve_ranked_hits", fake_retrieve_ranked_hits)
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", fake_hyde)

    results = service.retrieve_project_evidence(
        "project-1",
        "我的开题报告题目是什么",
        limit=3,
        apply_rerank=False,
    )

    assert calls == ["我的开题报告题目是什么"]
    assert hyde_called["value"] is False
    assert results[0]["source_id"] == strong_hits[0]["source_id"]
    assert results[0]["excerpt"] == strong_hits[0]["excerpt"]

def test_search_service_promotes_contextual_follow_up_into_retry_queries(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    calls: list[str] = []

    weak_hits = [
        {
            "chunk_id": "chunk-1",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "Section #1",
            "excerpt": "This is only a weak overview.",
            "normalized_text": "This is only a weak overview.",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 1.4,
            "quality_level": "normal",
        }
    ]
    strong_hits = [
        {
            "chunk_id": "chunk-2",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "题目 #1",
            "excerpt": "题目：基于STM32的室内空气质量检测与智能控制系统设计",
            "normalized_text": "题目：基于STM32的室内空气质量检测与智能控制系统设计",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 4.1,
            "quality_level": "normal",
        }
    ]

    def fake_retrieve_ranked_hits(*, project_id, query, limit):
        calls.append(query)
        if len(calls) == 1:
            return weak_hits
        return strong_hits

    monkeypatch.setattr(service, "_retrieve_ranked_hits", fake_retrieve_ranked_hits)
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", lambda **kwargs: None)

    results, diagnostics = service.retrieve_project_evidence_with_diagnostics(
        "project-1",
        "现在你知道了吗",
        limit=3,
        apply_rerank=False,
        history=[
            {"role": "user", "content_md": "我的开题报告题目是什么"},
            {"role": "assistant", "content_md": "我来查一下"},
        ],
    )

    assert len(calls) >= 2
    assert calls[1].startswith("我的开题报告题目是什么")
    assert diagnostics["context_clues"] == ["我的开题报告题目是什么"]
    assert diagnostics["triggered_second_pass"] is True
    assert diagnostics["retry_steps"][0]["strategy"] == "context_rewrite"
    assert results[0]["excerpt"].startswith("题目：")


def test_search_service_collects_retrieval_diagnostics_for_field_hits(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    strong_hits = [
        {
            "chunk_id": "chunk-2",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "题目 #1",
            "excerpt": "题目：基于STM32的室内空气质量检测与智能控制系统设计",
            "normalized_text": "题目：基于STM32的室内空气质量检测与智能控制系统设计",
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "relevance_score": 4.8,
            "quality_level": "normal",
        }
    ]

    monkeypatch.setattr(service, "_retrieve_ranked_hits", lambda **kwargs: strong_hits)
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", lambda **kwargs: None)

    results, diagnostics = service.retrieve_project_evidence_with_diagnostics(
        "project-1",
        "我的题目是什么",
        limit=3,
        apply_rerank=False,
    )

    assert results[0]["source_id"] == strong_hits[0]["source_id"]
    assert results[0]["excerpt"] == strong_hits[0]["excerpt"]
    assert diagnostics["first_pass"]["field_hit_count"] >= 1
    assert diagnostics["first_pass"]["is_low_confidence"] is False
    assert diagnostics["final"]["grounded_candidate"] is True


def test_search_service_expands_heading_hits_into_section_body(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    available_chunks = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-heading",
            "source_id": "source-1",
            "section_label": "Implementation Plan",
            "section_type": "heading",
            "heading_path": "Implementation Plan",
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
            "chunk_index": 0,
            "normalized_text": "Implementation Plan",
            "excerpt": "Implementation Plan",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "quality_level": "normal",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-body",
            "source_id": "source-1",
            "section_label": "Implementation Plan",
            "section_type": "body",
            "heading_path": "Implementation Plan",
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
            "chunk_index": 1,
            "normalized_text": "The implementation plan includes sensing, control, and dashboard modules.",
            "excerpt": "The implementation plan includes sensing, control, and dashboard modules.",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "quality_level": "normal",
        },
    ]

    monkeypatch.setattr(service.repository, "get_latest_chunks_for_project", lambda project_id: available_chunks)
    monkeypatch.setattr(service.vector_store, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", lambda **kwargs: None)

    results = service.retrieve_project_evidence(
        "project-1",
        "What is the implementation plan?",
        limit=3,
        apply_rerank=False,
    )

    assert results[0]["chunk_id"] == "chunk-body"
    assert results[0]["section_type"] == "body"
    assert "sensing, control, and dashboard modules" in results[0]["normalized_text"]


def test_search_service_does_not_expand_unscoped_field_hits_into_unrelated_body_chunks(monkeypatch):
    service = SearchService(llm_service=sessions_route_service.llm)
    available_chunks = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-field",
            "source_id": "source-1",
            "section_label": "Project Name",
            "section_type": "field",
            "heading_path": None,
            "field_label": "Project Name",
            "table_origin": "table_row_1",
            "proposition_type": None,
            "chunk_index": 0,
            "normalized_text": "Project Name: Quest 3 Teleoperation System",
            "excerpt": "Project Name: Quest 3 Teleoperation System",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "quality_level": "normal",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-body",
            "source_id": "source-1",
            "section_label": "body",
            "section_type": "body",
            "heading_path": None,
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
            "chunk_index": 1,
            "normalized_text": "This body paragraph describes implementation details only.",
            "excerpt": "This body paragraph describes implementation details only.",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "quality_level": "normal",
        },
    ]

    monkeypatch.setattr(service.repository, "get_latest_chunks_for_project", lambda project_id: available_chunks)
    monkeypatch.setattr(service.vector_store, "search", lambda **kwargs: [])
    monkeypatch.setattr(service.llm, "generate_hypothetical_passage", lambda **kwargs: None)

    results = service.retrieve_project_evidence(
        "project-1",
        "Project Name",
        limit=3,
        apply_rerank=False,
    )

    assert results[0]["chunk_id"] == "chunk-field"
    assert all(item["chunk_id"] != "chunk-body" for item in results)


def test_grounded_generation_stores_latest_retrieval_diagnostics(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation
    evidence = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-1",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "题目 #1",
            "excerpt": "题目：基于STM32的室内空气质量检测与智能控制系统设计",
            "relevance_score": 4.2,
        }
    ]
    diagnostics = {
        "original_query": "我的题目是什么",
        "context_clues": ["我的开题报告是什么项目"],
        "first_pass": {
            "hit_count": 1,
            "top_score": 4.2,
            "title_hit_count": 0,
            "field_hit_count": 1,
            "term_coverage_ratio": 1.0,
            "is_low_confidence": False,
        },
        "triggered_second_pass": False,
        "retry_steps": [],
        "final": {
            "hit_count": 1,
            "source_count": 1,
            "grounded_candidate": True,
            "returned_hit_count": 1,
        },
    }

    monkeypatch.setattr(
        grounded_generation.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: (evidence, diagnostics),
    )

    packed = grounded_generation.retrieve_evidence(
        project_id="project-1",
        query="我的题目是什么",
        research_mode=False,
        history=[{"role": "user", "content_md": "我的开题报告是什么项目"}],
    )

    assert packed[0]["evidence_index"] == 1
    assert grounded_generation.last_retrieval_diagnostics is not None
    assert grounded_generation.last_retrieval_diagnostics["original_query"] == diagnostics["original_query"]
    assert grounded_generation.last_retrieval_diagnostics["selection"]["selected_candidate_count"] == 1
    assert grounded_generation.last_retrieval_diagnostics["compression"]["compressed_evidence_count"] == 1


def test_grounded_generation_compresses_selected_evidence_and_augments_diagnostics(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation
    evidence = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-heading",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "Implementation Plan #1",
            "excerpt": "Implementation Plan introduction paragraph with broad context.",
            "normalized_text": (
                "Implementation Plan covers sensing, control, and dashboard modules. "
                "The control module coordinates fan speed adjustments. "
                "Budget discussion is listed elsewhere."
            ),
            "relevance_score": 4.1,
            "section_type": "body",
            "heading_path": "Implementation Plan",
            "field_label": None,
            "table_origin": None,
            "proposition_type": "method",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-field",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "Project Name #2",
            "excerpt": "Project Name: Indoor Air Quality System",
            "normalized_text": "Project Name: Indoor Air Quality System",
            "relevance_score": 4.6,
            "section_type": "field",
            "heading_path": "Implementation Plan",
            "field_label": "Project Name",
            "table_origin": "table_row_1",
            "proposition_type": "identity",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-proposition",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "Implementation Plan #3",
            "excerpt": "The control module coordinates fan speed adjustments.",
            "normalized_text": "The control module coordinates fan speed adjustments.",
            "relevance_score": 4.3,
            "section_type": "proposition",
            "heading_path": "Implementation Plan",
            "field_label": None,
            "table_origin": None,
            "proposition_type": "method",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-extra",
            "source_id": "source-2",
            "source_title": "Budget.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///budget.docx",
            "location_label": "Budget #1",
            "excerpt": "Unrelated budget detail.",
            "normalized_text": "Unrelated budget detail for a different section.",
            "relevance_score": 1.2,
            "section_type": "body",
            "heading_path": "Budget",
            "field_label": None,
            "table_origin": None,
            "proposition_type": "fact",
        },
    ]
    diagnostics = {
        "original_query": "What is the implementation plan?",
        "context_clues": [],
        "first_pass": {
            "hit_count": len(evidence),
            "top_score": 4.6,
            "title_hit_count": 1,
            "field_hit_count": 1,
            "term_coverage_ratio": 1.0,
            "is_low_confidence": False,
        },
        "triggered_second_pass": False,
        "retry_steps": [],
        "final": {
            "hit_count": len(evidence),
            "source_count": 2,
            "grounded_candidate": True,
            "returned_hit_count": len(evidence),
        },
    }

    monkeypatch.setattr(
        grounded_generation.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: (evidence, diagnostics),
    )

    packed = grounded_generation.retrieve_evidence(
        project_id="project-1",
        query="What is the implementation plan?",
        research_mode=False,
        history=None,
    )

    assert len(packed) == 3
    assert packed[0]["evidence_index"] == 1
    assert all("compression_reason" in item for item in packed)
    assert packed[0]["excerpt"]
    assert len(packed[0]["excerpt"]) <= len(packed[0]["normalized_text"])
    assert "source_excerpt" in packed[0]

    augmented = grounded_generation.last_retrieval_diagnostics
    assert augmented is not None
    assert augmented["selection"]["selector_applied"] is True
    assert augmented["compression"]["compressed_evidence_count"] == 3
    assert augmented["final"]["selected_evidence_count"] == 3


def test_grounded_generation_rejects_low_confidence_second_pass_false_positives(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation
    evidence = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-low",
            "source_id": "source-1",
            "source_title": "Outline.docx",
            "source_type": "file_docx",
            "canonical_uri": "file:///outline.docx",
            "location_label": "Project Name #1",
            "excerpt": "Project Name: Indoor Air Quality System",
            "normalized_text": "Project Name: Indoor Air Quality System",
            "relevance_score": 1.55,
            "section_type": "field",
            "heading_path": "Overview",
            "field_label": "Project Name",
            "table_origin": "table_row_1",
            "proposition_type": "identity",
        }
    ]
    diagnostics = {
        "original_query": "今天北京天气如何？",
        "context_clues": [],
        "first_pass": {
            "hit_count": 0,
            "top_score": 0.0,
            "title_hit_count": 0,
            "field_hit_count": 0,
            "term_coverage_ratio": 0.0,
            "is_low_confidence": True,
        },
        "triggered_second_pass": True,
        "retry_steps": [{"strategy": "hyde_passage", "query": "北京今日天气预报", "hit_count": 1, "top_score": 1.55}],
        "final": {
            "hit_count": 1,
            "source_count": 1,
            "grounded_candidate": True,
            "returned_hit_count": 1,
        },
    }

    monkeypatch.setattr(
        grounded_generation.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: (evidence, diagnostics),
    )

    packed = grounded_generation.retrieve_evidence(
        project_id="project-1",
        query="今天北京天气如何？",
        research_mode=False,
        history=None,
    )

    assert packed == []
    augmented = grounded_generation.last_retrieval_diagnostics
    assert augmented is not None
    assert augmented["selection"]["selected_candidate_count"] == 0
    assert augmented["selection"]["rejection_reason"] == "low_confidence_delivery_candidate"

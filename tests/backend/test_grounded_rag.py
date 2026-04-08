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
    assert any(item["message_type"] == "status_card" and item["title"] == "正在查项目资料" for item in detail["messages"])
    assert any(item["message_type"] == "status_card" and item["title"] == "正在整理结论" for item in detail["messages"])
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

    assert captured["limit"] == 14
    assert captured["apply_rerank"] is True
    assert captured["history"][-1]["content_md"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")
    assert answer["title"] == "调研结论"
    assert len(answer["sources"]) == 5
    assert any(item["message_type"] == "status_card" and item["title"] == "正在查项目资料" for item in detail["messages"])
    assert any(item["message_type"] == "status_card" and item["title"] == "正在整理结论" for item in detail["messages"])


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


def test_grounded_completion_budget_prefers_tighter_factoid_limit():
    service = LLMService()
    factoid_conversation = [{"message_type": "user_prompt", "content_md": "项目名称是什么？"}]
    complex_conversation = [{"message_type": "user_prompt", "content_md": "为什么这个方案可行？"}]

    assert service._grounded_completion_budget(conversation=factoid_conversation, research_mode=False) == 96
    assert service._grounded_completion_budget(conversation=complex_conversation, research_mode=False) == 220
    assert service._grounded_completion_budget(conversation=complex_conversation, research_mode=True) == 360


def test_build_grounded_messages_restored_and_guides_factoid_brevity():
    service = LLMService()
    messages = service._build_grounded_messages(
        conversation=[{"message_type": "user_prompt", "content_md": "项目名称是什么？"}],
        evidence_pack=[
            {
                "evidence_index": 1,
                "source_title": "Spec",
                "location_label": "项目名称 #1",
                "excerpt": "项目名称：室内空气质量检测与智能控制系统。",
                "llm_excerpt": "项目名称：室内空气质量检测与智能控制系统。",
                "source_kind": "project_source",
                "heading_path": "基础信息",
                "field_label": "项目名称",
            }
        ],
        research_mode=False,
        context_notes=["这是项目基础信息"],
    )

    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert "事实题尽量用一句话完成回答" in messages[-1]["content"]
    assert "excerpt: 项目名称：室内空气质量检测与智能控制系统。" in messages[-1]["content"]


def test_planner_and_precheck_messages_are_structured_for_research_and_web():
    service = LLMService()

    planner_messages = service._build_agent_planner_messages(
        query="How should we evaluate a RAG system end to end?",
        memory_notes=["The project already stores several notes about RAG evaluation."],
        research_mode=True,
        web_browsing=True,
    )
    precheck_messages = service._build_pre_answer_check_messages(
        query="How should we evaluate a RAG system end to end?",
        evidence_pack=[
            {
                "source_title": "RAG Eval Guide",
                "source_kind": "external_web",
                "excerpt": "Use retrieval, generation, and end-to-end evaluation together.",
            }
        ],
        plan_summary="Inspect project evidence first, then supplement with web evidence if needed",
        research_mode=True,
        web_browsing_enabled=True,
        web_used=True,
        diagnostics={"first_pass": {"top_score": 2.8, "term_coverage_ratio": 0.5}, "final": {"selected_evidence_count": 1}},
        project_retry_count=0,
    )

    assert "请严格输出 JSON" in planner_messages[-1]["content"]
    assert '"should_use_web":false' in planner_messages[-1]["content"]
    assert "网页补充是否可用：yes" in planner_messages[-1]["content"]
    assert "action 只能是 proceed / retry_project / need_web / insufficient" in precheck_messages[-1]["content"]
    assert "网页补充开关：on" in precheck_messages[-1]["content"]


def test_build_grounded_messages_mentions_web_led_evidence_mode():
    service = LLMService()

    messages = service._build_grounded_messages(
        conversation=[{"message_type": "user_prompt", "content_md": "??? RAG ????"}],
        evidence_pack=[
            {
                "evidence_index": 1,
                "source_title": "RAG Eval Guide",
                "location_label": "???? #1",
                "excerpt": "Use retrieval, generation, and end-to-end evaluation together.",
                "llm_excerpt": "Use retrieval, generation, and end-to-end evaluation together.",
                "source_kind": "external_web",
            }
        ],
        research_mode=True,
        context_notes=None,
        evidence_mode="web",
    )

    assert "\u8054\u7f51\u8865\u5145\u6765\u6e90" in messages[-1]["content"]
    assert "\u4e0d\u8981\u56e0\u4e3a\u7f3a\u5c11\u9879\u76ee\u5185\u8d44\u6599\u5c31\u9ed8\u8ba4\u62d2\u7b54" in messages[-1]["content"]


def test_grounded_generation_disclosure_note_mentions_web_led_answers():
    grounded_generation = sessions_route_service.grounded_generation
    note = grounded_generation._build_disclosure_note(
        {"used_general_knowledge": False, "evidence_status": "grounded"},
        evidences=[
            {
                "source_kind": "external_web",
                "source_title": "RAG Eval Guide",
                "canonical_uri": "https://example.com/rag-eval",
            }
        ],
    )

    assert note is not None
    assert "\u8054\u7f51\u8865\u5145\u6765\u6e90" in note


def test_grounded_generation_failure_skips_web_led_disclosure():
    grounded_generation = sessions_route_service.grounded_generation
    note = grounded_generation._build_disclosure_note(
        {"used_general_knowledge": False, "evidence_status": "grounded", "generation_failed": True},
        evidences=[
            {
                "source_kind": "external_web",
                "source_title": "RAG Eval Guide",
                "canonical_uri": "https://example.com/rag-eval",
            }
        ],
    )

    assert note is None


def test_grounded_generation_falls_back_to_relaxed_web_answer(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation

    monkeypatch.setattr(
        grounded_generation.llm,
        "generate_grounded_reply",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("strict json failed")),
    )
    monkeypatch.setattr(
        grounded_generation.llm,
        "generate_grounded_reply_fallback",
        lambda **kwargs: {
            "answer_md": "主要结论基于联网补充来源：Modular RAG 强调模块解耦、独立评测与可替换编排。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    answer = grounded_generation.generate_answer(
        history=[{"message_type": "user_prompt", "content_md": "具体介绍一下 Modular RAG"}],
        query="具体介绍一下 Modular RAG",
        research_mode=False,
        context_notes=None,
        evidences=[
            {
                "evidence_index": 1,
                "source_title": "Modular RAG Guide",
                "location_label": "Web #1",
                "excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "llm_excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "source_kind": "external_web",
                "canonical_uri": "https://example.com/modular-rag",
            }
        ],
    )

    assert "基于联网补充来源" in answer["answer_md"]
    assert answer["source_mode"] == "project_grounded"
    assert answer["evidence_status"] == "grounded"


def test_generate_grounded_reply_fallback_parses_json_payload(monkeypatch):
    service = LLMService()

    monkeypatch.setattr(service, "is_configured", lambda: True)
    monkeypatch.setattr(
        service,
        "_complete_messages",
        lambda **kwargs: '```json\n{"answer_md":"Recovered fallback answer.","used_general_knowledge":false,"evidence_status":"grounded"}\n```',
    )

    answer = service.generate_grounded_reply_fallback(
        conversation=[{"message_type": "user_prompt", "content_md": "What is Modular RAG?"}],
        evidence_pack=[
            {
                "evidence_index": 1,
                "source_title": "Modular RAG Guide",
                "location_label": "Web #1",
                "excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "llm_excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "source_kind": "external_web",
            }
        ],
        research_mode=False,
        context_notes=None,
        evidence_mode="web",
    )

    assert answer["answer_md"] == "Recovered fallback answer."
    assert answer["used_general_knowledge"] is False
    assert answer["evidence_status"] == "grounded"


def test_stream_grounded_generation_falls_back_before_first_chunk(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation

    def fake_stream_grounded_reply(**kwargs):
        raise RuntimeError("stream strict json failed")
        yield ""

    monkeypatch.setattr(
        grounded_generation.llm,
        "stream_grounded_reply",
        fake_stream_grounded_reply,
    )
    monkeypatch.setattr(
        grounded_generation.llm,
        "generate_grounded_reply_fallback",
        lambda **kwargs: {
            "answer_md": "主要结论基于联网补充来源：Modular RAG 可以把检索、路由和综合拆成可替换模块。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    iterator = grounded_generation.stream_generate_answer(
        history=[{"message_type": "user_prompt", "content_md": "具体介绍一下 Modular RAG"}],
        query="具体介绍一下 Modular RAG",
        research_mode=False,
        context_notes=None,
        evidences=[
            {
                "evidence_index": 1,
                "source_title": "Modular RAG Guide",
                "location_label": "Web #1",
                "excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "llm_excerpt": "Modular RAG separates retrieval, routing, synthesis, and evaluation stages.",
                "source_kind": "external_web",
                "canonical_uri": "https://example.com/modular-rag",
            }
        ],
    )

    chunks: list[str] = []
    while True:
        try:
            chunks.append(next(iterator))
        except StopIteration as stop:
            payload = stop.value
            break

    assert "".join(chunks) == payload["answer_md"]
    assert "基于联网补充来源" in payload["answer_md"]
    assert payload["source_mode"] == "project_grounded"
    assert payload["evidence_status"] == "grounded"


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


def test_grounded_generation_factoid_uses_tighter_evidence_budget(monkeypatch):
    grounded_generation = sessions_route_service.grounded_generation
    evidence = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": f"chunk-{index}",
            "source_id": f"source-{index}",
            "source_kind": "project_source",
            "source_title": f"Spec {index}",
            "source_type": "file_docx",
            "canonical_uri": f"file:///spec-{index}.docx",
            "location_label": f"Field #{index}",
            "excerpt": f"项目名称：室内空气质量检测系统 {index}",
            "normalized_text": f"项目名称：室内空气质量检测系统 {index}",
            "relevance_score": round(4.6 - (index * 0.1), 3),
            "section_type": "field",
            "heading_path": "基础信息",
            "field_label": "项目名称",
            "table_origin": None,
            "proposition_type": "identity",
        }
        for index in range(1, 4)
    ]
    diagnostics = {
        "original_query": "项目名称是什么？",
        "context_clues": [],
        "first_pass": {
            "hit_count": len(evidence),
            "top_score": 4.5,
            "title_hit_count": 1,
            "field_hit_count": 2,
            "term_coverage_ratio": 1.0,
            "is_low_confidence": False,
        },
        "triggered_second_pass": False,
        "retry_steps": [],
        "final": {
            "hit_count": len(evidence),
            "source_count": 3,
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
        query="项目名称是什么？",
        research_mode=False,
        history=None,
    )

    assert len(packed) == 2
    assert grounded_generation.last_retrieval_diagnostics["final"]["selected_evidence_count"] == 2


def test_grounded_generation_builds_shorter_llm_excerpt_for_factoid():
    grounded_generation = sessions_route_service.grounded_generation
    project_hits = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-field",
            "source_id": "source-1",
            "source_kind": "project_source",
            "source_title": "Spec",
            "source_type": "file_docx",
            "canonical_uri": "file:///spec.docx",
            "location_label": "项目名称 #1",
            "excerpt": "项目名称：室内空气质量检测系统，系统由采集模块、控制模块、显示模块和告警模块组成。",
            "normalized_text": "项目名称：室内空气质量检测系统，系统由采集模块、控制模块、显示模块和告警模块组成。",
            "relevance_score": 4.5,
            "section_type": "field",
            "heading_path": "基础信息",
            "field_label": "项目名称",
            "table_origin": None,
            "proposition_type": "identity",
        }
    ]
    diagnostics = {
        "original_query": "项目名称是什么？",
        "context_clues": [],
        "first_pass": {
            "hit_count": 1,
            "top_score": 4.5,
            "title_hit_count": 1,
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

    packed, _ = grounded_generation.prepare_agent_evidence(
        query="项目名称是什么？",
        project_hits=project_hits,
        project_diagnostics=diagnostics,
        research_mode=False,
    )

    assert packed
    assert "项目名称" in packed[0]["llm_excerpt"]
    assert len(packed[0]["llm_excerpt"]) <= len(packed[0]["source_excerpt"])


def test_explanation_queries_are_not_treated_as_factoid():
    grounded_generation = sessions_route_service.grounded_generation
    llm = LLMService()
    query = "\u4e3a\u4ec0\u4e48\u8fd9\u4e2a\u65b9\u6848\u53ef\u884c\uff1f"

    assert grounded_generation._query_looks_factoid(query) is False
    assert grounded_generation._target_evidence_limit(query=query, research_mode=False) == 3
    assert llm._query_looks_factoid(query) is False


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


def test_grounded_generation_keeps_project_evidence_ahead_of_external_web():
    grounded_generation = sessions_route_service.grounded_generation
    project_hits = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-project-1",
            "source_id": "source-1",
            "source_kind": "project_source",
            "source_title": "Quest 3 Notes",
            "source_type": "file_docx",
            "canonical_uri": "file:///quest3.docx",
            "location_label": "默认手柄 #1",
            "excerpt": "默认手柄：Touch Plus 控制器",
            "normalized_text": "默认手柄：Touch Plus 控制器",
            "relevance_score": 4.5,
            "section_type": "field",
            "heading_path": "设备配置",
            "field_label": "默认手柄",
            "table_origin": None,
            "proposition_type": "identity",
        },
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": "chunk-project-2",
            "source_id": "source-2",
            "source_kind": "project_source",
            "source_title": "Quest 3 Spec",
            "source_type": "file_pdf",
            "canonical_uri": "file:///quest3-spec.pdf",
            "location_label": "设备配置 #1",
            "excerpt": "Quest 3 随机附带 Touch Plus 控制器。",
            "normalized_text": "Quest 3 随机附带 Touch Plus 控制器。",
            "relevance_score": 4.1,
            "section_type": "body",
            "heading_path": "设备配置",
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
        },
    ]
    external_hits = [
        {
            "project_id": "project-1",
            "project_name": "Grounded Project",
            "chunk_id": None,
            "source_id": None,
            "source_kind": "external_web",
            "source_title": "Quest 3 Blog",
            "source_type": "web_page",
            "canonical_uri": "https://example.com/quest3-blog",
            "external_uri": "https://example.com/quest3-blog",
            "location_label": "网页补充 #1",
            "excerpt": "External blog summary about Touch Plus.",
            "normalized_text": "External blog summary about Touch Plus.",
            "relevance_score": 5.2,
            "section_type": "body",
            "heading_path": None,
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
        }
    ]
    diagnostics = {
        "original_query": "Quest 3 默认手柄是什么？",
        "context_clues": [],
        "first_pass": {
            "hit_count": len(project_hits),
            "top_score": 4.5,
            "title_hit_count": 1,
            "field_hit_count": 1,
            "term_coverage_ratio": 1.0,
            "is_low_confidence": False,
        },
        "triggered_second_pass": False,
        "retry_steps": [],
        "final": {
            "hit_count": len(project_hits),
            "source_count": 2,
            "grounded_candidate": True,
            "returned_hit_count": len(project_hits),
        },
    }

    packed, packed_diagnostics = grounded_generation.prepare_agent_evidence(
        query="Quest 3 默认手柄是什么？",
        project_hits=project_hits,
        project_diagnostics=diagnostics,
        research_mode=False,
        external_hits=external_hits,
    )

    assert packed
    assert packed[0]["source_kind"] == "project_source"
    assert all(item["source_kind"] == "project_source" for item in packed)
    assert packed_diagnostics["final"]["external_source_count"] == 0


def test_summary_and_report_cards_keep_final_sources(client, monkeypatch, html_server):
    project = _create_project(client, name="Result Cards Source Sync")
    session = _create_session(client, project["id"])
    source_url = _create_html_source(
        html_server,
        "result-card-source.html",
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
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    send_response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "我用的是哪个手柄？", "deep_research": False},
    )
    assert send_response.status_code == 200, send_response.text

    summary_response = client.post(f"/api/v1/sessions/{session['id']}/summary")
    report_response = client.post(f"/api/v1/sessions/{session['id']}/report")

    assert summary_response.status_code == 200, summary_response.text
    assert report_response.status_code == 200, report_response.text

    detail = client.get(f"/api/v1/sessions/{session['id']}").json()["item"]
    summary_card = next(item for item in detail["messages"] if item["message_type"] == "summary_card")
    report_card = next(item for item in detail["messages"] if item["message_type"] == "report_card")

    assert len(summary_card["sources"]) == 1
    assert len(report_card["sources"]) == 1
    assert summary_card["sources"][0]["source_title"] == "Quest 3 Notes"
    assert report_card["sources"][0]["source_title"] == "Quest 3 Notes"
    assert summary_card["source_mode"] == "project_grounded"
    assert report_card["source_mode"] == "project_grounded"

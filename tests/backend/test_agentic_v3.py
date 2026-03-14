from types import SimpleNamespace

from app.api.routes.sessions import service as sessions_route_service
from app.repositories.memory_repository import MemoryRepository


def _create_project(client, *, name: str = "Agentic V3 Project") -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "description": "V3 graph orchestration verification project",
            "default_external_policy": "allow_external",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _create_session(client, project_id: str) -> dict:
    response = client.post(f"/api/v1/projects/{project_id}/sessions")
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _create_web_source(client, project_id: str, html_server: dict, filename: str, title: str, body: str) -> dict:
    path = html_server["root"] / filename
    path.write_text(f"<html><head><title>{title}</title></head><body><p>{body}</p></body></html>", encoding="utf-8")
    response = client.post(
        f"/api/v1/projects/{project_id}/sources/web",
        json={"url": f"{html_server['base_url']}/{filename}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def _diagnostics_for(evidence: list[dict], *, grounded_candidate: bool = True) -> dict:
    top_score = max((float(item.get("relevance_score", 0.0)) for item in evidence), default=0.0)
    return {
        "original_query": "test",
        "context_clues": [],
        "first_pass": {
            "hit_count": len(evidence),
            "top_score": top_score,
            "title_hit_count": 1 if evidence else 0,
            "field_hit_count": 0,
            "term_coverage_ratio": 1.0 if evidence else 0.0,
            "is_low_confidence": not grounded_candidate,
        },
        "triggered_second_pass": False,
        "retry_steps": [],
        "final": {
            "hit_count": len(evidence),
            "source_count": len({item.get("source_id") or item.get("canonical_uri") for item in evidence}),
            "grounded_candidate": grounded_candidate and bool(evidence),
            "returned_hit_count": len(evidence),
        },
    }


def _project_evidence(source: dict, *, excerpt: str) -> list[dict]:
    return [
        {
            "project_id": source["project_id"],
            "project_name": source["project_name"],
            "chunk_id": None,
            "source_id": source["id"],
            "source_kind": "project_source",
            "source_title": source["title"],
            "source_type": source["source_type"],
            "canonical_uri": source["canonical_uri"],
            "external_uri": None,
            "location_label": "body #1",
            "excerpt": excerpt,
            "normalized_text": excerpt,
            "relevance_score": 4.4,
            "section_type": "field",
            "heading_path": "设备配置",
            "field_label": "默认手柄",
            "table_origin": None,
            "proposition_type": None,
        }
    ]


def _external_evidence(project: dict, *, excerpt: str) -> list[dict]:
    return [
        {
            "project_id": project["id"],
            "project_name": project["name"],
            "chunk_id": None,
            "source_id": None,
            "source_kind": "external_web",
            "source_title": "External Research Note",
            "source_type": "web_page",
            "canonical_uri": "https://example.com/external-note",
            "external_uri": "https://example.com/external-note",
            "location_label": "网页补充 #1",
            "excerpt": excerpt,
            "normalized_text": excerpt,
            "relevance_score": 3.6,
            "section_type": "body",
            "heading_path": None,
            "field_label": None,
            "table_origin": None,
            "proposition_type": None,
        }
    ]


def test_v3_web_browsing_disabled_does_not_call_external_web_tool(client, monkeypatch, html_server):
    project = _create_project(client, name="No Web Branch")
    session = _create_session(client, project["id"])
    source = _create_web_source(
        client,
        project["id"],
        html_server,
        "project-source.html",
        "Quest 3 Notes",
        "Quest 3 ships with Touch Plus controllers by default.",
    )
    evidence = _project_evidence(source, excerpt="Quest 3 ships with Touch Plus controllers by default.")

    called = {"web": False}

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: (evidence, _diagnostics_for(evidence)),
    )
    monkeypatch.setattr(
        sessions_route_service.agent.web,
        "build_external_evidence",
        lambda **kwargs: called.__setitem__("web", True) or [],
    )
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "项目资料说明 Quest 3 默认搭配 Touch Plus 手柄。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "Quest 3 默认手柄是什么？", "deep_research": False, "web_browsing": False},
    )
    assert response.status_code == 200, response.text
    detail = response.json()["item"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")

    assert called["web"] is False
    assert answer["source_mode"] == "project_grounded"
    assert answer["sources"][0]["source_kind"] == "project_source"


def test_v3_web_browsing_enabled_can_return_external_web_evidence(client, monkeypatch):
    project = _create_project(client, name="Web Branch Project")
    session = _create_session(client, project["id"])
    external_hits = _external_evidence(project, excerpt="External benchmark notes from the web.")

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: ([], _diagnostics_for([], grounded_candidate=False)),
    )
    monkeypatch.setattr(
        sessions_route_service.agent.web,
        "build_external_evidence",
        lambda **kwargs: external_hits,
    )
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "我补充了网页资料，并整理了外部 benchmark 结果。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "请联网补充 benchmark 结论。", "deep_research": False, "web_browsing": True},
    )
    assert response.status_code == 200, response.text
    detail = response.json()["item"]
    answer = next(item for item in detail["messages"] if item["message_type"] == "assistant_answer")

    assert answer["source_mode"] == "project_grounded"
    assert answer["sources"]
    assert answer["sources"][0]["source_kind"] == "external_web"
    assert answer["sources"][0]["external_uri"] == "https://example.com/external-note"


def test_v3_successful_grounded_answers_persist_memory_entries(client, monkeypatch, html_server):
    project = _create_project(client, name="Memory Project")
    session = _create_session(client, project["id"])
    source = _create_web_source(
        client,
        project["id"],
        html_server,
        "memory-source.html",
        "Quest 3 Notes",
        "Quest 3 ships with Touch Plus controllers by default.",
    )
    evidence = _project_evidence(source, excerpt="Quest 3 默认手柄是 Touch Plus 控制器。")

    monkeypatch.setattr(
        sessions_route_service.search,
        "retrieve_project_evidence_with_diagnostics",
        lambda *args, **kwargs: (evidence, _diagnostics_for(evidence)),
    )
    monkeypatch.setattr(
        sessions_route_service.llm,
        "generate_grounded_reply",
        lambda **kwargs: {
            "answer_md": "Quest 3 默认搭配 Touch Plus 控制器，可以继续追问兼容性。",
            "used_general_knowledge": False,
            "evidence_status": "grounded",
        },
    )

    response = client.post(
        f"/api/v1/sessions/{session['id']}/messages",
        json={"content": "Quest 3 默认手柄是什么？", "deep_research": False, "web_browsing": False},
    )
    assert response.status_code == 200, response.text

    repository = MemoryRepository()
    session_entries = repository.list_scope_entries(scope_type="session", scope_id=session["id"])
    project_entries = repository.list_scope_entries(scope_type="project", scope_id=project["id"])

    assert session_entries
    assert project_entries
    assert any("Touch Plus" in entry.fact_text for entry in project_entries)


def test_v2_runtime_flag_still_routes_to_legacy_send_flow(monkeypatch):
    captured = {"v2": False, "v3": False}

    monkeypatch.setattr(
        "app.services.session_service.get_settings",
        lambda: SimpleNamespace(agent_runtime_version="v2"),
    )
    monkeypatch.setattr(
        sessions_route_service,
        "_send_message_v2",
        lambda **kwargs: captured.__setitem__("v2", True) or {"id": "legacy"},
    )
    monkeypatch.setattr(
        sessions_route_service,
        "_send_message_v3",
        lambda **kwargs: captured.__setitem__("v3", True) or {"id": "graph"},
    )

    result = sessions_route_service.send_message(
        session_id="session-legacy",
        content="legacy",
        deep_research=False,
        web_browsing=True,
    )

    assert result == {"id": "legacy"}
    assert captured["v2"] is True
    assert captured["v3"] is False

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.settings import get_settings
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_repository import SourceRepository
from app.services.grounded_generation_service import GroundedGenerationService
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.search_service import SearchService
from app.services.web_research_service import WebResearchService


class AgentState(TypedDict, total=False):
    session_id: str
    project_id: str
    project_name: str
    query: str
    history: list[dict]
    research_mode: bool
    web_browsing: bool
    project_allows_external: bool
    status_updates: list[dict]
    memory: dict
    context_notes: list[str]
    plan: dict
    graph_profile: str
    project_hits: list[dict]
    project_diagnostics: dict
    external_hits: list[dict]
    final_evidence: list[dict]
    final_diagnostics: dict
    pre_answer_check: dict
    web_attempted: bool


@dataclass
class AgentTurnResult:
    evidence_pack: list[dict]
    context_notes: list[str]
    status_messages: list[dict]
    diagnostics: dict
    used_web: bool
    graph_profile: str
    plan_summary: str


class AgentOrchestratorService:
    def __init__(
        self,
        *,
        llm_service: LLMService | None = None,
        search_service: SearchService | None = None,
        grounded_generation_service: GroundedGenerationService | None = None,
    ) -> None:
        self.llm = llm_service or LLMService()
        self.search = search_service or SearchService(llm_service=self.llm)
        self.grounded_generation = grounded_generation_service or GroundedGenerationService(
            search_service=self.search,
            llm_service=self.llm,
        )
        self.memory = MemoryService()
        self.web = WebResearchService()
        self.projects = ProjectRepository()
        self.sources = SourceRepository()
        self._chat_graph = self._build_chat_graph().compile()
        self._research_graph = self._build_research_graph().compile()

    def orchestrate_turn(
        self,
        *,
        session_id: str,
        project_id: str,
        project_name: str,
        query: str,
        history: list[dict],
        research_mode: bool,
        web_browsing: bool,
    ) -> AgentTurnResult:
        project = self.projects.get_project(project_id)
        project_allows_external = bool(project and project.default_external_policy == "allow_external")
        initial_state: AgentState = {
            "session_id": session_id,
            "project_id": project_id,
            "project_name": project_name,
            "query": query,
            "history": history,
            "research_mode": research_mode,
            "web_browsing": web_browsing,
            "project_allows_external": project_allows_external,
            "status_updates": [],
            "context_notes": [],
            "external_hits": [],
            "web_attempted": False,
        }
        graph = self._research_graph if research_mode else self._chat_graph
        result = graph.invoke(initial_state)
        return AgentTurnResult(
            evidence_pack=result.get("final_evidence", []),
            context_notes=result.get("context_notes", []),
            status_messages=result.get("status_updates", []),
            diagnostics=result.get("final_diagnostics") or result.get("project_diagnostics") or {},
            used_web=bool(result.get("web_attempted")),
            graph_profile=result.get("graph_profile", "research" if research_mode else "chat"),
            plan_summary=result.get("plan", {}).get("summary", ""),
        )

    def persist_answer_memory(
        self,
        *,
        project_id: str,
        session_id: str,
        query: str,
        answer_md: str,
        evidences: list[dict],
        message_id: str,
    ) -> None:
        if not evidences:
            return
        self.memory.persist_from_answer(
            project_id=project_id,
            session_id=session_id,
            query=query,
            answer_md=answer_md,
            evidences=evidences,
            source_message_id=message_id,
        )

    def read_source_context(self, source_id: str) -> dict:
        source = self.sources.get_source(source_id)
        preview_chunks = self.sources.get_source_preview_chunks(source_id, limit=6)
        return {
            "source": source.to_summary() if source else None,
            "preview_chunks": [chunk.to_summary() for chunk in preview_chunks],
        }

    def _build_chat_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("load_turn_context", self._load_turn_context)
        graph.add_node("load_memory", self._load_memory)
        graph.add_node("classify_turn", self._classify_turn)
        graph.add_node("project_retrieval", self._project_retrieval)
        graph.add_node("optional_web_branch", self._optional_web_branch)
        graph.add_node("evidence_selection", self._evidence_selection)
        graph.add_node("pre_answer_check", self._pre_answer_check)
        graph.add_edge(START, "load_turn_context")
        graph.add_edge("load_turn_context", "load_memory")
        graph.add_edge("load_memory", "classify_turn")
        graph.add_edge("classify_turn", "project_retrieval")
        graph.add_edge("project_retrieval", "optional_web_branch")
        graph.add_edge("optional_web_branch", "evidence_selection")
        graph.add_edge("evidence_selection", "pre_answer_check")
        graph.add_conditional_edges(
            "pre_answer_check",
            self._route_after_pre_answer_check,
            {
                "retry_web": "optional_web_branch",
                "done": END,
            },
        )
        return graph

    def _build_research_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("load_turn_context", self._load_turn_context)
        graph.add_node("load_memory", self._load_memory)
        graph.add_node("plan_turn", self._plan_turn)
        graph.add_node("project_retrieval", self._project_retrieval)
        graph.add_node("optional_web_branch", self._optional_web_branch)
        graph.add_node("fuse_evidence", self._evidence_selection)
        graph.add_node("pre_answer_check", self._pre_answer_check)
        graph.add_edge(START, "load_turn_context")
        graph.add_edge("load_turn_context", "load_memory")
        graph.add_edge("load_memory", "plan_turn")
        graph.add_edge("plan_turn", "project_retrieval")
        graph.add_edge("project_retrieval", "optional_web_branch")
        graph.add_edge("optional_web_branch", "fuse_evidence")
        graph.add_edge("fuse_evidence", "pre_answer_check")
        graph.add_conditional_edges(
            "pre_answer_check",
            self._route_after_pre_answer_check,
            {
                "retry_web": "optional_web_branch",
                "done": END,
            },
        )
        return graph

    def _load_turn_context(self, state: AgentState) -> AgentState:
        profile = "research" if state["research_mode"] else "chat"
        return {
            "graph_profile": profile,
            "status_updates": self._append_status(
                state,
                title="正在查项目资料",
                body="正在根据当前会话和项目资料整理本轮问题。",
            ),
        }

    def _load_memory(self, state: AgentState) -> AgentState:
        memory = self.memory.lookup(
            project_id=state["project_id"],
            session_id=state["session_id"],
            query=state["query"],
            limit=6,
        )
        return {
            "memory": memory,
            "context_notes": memory["notes"],
        }

    def _classify_turn(self, state: AgentState) -> AgentState:
        plan = self.llm.plan_agent_turn(
            query=state["query"],
            memory_notes=state.get("context_notes", []),
            research_mode=False,
            web_browsing=bool(state.get("web_browsing")),
        )
        return {"plan": plan}

    def _plan_turn(self, state: AgentState) -> AgentState:
        plan = self.llm.plan_agent_turn(
            query=state["query"],
            memory_notes=state.get("context_notes", []),
            research_mode=True,
            web_browsing=bool(state.get("web_browsing")),
        )
        return {"plan": plan}

    def _project_retrieval(self, state: AgentState) -> AgentState:
        query = state.get("plan", {}).get("working_query") or state["query"]
        limit = 12 if state["research_mode"] else 8
        apply_rerank = True if state["research_mode"] else self.search.should_rerank_query(query)
        project_hits, diagnostics = self.search.retrieve_project_evidence_with_diagnostics(
            state["project_id"],
            query,
            limit=limit,
            apply_rerank=apply_rerank,
            history=state["history"],
        )
        return {
            "project_hits": project_hits,
            "project_diagnostics": diagnostics,
        }

    def _optional_web_branch(self, state: AgentState) -> AgentState:
        if state.get("web_attempted"):
            return {}
        if not self._should_attempt_web(state):
            return {}
        external_hits = self.web.build_external_evidence(
            project_id=state["project_id"],
            project_name=state["project_name"],
            query=state.get("plan", {}).get("working_query") or state["query"],
            limit=get_settings().agent_web_result_limit,
        )
        status_updates = state.get("status_updates", [])
        if external_hits:
            status_updates = self._append_status(
                state,
                title="正在联网补充",
                body="已找到可补充的网页资料，正在提炼与当前问题最相关的部分。",
            )
        return {
            "external_hits": external_hits,
            "web_attempted": True,
            "status_updates": status_updates,
        }

    def _evidence_selection(self, state: AgentState) -> AgentState:
        final_evidence, diagnostics = self.grounded_generation.prepare_agent_evidence(
            query=state["query"],
            project_hits=state.get("project_hits", []),
            project_diagnostics=state.get("project_diagnostics")
            or self._empty_diagnostics(state["query"]),
            research_mode=state["research_mode"],
            external_hits=state.get("external_hits", []),
        )
        status_updates = self._append_status(
            state,
            title="正在整理结论",
            body="正在整合命中的项目资料和补充证据，准备生成回答。",
        )
        return {
            "final_evidence": final_evidence,
            "final_diagnostics": diagnostics,
            "status_updates": status_updates,
        }

    def _pre_answer_check(self, state: AgentState) -> AgentState:
        check = self.llm.check_agent_answer_readiness(
            query=state["query"],
            evidence_pack=state.get("final_evidence", []),
            plan_summary=state.get("plan", {}).get("summary", ""),
            research_mode=state["research_mode"],
            web_browsing_enabled=bool(state.get("web_browsing") and state.get("project_allows_external")),
            web_used=bool(state.get("web_attempted")),
        )
        return {"pre_answer_check": check}

    def _route_after_pre_answer_check(self, state: AgentState) -> str:
        check = state.get("pre_answer_check", {})
        if (
            check.get("action") == "need_web"
            and state.get("web_browsing")
            and state.get("project_allows_external")
            and not state.get("web_attempted")
        ):
            return "retry_web"
        return "done"

    def _should_attempt_web(self, state: AgentState) -> bool:
        if not state.get("web_browsing"):
            return False
        if not state.get("project_allows_external"):
            return False
        plan = state.get("plan", {})
        diagnostics = state.get("project_diagnostics") or {}
        first_pass = diagnostics.get("first_pass", {})
        top_score = float(first_pass.get("top_score", 0.0) or 0.0)
        grounded_candidate = bool(diagnostics.get("final", {}).get("grounded_candidate"))
        if plan.get("should_use_web"):
            return True
        if not grounded_candidate:
            return True
        if state["research_mode"] and top_score < 3.6:
            return True
        if first_pass.get("is_low_confidence"):
            return True
        return False

    def _append_status(self, state: AgentState, *, title: str, body: str) -> list[dict]:
        current = list(state.get("status_updates", []))
        if any(item["title"] == title for item in current):
            return current
        current.append({"title": title, "content_md": body})
        return current

    def _empty_diagnostics(self, query: str) -> dict:
        return {
            "original_query": query,
            "context_clues": [],
            "first_pass": {
                "hit_count": 0,
                "top_score": 0.0,
                "title_hit_count": 0,
                "field_hit_count": 0,
                "term_coverage_ratio": 0.0,
                "is_low_confidence": True,
            },
            "triggered_second_pass": False,
            "retry_steps": [],
            "final": {
                "hit_count": 0,
                "source_count": 0,
                "grounded_candidate": False,
                "returned_hit_count": 0,
            },
        }

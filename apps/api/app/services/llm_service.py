from __future__ import annotations

import json
import re
from collections.abc import Iterator

import httpx

from app.core.settings import get_settings


GROUNDING_DISCLOSURE_NOTE = "补充说明：部分补充解释来自通用常识，不来自当前项目资料。"


class GroundedJsonStreamParser:
    def __init__(self, *, sanitizer) -> None:
        self._sanitize_output = sanitizer
        self.mode: str = "unknown"
        self.raw_text = ""
        self._scan_index = 0
        self._inside_answer = False
        self._escape = False
        self._answer_literal = ""
        self.answer_md = ""

    def push(self, chunk: str) -> list[str]:
        self.raw_text += chunk
        self._promote_mode()
        if self.mode == "markdown":
            cleaned = self._sanitize_output(self.raw_text)
            delta = cleaned[len(self.answer_md) :]
            self.answer_md = cleaned
            return [delta] if delta else []
        if self.mode != "json":
            return []
        self._consume_answer_literal()
        try:
            decoded = json.loads(f'"{self._answer_literal}"')
        except json.JSONDecodeError:
            return []
        delta = decoded[len(self.answer_md) :]
        self.answer_md = decoded
        return [delta] if delta else []

    def _promote_mode(self) -> None:
        if self.mode != "unknown":
            return
        stripped = self.raw_text.lstrip()
        if not stripped:
            return
        if stripped[0] != "{":
            self.mode = "markdown"
            return
        if '"answer_md"' in self.raw_text:
            self.mode = "json"
            return

    def _consume_answer_literal(self) -> None:
        if not self._inside_answer:
            marker_index = self.raw_text.find('"answer_md"', self._scan_index)
            if marker_index == -1:
                self._scan_index = max(0, len(self.raw_text) - 24)
                return
            colon_index = self.raw_text.find(":", marker_index)
            if colon_index == -1:
                self._scan_index = marker_index
                return
            quote_index = self.raw_text.find('"', colon_index)
            if quote_index == -1:
                self._scan_index = colon_index
                return
            self._inside_answer = True
            self._scan_index = quote_index + 1

        while self._inside_answer and self._scan_index < len(self.raw_text):
            character = self.raw_text[self._scan_index]
            self._scan_index += 1
            if self._escape:
                self._answer_literal += character
                self._escape = False
                continue
            if character == "\\":
                self._answer_literal += character
                self._escape = True
                continue
            if character == '"':
                self._inside_answer = False
                break
            self._answer_literal += character


class LLMService:
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.llm_api_key and settings.llm_model and settings.llm_base_url)

    def generate_chat_reply(
        self,
        *,
        conversation: list[dict],
        research_mode: bool = False,
        context_notes: list[str] | None = None,
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("LLM is not configured.")
        messages = self._build_chat_messages(
            conversation=conversation,
            research_mode=research_mode,
            context_notes=context_notes,
        )
        text = self._complete_messages(messages=messages, temperature=0.7)
        text = self._sanitize_output(text)
        if not text:
            raise RuntimeError("LLM returned an empty response.")
        return text

    def stream_chat_reply(
        self,
        *,
        conversation: list[dict],
        research_mode: bool = False,
        context_notes: list[str] | None = None,
    ) -> Iterator[str]:
        if not self.is_configured():
            raise RuntimeError("LLM is not configured.")
        messages = self._build_chat_messages(
            conversation=conversation,
            research_mode=research_mode,
            context_notes=context_notes,
        )
        raw_text = ""
        cleaned_text = ""
        for chunk in self._stream_completion(messages=messages, temperature=0.7):
            raw_text += chunk
            next_cleaned = self._sanitize_output(raw_text)
            if len(next_cleaned) <= len(cleaned_text):
                continue
            delta = next_cleaned[len(cleaned_text) :]
            cleaned_text = next_cleaned
            if delta:
                yield delta
        if not cleaned_text.strip():
            raise RuntimeError("LLM returned an empty streamed response.")

    def generate_grounded_reply(
        self,
        *,
        conversation: list[dict],
        evidence_pack: list[dict],
        research_mode: bool = False,
        context_notes: list[str] | None = None,
    ) -> dict:
        if not self.is_configured():
            raise RuntimeError("LLM is not configured.")
        messages = self._build_grounded_messages(
            conversation=conversation,
            evidence_pack=evidence_pack,
            research_mode=research_mode,
            context_notes=context_notes,
        )
        raw_text = self._complete_messages(messages=messages, temperature=0.2)
        return self.parse_grounded_reply(raw_text)

    def generate_hypothetical_passage(self, *, query: str, research_mode: bool = False) -> str:
        if not self.is_configured():
            return ""
        messages = self._build_hyde_messages(query=query, research_mode=research_mode)
        try:
            text = self._complete_messages(messages=messages, temperature=0.3)
        except RuntimeError:
            return ""
        return self._sanitize_output(text)

    def stream_grounded_reply(
        self,
        *,
        conversation: list[dict],
        evidence_pack: list[dict],
        research_mode: bool = False,
        context_notes: list[str] | None = None,
    ) -> Iterator[str]:
        if not self.is_configured():
            raise RuntimeError("LLM is not configured.")
        messages = self._build_grounded_messages(
            conversation=conversation,
            evidence_pack=evidence_pack,
            research_mode=research_mode,
            context_notes=context_notes,
        )
        parser = GroundedJsonStreamParser(sanitizer=self._sanitize_output)
        for chunk in self._stream_completion(messages=messages, temperature=0.2):
            for delta in parser.push(chunk):
                yield delta

        parsed = self.parse_grounded_reply(parser.raw_text, streamed_answer=parser.answer_md)
        if len(parsed["answer_md"]) > len(parser.answer_md):
            yield parsed["answer_md"][len(parser.answer_md) :]
        return parsed

    def plan_agent_turn(
        self,
        *,
        query: str,
        memory_notes: list[str],
        research_mode: bool,
        web_browsing: bool,
    ) -> dict:
        if not self.is_configured():
            return self._heuristic_plan_agent_turn(
                query=query,
                memory_notes=memory_notes,
                research_mode=research_mode,
                web_browsing=web_browsing,
            )
        messages = self._build_agent_planner_messages(
            query=query,
            memory_notes=memory_notes,
            research_mode=research_mode,
            web_browsing=web_browsing,
        )
        try:
            raw_text = self._complete_messages(messages=messages, temperature=0.2)
            payload = json.loads(self._strip_code_fence(self._sanitize_output(raw_text)))
        except (RuntimeError, json.JSONDecodeError):
            return self._heuristic_plan_agent_turn(
                query=query,
                memory_notes=memory_notes,
                research_mode=research_mode,
                web_browsing=web_browsing,
            )

        complexity = str(payload.get("complexity", "complex" if research_mode else "simple")).strip().lower()
        if complexity not in {"simple", "complex"}:
            complexity = "complex" if research_mode else "simple"
        task_type = str(payload.get("task_type", "summarize" if research_mode else "lookup")).strip().lower()
        if task_type not in {"lookup", "follow_up", "summarize", "compare", "explain"}:
            task_type = "summarize" if research_mode else "lookup"
        return {
            "working_query": str(payload.get("working_query", "")).strip() or query,
            "summary": str(payload.get("summary", "")).strip() or ("structured_research" if research_mode else "chat_turn"),
            "should_use_web": bool(payload.get("should_use_web", False)) and web_browsing,
            "complexity": complexity,
            "task_type": task_type,
        }

    def check_agent_answer_readiness(
        self,
        *,
        query: str,
        evidence_pack: list[dict],
        plan_summary: str,
        research_mode: bool,
        web_browsing_enabled: bool,
        web_used: bool,
        diagnostics: dict | None = None,
        project_retry_count: int = 0,
    ) -> dict:
        if not self.is_configured():
            return self._heuristic_check_agent_answer_readiness(
                query=query,
                evidence_pack=evidence_pack,
                research_mode=research_mode,
                web_browsing_enabled=web_browsing_enabled,
                web_used=web_used,
                diagnostics=diagnostics,
                project_retry_count=project_retry_count,
            )
        messages = self._build_pre_answer_check_messages(
            query=query,
            evidence_pack=evidence_pack,
            plan_summary=plan_summary,
            research_mode=research_mode,
            web_browsing_enabled=web_browsing_enabled,
            web_used=web_used,
            diagnostics=diagnostics or {},
            project_retry_count=project_retry_count,
        )
        try:
            raw_text = self._complete_messages(messages=messages, temperature=0.1)
            payload = json.loads(self._strip_code_fence(self._sanitize_output(raw_text)))
        except (RuntimeError, json.JSONDecodeError):
            return self._heuristic_check_agent_answer_readiness(
                query=query,
                evidence_pack=evidence_pack,
                research_mode=research_mode,
                web_browsing_enabled=web_browsing_enabled,
                web_used=web_used,
                diagnostics=diagnostics,
                project_retry_count=project_retry_count,
            )

        action = str(payload.get("action", "proceed")).strip().lower()
        if action not in {"proceed", "need_web", "retry_project", "insufficient"}:
            action = "proceed"
        return {
            "action": action,
            "reason": str(payload.get("reason", "")).strip(),
            "focus": str(payload.get("focus", "")).strip(),
        }

    def parse_grounded_reply(self, raw_text: str, *, streamed_answer: str = "") -> dict:
        cleaned = self._sanitize_output(raw_text)
        stripped = self._strip_code_fence(cleaned)
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            answer_md = self._normalize_grounded_markdown(streamed_answer or stripped)
            if not answer_md.strip():
                raise RuntimeError("Grounded reply fallback was empty.")
            return {
                "answer_md": answer_md.strip(),
                "used_general_knowledge": False,
                "evidence_status": "grounded",
            }

        answer_md = str(payload.get("answer_md", "")).strip() or streamed_answer.strip()
        if not answer_md:
            raise RuntimeError("Grounded reply JSON did not include answer_md.")
        answer_md = self._normalize_grounded_markdown(answer_md)

        evidence_status = str(payload.get("evidence_status", "grounded")).strip().lower()
        if evidence_status not in {"grounded", "insufficient", "conflicting"}:
            evidence_status = "grounded"

        return {
            "answer_md": answer_md,
            "used_general_knowledge": bool(payload.get("used_general_knowledge", False)),
            "evidence_status": evidence_status,
        }

    def _build_chat_messages(
        self,
        *,
        conversation: list[dict],
        research_mode: bool,
        context_notes: list[str] | None,
    ) -> list[dict]:
        system_prompt = (
            "你是一个中文优先的知识工作助手。当前项目没有命中足够的本地资料时，"
            "你可以按通用大模型对话模式自然回答。请保持准确、简洁，不确定时明确说明不确定。"
        )
        if research_mode:
            system_prompt += " 本次开启了深度调研模式，可以给出更结构化的分析与结论。"
        if context_notes:
            system_prompt += "\n\n本轮可参考的上下文：\n" + "\n".join(f"- {note}" for note in context_notes[:5])

        history = self._conversation_to_messages(conversation)[-12:]
        return [{"role": "system", "content": system_prompt}, *history]

    def _build_grounded_messages(
        self,
        *,
        conversation: list[dict],
        evidence_pack: list[dict],
        research_mode: bool,
        context_notes: list[str] | None,
    ) -> list[dict]:
        history = self._conversation_to_messages(conversation)
        recent_history = history[-12:]
        if not recent_history or recent_history[-1]["role"] != "user":
            raise RuntimeError("Grounded reply requires the latest user message.")

        current_question = recent_history[-1]["content"]
        prior_history = recent_history[:-1]
        evidence_lines: list[str] = []
        for index, item in enumerate(evidence_pack, start=1):
            evidence_index = item.get("evidence_index", index)
            context_parts = []
            if item.get("heading_path"):
                context_parts.append(f"heading_path={item['heading_path']}")
            if item.get("field_label"):
                context_parts.append(f"field_label={item['field_label']}")
            if item.get("proposition_type"):
                context_parts.append(f"proposition_type={item['proposition_type']}")
            if item.get("source_kind"):
                context_parts.append(f"source_kind={item['source_kind']}")
            evidence_lines.append(
                "\n".join(
                    [
                        f"[证据 {evidence_index}]",
                        f"source_id: {item.get('source_id') or 'external'}",
                        f"title: {item['source_title']}",
                        f"source_type: {item['source_type']}",
                        f"location: {item['location_label']}",
                        f"context: {'; '.join(context_parts)}" if context_parts else "context: none",
                        f"excerpt: {item['excerpt']}",
                        f"source_excerpt: {item['source_excerpt']}" if item.get("source_excerpt") else "source_excerpt: none",
                    ]
                )
            )
        answer_style = (
            "如果问题复杂，可以在 answer_md 里使用小标题和短列表。"
            if research_mode
            else "answer_md 默认用自然短文回答，只有内容天然成列表时才使用列表。"
        )
        context_block = ""
        if context_notes:
            context_block = "\n\n可参考的会话/项目上下文：\n" + "\n".join(f"- {note}" for note in context_notes[:5])
        grounded_prompt = (
            "你正在基于项目资料回答用户问题。请严格输出 JSON，不要输出代码块，不要输出额外解释。"
            '\n\nJSON 必须包含以下键，并保持 answer_md 放在第一位：\n{"answer_md":"...","used_general_knowledge":false,"evidence_status":"grounded"}'
            "\n\n规则："
            "\n1. 优先依据给定证据回答。"
            "\n2. 可以补少量通用常识让回答更自然，但不能把通用常识伪装成项目资料。"
            "\n3. 如果证据不足，evidence_status 必须是 insufficient，answer_md 里也要明确说不足。"
            "\n4. 如果证据互相冲突，evidence_status 必须是 conflicting，answer_md 里也要明确说冲突。"
            "\n5. 如果证据足够，evidence_status 用 grounded。"
            "\n6. 不要在正文中主动枚举来源标题，除非必须用来源名消歧。"
            f"\n7. {answer_style}"
            "\n8. 如果答案天然适合分点，必须输出合法 Markdown 列表；每个编号或项目符号都要单独占一行。"
            "\n9. 只有在确实补充了项目外通用常识时，used_general_knowledge 才能为 true。"
            f"\n\n用户问题：\n{current_question}"
            f"{context_block}"
            "\n\n可用项目证据：\n"
            + "\n\n".join(evidence_lines)
        )

        return [
            {"role": "system", "content": "你是一个中文优先的 grounded RAG 助手。"},
            *prior_history,
            {"role": "user", "content": grounded_prompt},
        ]

    def _build_hyde_messages(self, *, query: str, research_mode: bool) -> list[dict]:
        prompt = (
            "你正在为 RAG 检索生成一段假设性资料摘要。"
            "\n请直接输出一段简洁中文，不要解释，不要加引号，不要编造具体来源。"
            "\n目标是把用户问题改写成更容易被知识库召回的描述，尽量补上可能出现的字段名、主题词和同义表达。"
            "\n如果是题目、课题、项目名称这类问题，可以自然带上“题目 / 课题名称 / 项目名称 / 开题报告”等可能字段。"
        )
        if research_mode:
            prompt += "\n本次是深度调研场景，可以稍微补充更完整的主题线索，但仍保持简洁。"
        prompt += f"\n\n用户问题：\n{query}"
        return [
            {"role": "system", "content": "你是一个帮助检索系统改写查询的助手。"},
            {"role": "user", "content": prompt},
        ]

    def _build_agent_planner_messages(
        self,
        *,
        query: str,
        memory_notes: list[str],
        research_mode: bool,
        web_browsing: bool,
    ) -> list[dict]:
        prompt = (
            "你在为一个聊天优先的个人知识工作台规划本轮回答路径。"
            "\n请严格输出 JSON，不要输出代码块。"
            '\n{"working_query":"...","summary":"...","should_use_web":false,"complexity":"simple","task_type":"lookup"}'
            "\n规则："
            "\n1. 优先围绕当前问题生成更清晰的工作查询。"
            "\n2. 只有当网页补充开关已开启且你认为本轮需要外部补充时，should_use_web 才能为 true。"
            "\n3. complexity 只能是 simple 或 complex。"
            "\n4. task_type 只能是 lookup / follow_up / summarize / compare / explain。"
            "\n5. summary 用一句话概括本轮计划。"
            f"\n\n当前问题：\n{query}"
        )
        if memory_notes:
            prompt += "\n\n相关上下文：\n" + "\n".join(f"- {note}" for note in memory_notes[:5])
        prompt += f"\n\n模式：{'research' if research_mode else 'chat'}"
        prompt += f"\n网页补充是否可用：{'yes' if web_browsing else 'no'}"
        return [
            {"role": "system", "content": "你是一个负责规划检索与回答路径的中文助手。"},
            {"role": "user", "content": prompt},
        ]

    def _build_pre_answer_check_messages(
        self,
        *,
        query: str,
        evidence_pack: list[dict],
        plan_summary: str,
        research_mode: bool,
        web_browsing_enabled: bool,
        web_used: bool,
        diagnostics: dict,
        project_retry_count: int,
    ) -> list[dict]:
        evidence_lines = []
        for index, item in enumerate(evidence_pack, start=1):
            evidence_lines.append(
                f"[证据 {index}] title={item['source_title']} kind={item.get('source_kind', 'project_source')} excerpt={item['excerpt']}"
            )
        first_pass = diagnostics.get("first_pass", {})
        final = diagnostics.get("final", {})
        prompt = (
            "你要在回答生成前做一次检查。"
            "\n请严格输出 JSON，不要输出代码块。"
            '\n{"action":"proceed","reason":"...","focus":""}'
            "\naction 只能是 proceed / retry_project / need_web / insufficient。"
            "\n当证据已经足够时用 proceed。"
            "\n当项目证据已经命中，但还不够聚焦，且项目内还值得再筛一次时，用 retry_project。"
            "\n当网页补充已开启且当前证据明显不足，且还没用过网页时，用 need_web。"
            "\n当当前条件下无法补足证据时，用 insufficient。"
            f"\n\n当前问题：\n{query}"
            f"\n\n当前计划：\n{plan_summary}"
            f"\n\n模式：{'research' if research_mode else 'chat'}"
            f"\n网页补充开关：{'on' if web_browsing_enabled else 'off'}"
            f"\n本轮是否已使用网页：{'yes' if web_used else 'no'}"
            f"\n项目重筛次数：{project_retry_count}"
            f"\n首轮 top_score：{first_pass.get('top_score', 0.0)}"
            f"\n首轮 term_coverage_ratio：{first_pass.get('term_coverage_ratio', 0.0)}"
            f"\n最终 selected_evidence_count：{final.get('selected_evidence_count', len(evidence_pack))}"
            "\n\n当前证据：\n"
            + ("\n".join(evidence_lines) if evidence_lines else "(none)")
        )
        return [
            {"role": "system", "content": "你是一个回答前检查器。"},
            {"role": "user", "content": prompt},
        ]

    def _heuristic_plan_agent_turn(
        self,
        *,
        query: str,
        memory_notes: list[str],
        research_mode: bool,
        web_browsing: bool,
    ) -> dict:
        working_query = " ".join(query.split()).strip()
        contextual = self._query_looks_contextual(query)
        complex_query = research_mode or self._query_looks_complex(query)
        task_type = "lookup"
        if contextual:
            task_type = "follow_up"
        elif any(keyword in query for keyword in ("总结", "梳理", "概括", "结论", "建议")):
            task_type = "summarize"
        elif any(keyword in query for keyword in ("对比", "区别", "差异", "比较")):
            task_type = "compare"
        elif any(keyword in query for keyword in ("为什么", "原因", "如何", "怎么")):
            task_type = "explain"

        if memory_notes and contextual:
            working_query = f"{working_query} {' '.join(memory_notes[:2])}"

        should_use_web = False
        if web_browsing and (
            research_mode
            or any(keyword in query for keyword in ("联网", "官网", "最新", "外部", "行业", "公开资料", "benchmark", "基准"))
        ):
            should_use_web = True
        return {
            "working_query": " ".join(working_query.split()).strip(),
            "summary": "先检查项目资料，再视情况补充网页来源并整理结论" if web_browsing else "先检查项目资料并整理结论",
            "should_use_web": should_use_web,
            "complexity": "complex" if complex_query else "simple",
            "task_type": task_type,
        }

    def _heuristic_check_agent_answer_readiness(
        self,
        *,
        query: str,
        evidence_pack: list[dict],
        research_mode: bool,
        web_browsing_enabled: bool,
        web_used: bool,
        diagnostics: dict | None,
        project_retry_count: int,
    ) -> dict:
        diagnostics = diagnostics or {}
        first_pass = diagnostics.get("first_pass", {})
        selection = diagnostics.get("selection", {})
        final = diagnostics.get("final", {})
        top_score = float(first_pass.get("top_score", 0.0) or 0.0)
        term_coverage_ratio = float(first_pass.get("term_coverage_ratio", 0.0) or 0.0)
        candidate_count = int(selection.get("input_candidate_count", len(evidence_pack)) or len(evidence_pack))
        selected_count = int(final.get("selected_evidence_count", len(evidence_pack)) or len(evidence_pack))
        project_hits = [item for item in evidence_pack if item.get("source_kind") != "external_web"]
        external_hits = [item for item in evidence_pack if item.get("source_kind") == "external_web"]
        strong_structured_hits = [
            item
            for item in project_hits
            if str(item.get("section_type") or "body") in {"field", "proposition"}
        ]
        external_top_score = max((float(item.get("relevance_score", 0.0)) for item in external_hits), default=0.0)

        if not evidence_pack:
            if web_browsing_enabled and not web_used:
                return {"action": "need_web", "reason": "no_evidence", "focus": query}
            return {"action": "insufficient", "reason": "no_evidence", "focus": query}

        if not project_hits and external_hits:
            if external_top_score >= 2.8 or len(external_hits) >= 2:
                return {"action": "proceed", "reason": "external_evidence_ready", "focus": ""}
            return {"action": "insufficient", "reason": "weak_external_evidence", "focus": query}

        if (
            project_retry_count < 1
            and project_hits
            and (
                (
                    candidate_count > selected_count
                    and (
                        (self._query_looks_complex(query) and len(project_hits) <= 1)
                        or (top_score < 3.0 and term_coverage_ratio < 0.35 and not strong_structured_hits)
                    )
                )
                or (
                    len(project_hits) == 1
                    and not strong_structured_hits
                    and self._query_looks_factoid(query)
                    and top_score < 3.2
                )
                or (top_score < 3.0 and term_coverage_ratio < 0.35 and not strong_structured_hits)
            )
        ):
            return {
                "action": "retry_project",
                "reason": "project_evidence_not_focused",
                "focus": self._build_retry_focus(query=query, evidence_pack=project_hits),
            }

        if research_mode and len(evidence_pack) < 2 and web_browsing_enabled and not web_used:
            return {"action": "need_web", "reason": "thin_research_evidence", "focus": query}
        if top_score < 2.2 and not strong_structured_hits:
            if web_browsing_enabled and not web_used:
                return {"action": "need_web", "reason": "weak_project_evidence", "focus": query}
            return {"action": "insufficient", "reason": "weak_project_evidence", "focus": query}
        return {"action": "proceed", "reason": "evidence_ready", "focus": ""}

    def _build_retry_focus(self, *, query: str, evidence_pack: list[dict]) -> str:
        metadata_terms: list[str] = []
        for item in evidence_pack[:3]:
            for value in (item.get("field_label"), item.get("heading_path"), item.get("proposition_type")):
                text = " ".join(str(value or "").split()).strip()
                if text and text not in metadata_terms:
                    metadata_terms.append(text)
        if not metadata_terms:
            return " ".join(query.split()).strip()
        return " ".join([query, *metadata_terms[:2]]).strip()

    def _query_looks_complex(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        if len(normalized) >= 40:
            return True
        return any(
            keyword in normalized
            for keyword in ("总结", "梳理", "比较", "区别", "差异", "建议", "结论", "原因", "为什么", "如何", "方案", "评估")
        )

    def _query_looks_factoid(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        return any(
            keyword in normalized
            for keyword in ("什么", "哪个", "哪种", "多少", "默认", "名称", "题目", "标题", "谁", "何时", "哪里")
        )

    def _conversation_to_messages(self, conversation: list[dict]) -> list[dict]:
        messages: list[dict] = []
        for item in conversation:
            role = None
            if item["message_type"] == "user_prompt":
                role = "user"
            elif item["message_type"] == "assistant_answer":
                role = "assistant"
            if role is None:
                continue
            content = (item.get("content_md") or "").strip()
            if not content:
                continue
            messages.append({"role": role, "content": content})
        return messages

    def _complete_messages(self, *, messages: list[dict], temperature: float) -> str:
        settings = get_settings()
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

        try:
            response = httpx.post(
                url,
                headers=self._headers(settings.llm_api_key),
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": temperature,
                },
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_detail(exc.response)
            raise RuntimeError(f"LLM request failed with status {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"LLM returned an unexpected payload shape: {payload}") from exc
        return self._coerce_content_to_text(content)

    def _stream_completion(self, *, messages: list[dict], temperature: float) -> Iterator[str]:
        settings = get_settings()
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

        try:
            with httpx.stream(
                "POST",
                url,
                headers=self._headers(settings.llm_api_key),
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                },
                timeout=settings.llm_timeout_seconds,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = line[6:] if line.startswith("data: ") else line
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    chunk = self._extract_stream_chunk(payload)
                    if chunk:
                        yield chunk
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_detail(exc.response)
            raise RuntimeError(f"LLM request failed with status {exc.response.status_code}: {detail}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _coerce_content_to_text(self, content) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "").strip()
                for part in content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            ).strip()
        return ""

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:400].strip() or "No error body returned."

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            message = payload.get("message")
            if message:
                return str(message)
        return str(payload)[:400]

    def _sanitize_output(self, text: str) -> str:
        cleaned = text
        lowered = cleaned.lower()
        open_tag = "<think>"
        close_tag = "</think>"

        while True:
            start = lowered.find(open_tag)
            if start == -1:
                break
            end = lowered.find(close_tag, start)
            if end == -1:
                cleaned = cleaned[:start]
                break
            cleaned = cleaned[:start] + cleaned[end + len(close_tag) :]
            lowered = cleaned.lower()

        return cleaned.strip()

    def _normalize_grounded_markdown(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").strip()
        if not normalized:
            return normalized

        numbered_markers = re.findall(r"(?<!\S)\d+\.\s+", normalized)
        if len(numbered_markers) >= 2 and "\n" not in normalized:
            normalized = re.sub(r"\s+(?=\d+\.\s+)", "\n", normalized)

        return normalized.strip()

    def _strip_code_fence(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return stripped

    def _extract_stream_chunk(self, payload: dict) -> str:
        try:
            delta = payload["choices"][0].get("delta", {})
        except (KeyError, IndexError, TypeError):
            return ""

        content = delta.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            )
        return ""

    def _query_looks_contextual(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        if len(normalized) <= 14:
            return True
        return any(term in normalized for term in ("现在", "这个", "那个", "它", "知道了吗", "了吧"))

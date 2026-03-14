from __future__ import annotations

from datetime import UTC, datetime
import re

from app.repositories.memory_repository import MemoryRepository
from app.repositories.search_repository import SearchRepository


class MemoryService:
    def __init__(self) -> None:
        self.repository = MemoryRepository()
        self.search_repository = SearchRepository()

    def lookup(self, *, project_id: str, session_id: str, query: str, limit: int = 6) -> dict:
        session_hits = self._score_entries(
            entries=[item.to_summary() for item in self.repository.list_scope_entries(scope_type="session", scope_id=session_id)],
            query=query,
            limit=max(2, limit // 2),
            scope_type="session",
        )
        project_hits = self._score_entries(
            entries=[item.to_summary() for item in self.repository.list_scope_entries(scope_type="project", scope_id=project_id)],
            query=query,
            limit=limit,
            scope_type="project",
        )
        merged = self._merge_memory_hits(session_hits=session_hits, project_hits=project_hits, limit=limit)
        self.repository.touch_entries([item["id"] for item in merged])
        return {
            "session": session_hits,
            "project": project_hits,
            "notes": [item["fact_text"] for item in merged],
        }

    def persist_from_answer(
        self,
        *,
        project_id: str,
        session_id: str,
        query: str,
        answer_md: str,
        evidences: list[dict],
        source_message_id: str,
    ) -> None:
        candidates = self._extract_memory_candidates(query=query, answer_md=answer_md, evidences=evidences)
        for candidate in candidates["session"]:
            self.repository.upsert_entry(
                scope_type="session",
                scope_id=session_id,
                topic=candidate["topic"],
                fact_text=candidate["fact_text"],
                salience=candidate["salience"],
                source_message_id=source_message_id,
            )
        for candidate in candidates["project"]:
            self.repository.upsert_entry(
                scope_type="project",
                scope_id=project_id,
                topic=candidate["topic"],
                fact_text=candidate["fact_text"],
                salience=candidate["salience"],
                source_message_id=source_message_id,
            )

    def _score_entries(self, *, entries: list[dict], query: str, limit: int, scope_type: str) -> list[dict]:
        if not entries:
            return []
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        contextual = self._query_looks_contextual(query)
        ranked: list[dict] = []
        normalized_query = " ".join(query.split()).lower()
        for entry in entries:
            haystack = f"{entry['topic']} {entry['fact_text']}".lower()
            score = float(entry["salience"])
            if scope_type == "session":
                score += 0.5 if contextual else 0.2
            score += 0.9 * sum(1 for term in terms if term in haystack)
            if normalized_query and normalized_query in haystack:
                score += 1.2
            score += self._recency_bonus(entry)
            if score <= 0:
                continue
            ranked.append({**entry, "memory_score": round(score, 3)})
        ranked.sort(key=lambda item: (item["memory_score"], item["updated_at"]), reverse=True)
        return ranked[:limit]

    def _merge_memory_hits(self, *, session_hits: list[dict], project_hits: list[dict], limit: int) -> list[dict]:
        merged: list[dict] = []
        seen_facts: set[str] = set()
        for item in [*session_hits, *project_hits]:
            normalized_fact = self._normalize_fact(item["fact_text"])
            if normalized_fact in seen_facts:
                continue
            seen_facts.add(normalized_fact)
            merged.append(item)
            if len(merged) >= limit:
                break
        return merged

    def _extract_memory_candidates(self, *, query: str, answer_md: str, evidences: list[dict]) -> dict:
        session_candidates: list[dict] = []
        project_candidates: list[dict] = []
        seen_project: set[tuple[str, str]] = set()
        seen_session: set[tuple[str, str]] = set()

        clean_answer = self._normalize_fact(self._trim_text(self._first_sentence(answer_md), 220))
        if self._is_stable_fact(clean_answer):
            session_candidates.append(
                {
                    "topic": self._derive_topic(query=query, fallback="recent_answer"),
                    "fact_text": clean_answer,
                    "salience": 1.0,
                }
            )

        goal_candidate = self._build_goal_candidate(query)
        if goal_candidate:
            session_candidates.append(goal_candidate)

        for evidence in evidences[:5]:
            fact_text = self._normalize_fact(
                self._trim_text(str(evidence.get("source_excerpt") or evidence.get("excerpt") or ""), 220)
            )
            if not self._is_stable_fact(fact_text):
                continue
            topic = self._normalize_topic(
                str(
                    evidence.get("field_label")
                    or evidence.get("heading_path")
                    or evidence.get("proposition_type")
                    or self._derive_topic(query=query, fallback="project_fact")
                )
            )
            if not topic:
                continue

            if evidence.get("source_kind") != "external_web":
                project_key = (topic, fact_text)
                if project_key not in seen_project:
                    seen_project.add(project_key)
                    project_candidates.append(
                        {
                            "topic": topic,
                            "fact_text": fact_text,
                            "salience": 1.2 if evidence.get("field_label") else 1.0,
                        }
                    )

            if evidence.get("proposition_type") or evidence.get("field_label") or evidence.get("source_kind") == "external_web":
                session_key = (topic, fact_text)
                if session_key not in seen_session:
                    seen_session.add(session_key)
                    session_candidates.append(
                        {
                            "topic": topic,
                            "fact_text": fact_text,
                            "salience": 1.05 if evidence.get("source_kind") == "external_web" else 1.1,
                        }
                    )

        return {
            "session": session_candidates[:5],
            "project": project_candidates[:6],
        }

    def _derive_topic(self, *, query: str, fallback: str) -> str:
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        if terms:
            return self._normalize_topic(" / ".join(terms[:3]))
        return fallback

    def _build_goal_candidate(self, query: str) -> dict | None:
        normalized_query = self._normalize_fact(query)
        if not normalized_query or not self._is_stable_query_goal(normalized_query):
            return None
        return {
            "topic": "current_goal",
            "fact_text": f"当前会话目标：{normalized_query}",
            "salience": 0.95,
        }

    def _recency_bonus(self, entry: dict) -> float:
        reference = entry.get("last_used_at") or entry.get("updated_at") or entry.get("created_at")
        if not reference:
            return 0.0
        try:
            timestamp = datetime.fromisoformat(str(reference).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        age_hours = max((datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds() / 3600, 0.0)
        if age_hours <= 6:
            return 0.35
        if age_hours <= 48:
            return 0.15
        if age_hours <= 168:
            return 0.0
        return -0.15

    def _is_stable_query_goal(self, text: str) -> bool:
        return not self._query_looks_contextual(text) and len(text) >= 8 and "？" not in text and "?" not in text

    def _is_stable_fact(self, text: str) -> bool:
        if len(text) < 12:
            return False
        lowered = text.lower()
        if any(marker in lowered for marker in ("可能", "也许", "不确定", "猜测", "unknown", "maybe")):
            return False
        if "?" in text or "？" in text:
            return False
        if text.startswith("当前会话目标：") and len(text) < 16:
            return False
        return True

    def _query_looks_contextual(self, query: str) -> bool:
        normalized = " ".join(query.split()).lower()
        return any(
            token in normalized
            for token in ("这个", "那个", "它", "他", "她", "这些", "那些", "刚才", "现在", "继续", "上面", "前面")
        )

    def _first_sentence(self, text: str) -> str:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return ""
        parts = re.split(r"(?<=[。！？；;.!?])\s+|(?<=[。！？；;.!?])", cleaned)
        for part in parts:
            sentence = part.strip()
            if len(sentence) >= 12:
                return sentence
        return cleaned

    def _normalize_topic(self, text: str) -> str:
        normalized = " ".join(text.split()).strip()
        normalized = re.sub(r"[：:]+$", "", normalized)
        return normalized[:80]

    def _normalize_fact(self, text: str) -> str:
        normalized = " ".join(text.split()).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _trim_text(self, text: str, limit: int) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

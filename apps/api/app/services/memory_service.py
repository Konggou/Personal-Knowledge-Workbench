from __future__ import annotations

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
        )
        project_hits = self._score_entries(
            entries=[item.to_summary() for item in self.repository.list_scope_entries(scope_type="project", scope_id=project_id)],
            query=query,
            limit=limit,
        )
        self.repository.touch_entries([item["id"] for item in [*session_hits, *project_hits]])
        return {
            "session": session_hits,
            "project": project_hits,
            "notes": [item["fact_text"] for item in [*session_hits, *project_hits][:limit]],
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

    def _score_entries(self, *, entries: list[dict], query: str, limit: int) -> list[dict]:
        if not entries:
            return []
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        ranked: list[dict] = []
        normalized_query = " ".join(query.split()).lower()
        for entry in entries:
            haystack = f"{entry['topic']} {entry['fact_text']}".lower()
            score = float(entry["salience"])
            score += 0.9 * sum(1 for term in terms if term in haystack)
            if normalized_query and normalized_query in haystack:
                score += 1.5
            if score <= 0:
                continue
            ranked.append({**entry, "memory_score": round(score, 3)})
        ranked.sort(key=lambda item: (item["memory_score"], item["updated_at"]), reverse=True)
        return ranked[:limit]

    def _extract_memory_candidates(self, *, query: str, answer_md: str, evidences: list[dict]) -> dict:
        session_candidates: list[dict] = []
        project_candidates: list[dict] = []
        seen_project: set[tuple[str, str]] = set()
        seen_session: set[tuple[str, str]] = set()

        clean_answer = self._trim_text(self._first_sentence(answer_md), 220)
        if clean_answer:
            session_candidates.append(
                {
                    "topic": self._derive_topic(query=query, fallback="recent_answer"),
                    "fact_text": clean_answer,
                    "salience": 1.0,
                }
            )

        for evidence in evidences[:4]:
            fact_text = self._trim_text(str(evidence.get("source_excerpt") or evidence.get("excerpt") or ""), 220)
            if len(fact_text) < 18:
                continue
            topic = evidence.get("field_label") or evidence.get("heading_path") or evidence.get("proposition_type") or "project_fact"
            topic = self._trim_text(str(topic), 80)
            if not topic:
                continue

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

            if evidence.get("proposition_type") or evidence.get("field_label"):
                session_key = (topic, fact_text)
                if session_key not in seen_session:
                    seen_session.add(session_key)
                    session_candidates.append(
                        {
                            "topic": topic,
                            "fact_text": fact_text,
                            "salience": 1.1,
                        }
                    )

        return {
            "session": session_candidates[:4],
            "project": project_candidates[:6],
        }

    def _derive_topic(self, *, query: str, fallback: str) -> str:
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        if terms:
            return " / ".join(terms[:3])
        return fallback

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

    def _trim_text(self, text: str, limit: int) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

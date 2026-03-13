from app.services.search_service import SearchService
from app.services.source_service import SourceService


class KnowledgeService:
    def __init__(self) -> None:
        self.sources = SourceService()
        self.search = SearchService()

    def list_knowledge(
        self,
        *,
        query: str | None = None,
        project_id: str | None = None,
        include_archived: bool = False,
    ) -> dict:
        normalized_query = (query or "").strip()
        if normalized_query:
            return self._search_knowledge(
                query=normalized_query,
                project_id=project_id,
                include_archived=include_archived,
            )

        items = self.sources.list_all_sources(project_id=project_id, include_archived=include_archived)
        return {
            "query": normalized_query,
            "groups": self._group_sources(items),
        }

    def _search_knowledge(self, *, query: str, project_id: str | None, include_archived: bool) -> dict:
        scope = "project" if project_id else "global"
        hits = self.search.search(scope=scope, query=query, project_id=project_id, limit=24)["results"]
        source_map: dict[str, dict] = {}

        for hit in hits:
            key = hit["source_id"]
            existing = source_map.get(key)
            if existing is None:
                source_map[key] = {
                    "id": hit["source_id"],
                    "project_id": hit["project_id"],
                    "project_name": hit["project_name"],
                    "source_type": hit["source_type"],
                    "title": hit["source_title"],
                    "canonical_uri": hit["canonical_uri"],
                    "ingestion_status": "ready",
                    "quality_level": "normal",
                    "refresh_strategy": "manual" if hit["source_type"] == "web_page" else "none",
                    "created_at": "",
                    "updated_at": "",
                    "last_refreshed_at": None,
                    "error_code": None,
                    "error_message": None,
                    "archived_at": None,
                    "deleted_at": None,
                    "original_filename": None,
                    "mime_type": None,
                    "favicon_url": hit.get("favicon_url"),
                    "match_excerpt": hit["excerpt"],
                }

        if not source_map:
            return {
                "query": query,
                "groups": [],
            }

        all_sources = self.sources.list_all_sources(project_id=project_id, include_archived=include_archived)
        hydrated: list[dict] = []
        for source in all_sources:
            if source["id"] not in source_map:
                continue
            merged = {**source, "match_excerpt": source_map[source["id"]]["match_excerpt"]}
            hydrated.append(merged)

        return {
            "query": query,
            "groups": self._group_sources(hydrated),
        }

    def _group_sources(self, items: list[dict]) -> list[dict]:
        groups: dict[str, dict] = {}
        for item in items:
            group = groups.setdefault(
                item["project_id"],
                {
                    "project_id": item["project_id"],
                    "project_name": item["project_name"],
                    "items": [],
                },
            )
            group["items"].append(item)

        return list(groups.values())

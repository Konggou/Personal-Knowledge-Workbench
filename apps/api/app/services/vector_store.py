from qdrant_client import QdrantClient, models

import app.core.settings as settings_module

from app.services.embedding_service import EmbeddingService


class VectorStore:
    _clients: dict[tuple[str, str, str], QdrantClient] = {}
    _backend_modes: dict[tuple[str, str, str], str] = {}

    def __init__(self) -> None:
        self.embedder = EmbeddingService()

    @property
    def settings(self):
        return settings_module.get_settings()

    def ensure_collection(self) -> None:
        client = self._get_client(ensure_collection=False)
        if client.collection_exists(self.settings.qdrant_collection):
            return

        client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=self.embedder.dimension,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert_source_chunks(self, chunks: list[dict]) -> bool:
        if not chunks:
            return True

        try:
            client = self._get_client()
            self.delete_source_points(chunks[0]["source_id"])
            vectors = self.embedder.embed_documents([chunk["normalized_text"] for chunk in chunks])
            points = [
                models.PointStruct(
                    id=chunk["qdrant_point_id"],
                    vector=vector,
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "source_id": chunk["source_id"],
                        "project_id": chunk["project_id"],
                        "project_name": chunk["project_name"],
                        "snapshot_id": chunk["snapshot_id"],
                        "source_title": chunk["source_title"],
                        "source_type": chunk["source_type"],
                        "canonical_uri": chunk["canonical_uri"],
                        "section_label": chunk["section_label"],
                        "chunk_index": chunk["chunk_index"],
                        "excerpt": chunk["excerpt"],
                        "normalized_text": chunk["normalized_text"],
                        "quality_level": chunk["quality_level"],
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            client.upsert(collection_name=self.settings.qdrant_collection, points=points)
            return True
        except Exception:
            return False

    def delete_source_points(self, source_id: str) -> bool:
        try:
            client = self._get_client()
            client.delete(
                collection_name=self.settings.qdrant_collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_id",
                                match=models.MatchValue(value=source_id),
                            )
                        ]
                    )
                ),
            )
            return True
        except Exception:
            return False

    def search(self, *, query: str, project_id: str | None, limit: int) -> list[dict]:
        try:
            client = self._get_client()
            query_filter = None
            if project_id is not None:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="project_id",
                            match=models.MatchValue(value=project_id),
                        )
                    ]
                )

            result = client.query_points(
                collection_name=self.settings.qdrant_collection,
                query=self.embedder.embed_query(query),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

            hits: list[dict] = []
            for point in result.points:
                payload = point.payload or {}
                hits.append(
                    {
                        "project_id": payload["project_id"],
                        "project_name": payload.get("project_name"),
                        "chunk_id": payload["chunk_id"],
                        "source_id": payload["source_id"],
                        "source_title": payload["source_title"],
                        "source_type": payload["source_type"],
                        "canonical_uri": payload["canonical_uri"],
                        "location_label": f"{payload['section_label']} #{int(payload['chunk_index']) + 1}",
                        "excerpt": payload["excerpt"],
                        "normalized_text": payload["normalized_text"],
                        "relevance_score": round(float(point.score), 3),
                        "quality_level": payload["quality_level"],
                        "snapshot_id": payload["snapshot_id"],
                    }
                )
            return hits
        except Exception:
            return []

    def _get_client(self, *, ensure_collection: bool = True) -> QdrantClient:
        current_key = (
            self.settings.qdrant_url,
            self.settings.qdrant_collection,
            str(self.settings.data_dir),
        )
        existing = VectorStore._clients.get(current_key)
        if existing is not None:
            return existing

        client, backend_mode = self._build_client()
        VectorStore._clients[current_key] = client
        VectorStore._backend_modes[current_key] = backend_mode

        if ensure_collection:
            self.ensure_collection()
        return client

    def describe_backend(self) -> dict:
        current_key = (
            self.settings.qdrant_url,
            self.settings.qdrant_collection,
            str(self.settings.data_dir),
        )
        mode = VectorStore._backend_modes.get(current_key)
        if mode is None:
            try:
                self._get_client()
                mode = VectorStore._backend_modes.get(current_key, "unknown")
            except Exception:
                mode = "unavailable"

        return {
            "configured_qdrant_url": self.settings.qdrant_url,
            "collection": self.settings.qdrant_collection,
            "backend_mode": mode,
            "local_path": str(self.settings.qdrant_local_path),
        }

    def _build_client(self) -> tuple[QdrantClient, str]:
        if self.settings.qdrant_url == ":memory:":
            return QdrantClient(location=":memory:"), "memory"

        if self.settings.qdrant_url == "embedded":
            self.settings.qdrant_local_path.mkdir(parents=True, exist_ok=True)
            return QdrantClient(path=str(self.settings.qdrant_local_path)), "embedded"

        try:
            client = QdrantClient(url=self.settings.qdrant_url, timeout=5.0)
            client.collection_exists(self.settings.qdrant_collection)
            return client, "remote"
        except Exception:
            if not self.settings.qdrant_allow_embedded_fallback:
                raise

            self.settings.qdrant_local_path.mkdir(parents=True, exist_ok=True)
            return QdrantClient(path=str(self.settings.qdrant_local_path)), "embedded_fallback"

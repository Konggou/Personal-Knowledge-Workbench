import re
import sqlite3

from app.core.database import get_connection
from app.core.settings import get_settings


class SearchRepository:
    _ascii_term_pattern = re.compile(r"[A-Za-z0-9]{2,}")
    _cjk_term_pattern = re.compile(r"[\u4e00-\u9fff]{2,}")
    _term_aliases = {
        "题目": ("课题", "课题名称", "项目", "项目名称", "标题"),
        "标题": ("题目", "课题", "课题名称", "项目名称"),
        "项目": ("课题", "课题名称", "项目名称"),
        "项目名称": ("课题名称", "题目"),
        "开题报告": ("课题", "课题名称", "题目"),
    }

    @property
    def settings(self):
        return get_settings()

    def get_project_current_snapshot_id(self, project_id: str) -> str | None:
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT current_snapshot_id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            return row["current_snapshot_id"]
        finally:
            connection.close()

    def ensure_retrieval_index(self) -> None:
        connection = get_connection()
        try:
            version_row = connection.execute(
                "SELECT value FROM _app_metadata WHERE key = 'retrieval_fts_version'",
            ).fetchone()
            current_version = str(version_row["value"]) if version_row is not None else None
            if current_version != self.settings.retrieval_fts_version or not self._fts_counts_match(connection):
                self._rebuild_fts_index(connection)
                connection.execute(
                    """
                    INSERT INTO _app_metadata (key, value)
                    VALUES ('retrieval_fts_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (self.settings.retrieval_fts_version,),
                )
                connection.commit()
        finally:
            connection.close()

    def get_latest_chunks_for_project(self, project_id: str) -> list[dict]:
        return self.get_latest_chunks(scope="project", project_id=project_id)

    def get_latest_chunks(self, *, scope: str, project_id: str | None = None) -> list[dict]:
        connection = get_connection()
        try:
            query = """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  JOIN sources s ON s.id = sc.source_id
                  WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                    AND s.deleted_at IS NULL
            """
            params: list[object] = []
            if scope == "project":
                query += " AND s.project_id = ?"
                params.append(project_id)
            query += """
                  GROUP BY sc.source_id
                )
                SELECT
                  s.project_id,
                  p.name AS project_name,
                  sc.id AS chunk_id,
                  sc.source_id,
                  sc.section_label,
                  sc.section_type,
                  sc.heading_path,
                  sc.field_label,
                  sc.table_origin,
                  sc.proposition_type,
                  sc.chunk_index,
                  sc.normalized_text,
                  sc.excerpt,
                  s.title AS source_title,
                  s.source_type,
                  s.canonical_uri,
                  s.quality_level
                FROM source_chunks sc
                JOIN sources s ON s.id = sc.source_id
                JOIN projects p ON p.id = s.project_id
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot lss
                  ON lss.source_id = sc.source_id
                 AND lss.latest_snapshot_number = ps.snapshot_number
                WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                  AND s.deleted_at IS NULL
                  AND sc.retrieval_enabled = 1
            """
            if scope == "project":
                query += " AND s.project_id = ?"
                params.append(project_id)
            query += " ORDER BY s.updated_at DESC, sc.chunk_index ASC"
            rows = connection.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def search_lexical_chunks(self, *, scope: str, query: str, project_id: str | None = None, limit: int = 10) -> list[dict]:
        self.ensure_retrieval_index()
        expression = self.build_fts_query(query)
        if not expression:
            return []

        connection = get_connection()
        try:
            sql = """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  JOIN sources s ON s.id = sc.source_id
                  WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                    AND s.deleted_at IS NULL
            """
            params: list[object] = []
            if scope == "project":
                sql += " AND s.project_id = ?"
                params.append(project_id)
            sql += """
                  GROUP BY sc.source_id
                )
                SELECT
                  s.project_id,
                  p.name AS project_name,
                  sc.id AS chunk_id,
                  sc.source_id,
                  sc.section_label,
                  sc.section_type,
                  sc.heading_path,
                  sc.field_label,
                  sc.table_origin,
                  sc.proposition_type,
                  sc.chunk_index,
                  sc.normalized_text,
                  sc.excerpt,
                  s.title AS source_title,
                  s.source_type,
                  s.canonical_uri,
                  s.quality_level,
                  bm25(source_chunk_fts, 2.2, 1.0) AS bm25_score
                FROM source_chunk_fts
                JOIN source_chunks sc ON sc.id = source_chunk_fts.chunk_id
                JOIN sources s ON s.id = sc.source_id
                JOIN projects p ON p.id = s.project_id
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot lss
                  ON lss.source_id = sc.source_id
                 AND lss.latest_snapshot_number = ps.snapshot_number
                WHERE source_chunk_fts MATCH ?
                  AND s.ingestion_status IN ('ready', 'ready_low_quality')
                  AND s.deleted_at IS NULL
                  AND sc.retrieval_enabled = 1
            """
            params.append(expression)
            if scope == "project":
                sql += " AND s.project_id = ?"
                params.append(project_id)
            sql += """
                ORDER BY bm25_score ASC, s.updated_at DESC, sc.chunk_index ASC
                LIMIT ?
            """
            params.append(limit)
            rows = connection.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error:
            return []
        finally:
            connection.close()

        results: list[dict] = []
        for rank, row in enumerate(rows, start=1):
            item = dict(row)
            bm25_score = float(item.pop("bm25_score"))
            results.append(
                {
                    **item,
                    "bm25_score": round(bm25_score, 6),
                    "relevance_score": round(max(-bm25_score, 0.0), 6),
                    "lexical_rank": rank,
                }
            )
        return results

    def build_query_terms(self, query: str) -> list[str]:
        normalized = query.lower().strip()
        if not normalized:
            return []

        terms: list[str] = []
        seen: set[str] = set()

        for token in self._ascii_term_pattern.findall(normalized):
            if token in seen:
                continue
            seen.add(token)
            terms.append(token)

        for token in self._cjk_term_pattern.findall(normalized):
            self._append_term(terms, seen, token)
            self._append_aliases(terms, seen, token)

            if len(token) > 4:
                upper = min(len(token), 6)
                for size in range(2, upper + 1):
                    for index in range(0, len(token) - size + 1):
                        ngram = token[index : index + size]
                        self._append_term(terms, seen, ngram)
                        self._append_aliases(terms, seen, ngram)

        return terms

    def build_fts_query(self, query: str) -> str:
        normalized = " ".join(query.split()).strip().lower()
        if not normalized:
            return ""

        candidates: list[str] = []
        seen: set[str] = set()

        def append_term(term: str) -> None:
            cleaned = term.strip()
            if len(cleaned) < 2 or cleaned in seen:
                return
            seen.add(cleaned)
            escaped = cleaned.replace('"', '""')
            candidates.append(f'"{escaped}"')

        append_term(normalized)
        for term in self.build_query_terms(query)[:14]:
            append_term(term)

        return " OR ".join(candidates[:14])

    def _append_term(self, terms: list[str], seen: set[str], token: str) -> None:
        if token in seen:
            return
        seen.add(token)
        terms.append(token)

    def _append_aliases(self, terms: list[str], seen: set[str], token: str) -> None:
        for alias in self._term_aliases.get(token, ()):
            self._append_term(terms, seen, alias)

    def _fts_counts_match(self, connection) -> bool:
        try:
            chunk_row = connection.execute(
                """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  JOIN sources s ON s.id = sc.source_id
                  WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                    AND s.deleted_at IS NULL
                  GROUP BY sc.source_id
                )
                SELECT COUNT(*) AS total
                FROM source_chunks sc
                JOIN sources s ON s.id = sc.source_id
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot lss
                  ON lss.source_id = sc.source_id
                 AND lss.latest_snapshot_number = ps.snapshot_number
                WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                  AND s.deleted_at IS NULL
                  AND sc.retrieval_enabled = 1
                """,
            ).fetchone()
            fts_row = connection.execute(
                """
                WITH latest_source_snapshot AS (
                  SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
                  FROM source_chunks sc
                  JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                  JOIN sources s ON s.id = sc.source_id
                  WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                    AND s.deleted_at IS NULL
                  GROUP BY sc.source_id
                )
                SELECT COUNT(*) AS total
                FROM source_chunk_fts fts
                JOIN source_chunks sc ON sc.id = fts.chunk_id
                JOIN sources s ON s.id = sc.source_id
                JOIN project_snapshots ps ON ps.id = sc.snapshot_id
                JOIN latest_source_snapshot lss
                  ON lss.source_id = sc.source_id
                 AND lss.latest_snapshot_number = ps.snapshot_number
                WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                  AND s.deleted_at IS NULL
                  AND sc.retrieval_enabled = 1
                """,
            ).fetchone()
            return int(chunk_row["total"]) == int(fts_row["total"])
        except sqlite3.Error:
            return False

    def _rebuild_fts_index(self, connection) -> None:
        connection.execute("DELETE FROM source_chunk_fts")
        connection.execute(
            """
            WITH latest_source_snapshot AS (
              SELECT sc.source_id, MAX(ps.snapshot_number) AS latest_snapshot_number
              FROM source_chunks sc
              JOIN project_snapshots ps ON ps.id = sc.snapshot_id
              JOIN sources s ON s.id = sc.source_id
              WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
                AND s.deleted_at IS NULL
              GROUP BY sc.source_id
            )
            INSERT INTO source_chunk_fts (chunk_id, project_id, snapshot_id, title, normalized_text)
            SELECT
              sc.id,
              sc.project_id,
              sc.snapshot_id,
              s.title,
              sc.normalized_text
            FROM source_chunks sc
            JOIN sources s ON s.id = sc.source_id
            JOIN project_snapshots ps ON ps.id = sc.snapshot_id
            JOIN latest_source_snapshot lss
              ON lss.source_id = sc.source_id
             AND lss.latest_snapshot_number = ps.snapshot_number
            WHERE s.ingestion_status IN ('ready', 'ready_low_quality')
              AND s.deleted_at IS NULL
              AND sc.retrieval_enabled = 1
            """
        )

import re

from app.core.database import get_connection


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

            # Chinese queries often arrive as whole sentences without spaces.
            # Add short overlapping n-grams so lexical matching can still hit
            # titles like “开题报告” or field labels like “项目名称”.
            if len(token) > 4:
                upper = min(len(token), 6)
                for size in range(2, upper + 1):
                    for index in range(0, len(token) - size + 1):
                        ngram = token[index : index + size]
                        self._append_term(terms, seen, ngram)
                        self._append_aliases(terms, seen, ngram)

        return terms

    def _append_term(self, terms: list[str], seen: set[str], token: str) -> None:
        if token in seen:
            return
        seen.add(token)
        terms.append(token)

    def _append_aliases(self, terms: list[str], seen: set[str], token: str) -> None:
        for alias in self._term_aliases.get(token, ()):
            self._append_term(terms, seen, alias)

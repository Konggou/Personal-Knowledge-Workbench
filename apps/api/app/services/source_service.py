from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

import httpx
from docx import Document
from docx.table import Table, _Cell
from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.repositories.session_repository import SessionRepository
from app.repositories.source_repository import SourceRepository
from app.services.vector_store import VectorStore


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_tag: str | None = None
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_tag = tag
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3"}:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_tag == tag:
            self._skip_tag = None
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_tag:
            return

        text = " ".join(data.split())
        if not text:
            return

        if self._in_title:
            self._title_parts.append(text)
        self._text_parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self._title_parts).strip()

    @property
    def text(self) -> str:
        raw = "\n".join(part for part in self._text_parts if part.strip())
        paragraphs = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in paragraphs if line)


class SourceService:
    def __init__(self) -> None:
        self.repository = SourceRepository()
        self.sessions = SessionRepository()
        self.vector_store = VectorStore()

    def list_sources(self, project_id: str, *, include_archived: bool = False) -> list[dict]:
        if not self.repository.project_exists(project_id):
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return [record.to_summary() for record in self.repository.list_sources(project_id, include_archived=include_archived)]

    def list_all_sources(self, *, project_id: str | None = None, include_archived: bool = False) -> list[dict]:
        return [record.to_summary() for record in self.repository.list_all_sources(project_id=project_id, include_archived=include_archived)]

    def create_web_source(self, project_id: str, url: str, *, session_id: str | None = None) -> dict:
        if not self.repository.project_exists(project_id):
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

        source = self.repository.create_web_source(project_id, url)

        try:
            title, text = self._fetch_web_content(url)
            self._complete_ingestion(source_id=source.id, project_id=project_id, title=title, text=text, reason="source_ingested")
        except Exception as exc:
            self.repository.finalize_source_failure(
                source_id=source.id,
                error_code="ingestion_failed",
                error_message=str(exc),
            )

        refreshed = self.repository.get_source(source.id)
        if refreshed is None:
            raise HTTPException(status_code=500, detail="Source creation failed unexpectedly.")

        if session_id is not None:
            self._append_source_update_message(session_id, refreshed.to_summary(), "已添加网页资料")

        return refreshed.to_summary()

    async def create_file_sources(self, project_id: str, files: list[UploadFile], *, session_id: str | None = None) -> list[dict]:
        if not self.repository.project_exists(project_id):
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

        created_sources: list[dict] = []
        for file in files:
            filename = file.filename or "uploaded-file"
            suffix = Path(filename).suffix.lower()
            if suffix not in {".pdf", ".docx"}:
                raise HTTPException(status_code=422, detail=f"Unsupported file type: {filename}")

            source_type = "file_pdf" if suffix == ".pdf" else "file_docx"
            source = self.repository.create_file_source(
                project_id=project_id,
                source_type=source_type,
                title=filename,
                canonical_uri=f"file://{filename}",
                original_filename=filename,
                mime_type=file.content_type or "application/octet-stream",
            )

            try:
                content = await file.read()
                text = self._extract_pdf_text(content) if source_type == "file_pdf" else self._extract_docx_text(content)
                self._complete_ingestion(
                    source_id=source.id,
                    project_id=project_id,
                    title=filename,
                    text=text,
                    reason="source_ingested",
                )
            except Exception as exc:
                self.repository.finalize_source_failure(
                    source_id=source.id,
                    error_code="ingestion_failed",
                    error_message=str(exc),
                )

            refreshed = self.repository.get_source(source.id)
            if refreshed is not None:
                summary = refreshed.to_summary()
                created_sources.append(summary)
                if session_id is not None:
                    self._append_source_update_message(session_id, summary, "已添加文件资料")

        return created_sources

    def get_source_preview(self, source_id: str) -> dict:
        source = self.repository.get_source(source_id)
        if source is None or source.deleted_at is not None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")

        preview_chunks = self.repository.get_source_preview_chunks(source_id)
        item = source.to_summary()
        item["preview_chunks"] = [chunk.to_summary() for chunk in preview_chunks]
        return item

    def refresh_source(self, source_id: str) -> dict:
        source = self.repository.get_source(source_id)
        if source is None or source.deleted_at is not None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        if source.source_type != "web_page":
            raise HTTPException(status_code=422, detail="Only web sources can be refreshed.")

        self.repository.mark_source_processing(source_id)
        try:
            title, text = self._fetch_web_content(source.canonical_uri)
            self._complete_ingestion(
                source_id=source.id,
                project_id=source.project_id,
                title=title,
                text=text,
                reason="source_refreshed",
            )
        except Exception as exc:
            self.repository.finalize_source_failure(
                source_id=source.id,
                error_code="refresh_failed",
                error_message=str(exc),
            )

        refreshed = self.repository.get_source(source.id)
        if refreshed is None:
            raise HTTPException(status_code=500, detail="Source refresh failed unexpectedly.")
        return refreshed.to_summary()

    def update_web_source(self, source_id: str, url: str) -> dict:
        try:
            updated = self.repository.update_web_source_url(source_id, url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return updated.to_summary()

    def archive_source(self, source_id: str) -> dict:
        source = self.repository.archive_source(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        self.vector_store.delete_source_points(source_id)
        return source.to_summary()

    def restore_source(self, source_id: str) -> dict:
        existing = self.repository.get_source(source_id)
        if existing is None or existing.deleted_at is not None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        if existing.ingestion_status != "archived":
            raise HTTPException(status_code=422, detail="Only archived sources can be restored.")

        source = self.repository.restore_source(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        self._sync_source_vectors(source_id)
        return source.to_summary()

    def delete_source(self, source_id: str) -> dict:
        existing = self.repository.get_source(source_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        source = self.repository.delete_source(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        self.vector_store.delete_source_points(source_id)
        return source.to_summary()

    def _append_source_update_message(self, session_id: str, source: dict, prefix: str) -> None:
        detail = self.sessions.get_session_detail(session_id)
        if detail is None:
            return
        self.sessions.create_message(
            session_id=session_id,
            project_id=detail["project_id"],
            role="system",
            message_type="source_update",
            title=prefix,
            content_md=f"{prefix}：{source['title']}",
        )

    def _complete_ingestion(self, *, source_id: str, project_id: str, title: str, text: str, reason: str) -> None:
        chunks = self._chunk_text(text)
        if not chunks:
            raise ValueError("No usable text could be extracted from the source.")

        quality_level = "normal" if len(chunks) >= 2 or len(text) >= 600 else "low"
        self.repository.complete_source_ingestion(
            source_id=source_id,
            project_id=project_id,
            title=title,
            quality_level=quality_level,
            chunks=chunks,
            reason=reason,
        )
        self._sync_source_vectors(source_id)

    def _extract_pdf_text(self, content: bytes) -> str:
        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            extracted = (page.extract_text() or "").strip()
            if extracted:
                parts.append(extracted)
        text = "\n\n".join(parts).strip()
        if not text:
            raise ValueError("The PDF did not produce readable text.")
        return text

    def _extract_docx_text(self, content: bytes) -> str:
        document = Document(BytesIO(content))
        blocks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        blocks.extend(self._extract_docx_tables(document.tables))
        text = "\n\n".join(block for block in blocks if block).strip()
        if not text:
            raise ValueError("The DOCX did not produce readable text.")
        return text

    def _extract_docx_tables(self, tables: list[Table]) -> list[str]:
        rows: list[str] = []
        for table in tables:
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    cell_text = self._extract_docx_cell_text(cell)
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    rows.append(" | ".join(cells))
        return rows

    def _extract_docx_cell_text(self, cell: _Cell) -> str:
        parts = [paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()]
        nested_rows = self._extract_docx_tables(cell.tables)
        if nested_rows:
            parts.extend(nested_rows)
        return " ".join(part for part in parts if part)

    def _fetch_web_content(self, url: str) -> tuple[str, str]:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        parser = _HTMLTextExtractor()
        parser.feed(response.text)

        title = parser.title or url
        text = parser.text.strip()
        if not text:
            raise ValueError("No readable body content was extracted from the page.")
        return title, text

    def _chunk_text(self, text: str, max_chars: int = 900) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph

        if current:
            chunks.append(current)

        return chunks

    def _sync_source_vectors(self, source_id: str) -> None:
        chunks = self.repository.get_latest_source_chunks_for_indexing(source_id)
        self.vector_store.upsert_source_chunks(chunks)

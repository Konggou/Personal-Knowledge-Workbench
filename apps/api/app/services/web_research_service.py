from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import quote_plus

import httpx

from app.core.settings import get_settings
from app.repositories.search_repository import SearchRepository


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


class WebResearchService:
    _url_pattern = re.compile(r"https?://[^\s)>\]]+")

    def __init__(self) -> None:
        self.search_repository = SearchRepository()

    def search(self, *, query: str, limit: int | None = None) -> list[dict]:
        direct_urls = self._extract_direct_urls(query)
        if direct_urls:
            return [{"title": url, "url": url, "snippet": url, "provider": "direct_url"} for url in direct_urls[: limit or 2]]

        settings = get_settings()
        result_limit = limit or settings.agent_web_result_limit
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        with httpx.Client(timeout=12.0, follow_redirects=True, trust_env=False) as client:
            response = client.get(search_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

        matches = re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            response.text,
            re.S,
        )
        results: list[dict] = []
        for match in matches:
            title = self._strip_html(match.group("title"))
            result_url = httpx.URL(match.group("url")).human_repr()
            snippet = self._strip_html(match.group("snippet"))
            if not title or not result_url:
                continue
            results.append(
                {
                    "title": title,
                    "url": result_url,
                    "snippet": snippet,
                    "provider": "duckduckgo",
                }
            )
            if len(results) >= result_limit:
                break
        return results

    def fetch(self, *, url: str) -> dict:
        with httpx.Client(timeout=15.0, follow_redirects=True, trust_env=False) as client:
            response = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

        parser = _HTMLTextExtractor()
        parser.feed(response.text)
        text = parser.text.strip()
        title = parser.title or url
        if not text:
            raise ValueError("No readable body content was extracted from the external web page.")
        return {
            "title": title,
            "canonical_uri": str(response.url),
            "excerpt": self._trim_excerpt(text),
            "normalized_text": " ".join(text.split()),
        }

    def build_external_evidence(
        self,
        *,
        project_id: str,
        project_name: str,
        query: str,
        limit: int | None = None,
    ) -> list[dict]:
        ranked: list[dict] = []
        settings = get_settings()
        fetch_limit = settings.agent_web_fetch_limit or 2
        for index, candidate in enumerate(self.search(query=query, limit=limit), start=1):
            try:
                fetched = self.fetch(url=candidate["url"])
            except Exception:
                continue
            ranked.append(
                {
                    "project_id": project_id,
                    "project_name": project_name,
                    "chunk_id": None,
                    "source_id": None,
                    "source_kind": "external_web",
                    "source_title": fetched["title"],
                    "source_type": "web_page",
                    "canonical_uri": fetched["canonical_uri"],
                    "external_uri": fetched["canonical_uri"],
                    "location_label": f"网页补充 #{index}",
                    "excerpt": fetched["excerpt"],
                    "normalized_text": fetched["normalized_text"],
                    "relevance_score": self._score_external_hit(
                        query=query,
                        text=fetched["normalized_text"],
                        title=fetched["title"],
                    ),
                    "section_type": "body",
                    "heading_path": None,
                    "field_label": None,
                    "table_origin": None,
                    "proposition_type": None,
                }
            )
            if len(ranked) >= fetch_limit:
                break
        ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return ranked

    def _extract_direct_urls(self, query: str) -> list[str]:
        return list(dict.fromkeys(match.group(0) for match in self._url_pattern.finditer(query)))

    def _score_external_hit(self, *, query: str, text: str, title: str) -> float:
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        haystack = f"{title} {text}".lower()
        score = 1.0
        score += 0.8 * sum(1 for term in terms if term in haystack)
        if query.lower() in haystack:
            score += 1.2
        return round(score, 3)

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").replace("&amp;", "&").strip()

    def _trim_excerpt(self, text: str, limit: int = 360) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

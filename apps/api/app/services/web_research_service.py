from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlencode, urlparse, urlunparse

import httpx

from app.core.settings import get_settings
from app.repositories.search_repository import SearchRepository
from app.repositories.source_repository import SourceRepository


class _HTMLTextExtractor(HTMLParser):
    _skip_tags = {"script", "style", "noscript", "svg", "form"}
    _block_tags = {
        "p",
        "div",
        "section",
        "article",
        "br",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "main",
    }

    def __init__(self) -> None:
        super().__init__()
        self._skip_tag: str | None = None
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._skip_tags:
            self._skip_tag = tag
        elif tag == "title":
            self._in_title = True
        elif tag in self._block_tags:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_tag == tag:
            self._skip_tag = None
        if tag == "title":
            self._in_title = False
        if tag in self._block_tags:
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
    _ddg_result_pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.S,
    )
    _boilerplate_patterns = (
        "cookie",
        "privacy policy",
        "all rights reserved",
        "subscribe",
        "sign up",
        "newsletter",
        "javascript",
        "enable cookies",
    )
    _tracking_query_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "ref",
        "source",
    }

    def __init__(self) -> None:
        self.search_repository = SearchRepository()
        self.source_repository = SourceRepository()

    def search(self, *, query: str, limit: int | None = None) -> list[dict]:
        direct_urls = self._extract_direct_urls(query)
        if direct_urls:
            return [
                {
                    "title": url,
                    "url": self.normalize_url(url),
                    "snippet": url,
                    "provider": "direct_url",
                }
                for url in direct_urls[: limit or 2]
            ]

        settings = get_settings()
        result_limit = max(limit or settings.agent_web_result_limit, 1)
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        with httpx.Client(timeout=12.0, follow_redirects=True, trust_env=False) as client:
            response = client.get(search_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

        ranked: list[dict] = []
        seen_urls: set[str] = set()
        for match in self._ddg_result_pattern.finditer(response.text):
            title = self._strip_html(match.group("title"))
            candidate_url = self._resolve_result_url(match.group("url"))
            snippet = self._strip_html(match.group("snippet"))
            if not title or not candidate_url:
                continue
            normalized_url = self.normalize_url(candidate_url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            if not self._is_supported_external_url(normalized_url):
                continue
            seen_urls.add(normalized_url)
            ranked.append(
                {
                    "title": title,
                    "url": normalized_url,
                    "snippet": snippet,
                    "provider": "duckduckgo",
                    "candidate_score": self._score_search_candidate(
                        query=query,
                        title=title,
                        snippet=snippet,
                        url=normalized_url,
                    ),
                }
            )

        ranked.sort(key=lambda item: item["candidate_score"], reverse=True)
        return ranked[:result_limit]

    def fetch(self, *, url: str) -> dict:
        normalized_input_url = self.normalize_url(url)
        with httpx.Client(timeout=15.0, follow_redirects=True, trust_env=False) as client:
            response = client.get(normalized_input_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

        parser = _HTMLTextExtractor()
        parser.feed(response.text)
        text = self._clean_extracted_text(parser.text)
        if not text:
            # Fall back to shorter paragraphs for minimal fixtures and simple pages.
            text = self._clean_extracted_text(parser.text, allow_short_lines=True)
        title = self._clean_title(parser.title or normalized_input_url)
        canonical_uri = self.normalize_url(str(response.url))
        if not text:
            raise ValueError("No readable body content was extracted from the external web page.")
        return {
            "title": title or canonical_uri,
            "canonical_uri": canonical_uri,
            "text": text,
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
        fetch_limit = max(settings.agent_web_fetch_limit or 2, 1)
        candidate_limit = max((limit or settings.agent_web_result_limit) * 2, fetch_limit)
        known_project_uris = {
            self.normalize_url(item.canonical_uri)
            for item in self.source_repository.list_sources(project_id)
            if item.source_type == "web_page"
        }
        seen_uris: set[str] = set()
        seen_signatures: set[str] = set()
        for candidate in self.search(query=query, limit=candidate_limit):
            if len(ranked) >= fetch_limit:
                break
            try:
                fetched = self.fetch(url=candidate["url"])
            except Exception:
                continue
            canonical_uri = fetched["canonical_uri"]
            if canonical_uri in known_project_uris or canonical_uri in seen_uris:
                continue
            signature = self._build_text_signature(fetched["title"], fetched["normalized_text"])
            if signature in seen_signatures:
                continue
            seen_uris.add(canonical_uri)
            seen_signatures.add(signature)
            ranked.append(
                {
                    "project_id": project_id,
                    "project_name": project_name,
                    "chunk_id": None,
                    "source_id": None,
                    "source_kind": "external_web",
                    "source_title": fetched["title"],
                    "source_type": "web_page",
                    "canonical_uri": canonical_uri,
                    "external_uri": canonical_uri,
                    "location_label": f"网页补充 #{len(ranked) + 1}",
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
        ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return ranked[:fetch_limit]

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            return url.strip()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        kept_query_items = []
        for key, values in parse_qs(parsed.query, keep_blank_values=False).items():
            if key.lower() in self._tracking_query_keys:
                continue
            for value in values:
                kept_query_items.append((key, value))
        normalized_query = urlencode(sorted(kept_query_items))
        return urlunparse((parsed.scheme.lower(), netloc, path, "", normalized_query, ""))

    def _extract_direct_urls(self, query: str) -> list[str]:
        return list(dict.fromkeys(match.group(0) for match in self._url_pattern.finditer(query)))

    def _resolve_result_url(self, url: str) -> str:
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc:
            uddg = parse_qs(parsed.query).get("uddg")
            if uddg:
                return unquote(uddg[0])
        return url

    def _is_supported_external_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc:
            return False
        return not any(blocked in parsed.netloc.lower() for blocked in ("duckduckgo.com", "localhost", "127.0.0.1"))

    def _score_search_candidate(self, *, query: str, title: str, snippet: str, url: str) -> float:
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        url_lower = url.lower()
        score = 1.0
        score += 1.1 * sum(1 for term in terms if term in title_lower)
        score += 0.6 * sum(1 for term in terms if term in snippet_lower)
        score += 0.25 * sum(1 for term in terms if term in url_lower)
        if any(keyword in title_lower for keyword in ("official", "documentation", "docs", "guide")):
            score += 0.3
        return round(score, 3)

    def _score_external_hit(self, *, query: str, text: str, title: str) -> float:
        terms = [term for term in self.search_repository.build_query_terms(query) if len(term) >= 2]
        haystack = f"{title} {text}".lower()
        score = 0.8
        score += 0.9 * sum(1 for term in terms if term in haystack)
        if query.lower() in haystack:
            score += 1.0
        return round(score, 3)

    def _clean_extracted_text(self, text: str, *, allow_short_lines: bool = False) -> str:
        paragraphs = []
        seen_lines: set[str] = set()
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split()).strip()
            if not line:
                continue
            lowered = line.lower()
            if not allow_short_lines and len(line) < 24 and not re.search(r"[\u4e00-\u9fff]{6,}", line):
                continue
            if any(pattern in lowered for pattern in self._boilerplate_patterns):
                continue
            if line in seen_lines:
                continue
            seen_lines.add(line)
            paragraphs.append(line)
        return "\n".join(paragraphs)

    def _clean_title(self, title: str) -> str:
        cleaned = " ".join(title.split()).strip()
        cleaned = re.sub(r"\s*\|\s*.*$", "", cleaned)
        cleaned = re.sub(r"\s*-\s*.*$", "", cleaned)
        return cleaned[:160]

    def _build_text_signature(self, title: str, text: str) -> str:
        lead = " ".join(text.split()[:40])
        return f"{self._clean_title(title).lower()}::{lead.lower()}"

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).replace("&nbsp;", " ").replace("&amp;", "&").strip()

    def _trim_excerpt(self, text: str, limit: int = 360) -> str:
        normalized = " ".join(text.split()).strip()
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."

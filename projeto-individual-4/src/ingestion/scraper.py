"""Descoberta de links de Prévia Operacional nas Centrais de Resultados."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; PipelineUDA/1.0; +https://github.com/unb-gces/projeto-individual-4)"
)
PREVIA_PATTERN = re.compile(r"previa\s+operacional|pr[eé]via\s+operacional", re.IGNORECASE)


@dataclass(frozen=True)
class PdfLink:
    company: str
    url: str
    title: str


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _is_pdf_href(href: str) -> bool:
    lowered = href.lower()
    return lowered.endswith(".pdf") or ".pdf?" in lowered or "/pdf/" in lowered


def _is_previa_operacional(text: str, href: str) -> bool:
    combined = f"{text} {href}".replace("_", " ")
    if PREVIA_PATTERN.search(combined):
        return True
    normalized = _normalize_text(combined)
    return "previa operacional" in normalized


def _clean_title(text: str, href: str) -> str:
    title = text.strip() or href.rsplit("/", 1)[-1]
    return re.sub(r"\s+", " ", title)


class RIScraper:
    def __init__(self, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> RIScraper:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def fetch_results_html(self, results_url: str) -> str:
        response = self._client.get(results_url)
        response.raise_for_status()
        return response.text

    def discover_previa_links(
        self,
        results_url: str,
        company: str,
        html: Optional[str] = None,
    ) -> list[PdfLink]:
        page_html = html if html is not None else self.fetch_results_html(results_url)
        soup = BeautifulSoup(page_html, "lxml")
        discovered: list[PdfLink] = []
        seen_urls: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = urljoin(results_url, anchor["href"].strip())
            if href in seen_urls:
                continue

            title = _clean_title(anchor.get_text(" ", strip=True), href)
            if not _is_previa_operacional(title, href):
                continue
            if not _is_pdf_href(href) and "download" not in href.lower():
                continue

            seen_urls.add(href)
            discovered.append(PdfLink(company=company, url=href, title=title))

        return discovered

    def discover_for_companies(
        self,
        companies: list[tuple[str, str]],
    ) -> list[PdfLink]:
        links: list[PdfLink] = []
        for company, results_url in companies:
            links.extend(self.discover_previa_links(results_url, company))
        return links


def is_same_domain(url: str, base_url: str) -> bool:
    return urlparse(url).netloc == urlparse(base_url).netloc

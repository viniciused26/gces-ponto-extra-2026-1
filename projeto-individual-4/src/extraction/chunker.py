"""
Segmentação híbrida de documentos para extração via LLM.

- Full-Scan: PDFs curtos (<= FULL_SCAN_MAX_PAGES) enviados integralmente.
- Chunking semântico: PDFs longos segmentados por páginas relevantes
  (títulos, palavras-chave operacionais).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.extraction.pdf_reader import PageText

FULL_SCAN_MAX_PAGES = 8

OPERATIONAL_KEYWORDS = (
    "VENDAS",
    "LANÇAMENTOS",
    "LANCAMENTOS",
    "ESTOQUE",
    "DADOS OPERACIONAIS",
    "VGV",
    "REPASSE",
    "PRODUZIDAS",
    "ENTREGUES",
    "GERAÇÃO DE CAIXA",
    "GERACAO DE CAIXA",
    "UNIDADES PRODUZIDAS",
    "VENDAS LÍQUIDAS",
    "VENDAS LIQUIDAS",
    "CONJUNTURA",
    "BALANÇO",
    "BALANCO",
)

METADATA_MAX_PAGE = 2

HEADING_PATTERN = re.compile(
    r"^(\d+[\.)]\s+.+|[A-ZÁÉÍÓÚÃÕÇÂÊÔÜ][A-ZÁÉÍÓÚÃÕÇÂÊÔÜ0-9\s/&\-]{2,})$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    title: str | None = None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper())


def _page_is_relevant(text: str) -> bool:
    normalized = _normalize(text)
    return any(keyword in normalized for keyword in OPERATIONAL_KEYWORDS)


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isupper() and 2 <= len(stripped.split()) <= 10:
            return stripped
        if HEADING_PATTERN.match(stripped):
            return stripped
    return None


def _format_page(page: PageText) -> str:
    return f"[Página {page.page_number}]\n{page.text}"


def chunk_pages(pages: list[PageText]) -> list[TextChunk]:
    if not pages:
        return []

    if len(pages) <= FULL_SCAN_MAX_PAGES:
        combined = "\n\n".join(_format_page(page) for page in pages if page.text)
        return [
            TextChunk(
                chunk_id="full-scan",
                text=combined,
                page_start=pages[0].page_number,
                page_end=pages[-1].page_number,
                title="Documento completo",
            )
        ]

    selected: list[PageText] = []
    seen_pages: set[int] = set()

    for page in pages:
        if page.page_number <= METADATA_MAX_PAGE or _page_is_relevant(page.text):
            if page.page_number not in seen_pages and page.text:
                selected.append(page)
                seen_pages.add(page.page_number)

    if not selected:
        selected = [page for page in pages if page.text]

    return [
        TextChunk(
            chunk_id=f"page-{page.page_number}",
            text=_format_page(page),
            page_start=page.page_number,
            page_end=page.page_number,
            title=_extract_title(page.text),
        )
        for page in selected
    ]


def chunking_strategy(pages: list[PageText]) -> str:
    if len(pages) <= FULL_SCAN_MAX_PAGES:
        return "full-scan"
    return "semantic-chunks"

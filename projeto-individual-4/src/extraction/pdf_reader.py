"""Leitura de texto bruto de PDFs via PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


def read_pdf_pages(path: Path | str) -> list[PageText]:
    """Extrai texto página a página (numeração iniciando em 1)."""
    pdf_path = Path(path)
    pages: list[PageText] = []

    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            pages.append(PageText(page_number=index, text=text))

    return pages


def read_pdf_full_text(path: Path | str) -> str:
    """Concatena o texto de todas as páginas com separadores."""
    pages = read_pdf_pages(path)
    return "\n\n".join(
        f"[Página {page.page_number}]\n{page.text}" for page in pages if page.text
    )

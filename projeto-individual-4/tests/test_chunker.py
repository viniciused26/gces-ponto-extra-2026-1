"""Testes da estratégia de chunking."""

from pathlib import Path

from src.extraction.chunker import FULL_SCAN_MAX_PAGES, chunk_pages, chunking_strategy
from src.extraction.pdf_reader import read_pdf_pages

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOLETIM = FIXTURES / "Boletim_Conjuntura_2025_3T.pdf"
MRV = FIXTURES / "MRV SA - Prévia Operacional - 1T26.pdf"


def test_boletim_uses_full_scan():
    pages = read_pdf_pages(BOLETIM)
    assert chunking_strategy(pages) == "full-scan"
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "full-scan"
    assert "MRV" in chunks[0].text


def test_mrv_uses_semantic_chunks():
    pages = read_pdf_pages(MRV)
    assert len(pages) > FULL_SCAN_MAX_PAGES
    assert chunking_strategy(pages) == "semantic-chunks"
    chunks = chunk_pages(pages)
    assert 1 < len(chunks) <= len(pages)
    assert len(chunks) < len(pages)
    assert all(chunk.page_start == chunk.page_end for chunk in chunks)


def test_mrv_chunks_include_operational_pages():
    pages = read_pdf_pages(MRV)
    chunks = chunk_pages(pages)
    combined = "\n".join(chunk.text.upper() for chunk in chunks)
    assert "LANÇAMENTOS" in combined or "LANCAMENTOS" in combined
    assert "VENDAS" in combined or "OPERACIONAL" in combined

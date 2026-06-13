"""Testes do leitor de PDF."""

from pathlib import Path

from src.extraction.pdf_reader import read_pdf_full_text, read_pdf_pages

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOLETIM = FIXTURES / "Boletim_Conjuntura_2025_3T.pdf"
MRV = FIXTURES / "MRV SA - Prévia Operacional - 1T26.pdf"


def test_read_boletim_has_single_page():
    pages = read_pdf_pages(BOLETIM)
    assert len(pages) == 1
    assert "MRV" in pages[0].text
    assert "LANÇAMENTOS" in pages[0].text.upper() or "LANCAMENTOS" in pages[0].text.upper()


def test_read_mrv_has_multiple_pages():
    pages = read_pdf_pages(MRV)
    assert len(pages) == 13
    assert any("PRÉVIA" in page.text.upper() or "PREVIA" in page.text.upper() for page in pages)


def test_read_pdf_full_text_includes_page_markers():
    text = read_pdf_full_text(BOLETIM)
    assert "[Página 1]" in text
    assert "MRV" in text

"""Testes do scraper de RI."""

from src.ingestion.scraper import RIScraper

SAMPLE_HTML = """
<html><body>
  <a href="/files/previa-operacional-1t26.pdf">Prévia Operacional 1T26</a>
  <a href="/files/release-resultados.pdf">Release de Resultados 1T26</a>
  <a href="/files/PREVIA_OPERACIONAL_4T25.PDF">Download PDF</a>
  <a href="/noticia">Prévia Operacional sem pdf</a>
</body></html>
"""


def test_discover_previa_links_filters_pdf_only():
    scraper = RIScraper()
    links = scraper.discover_previa_links(
        "https://ri.exemplo.com.br/central/",
        "MRV",
        html=SAMPLE_HTML,
    )
    scraper.close()

    urls = {link.url for link in links}
    assert len(links) == 2
    assert "https://ri.exemplo.com.br/files/previa-operacional-1t26.pdf" in urls
    assert "https://ri.exemplo.com.br/files/PREVIA_OPERACIONAL_4T25.PDF" in urls
    assert all(link.company == "MRV" for link in links)


def test_discover_previa_links_is_case_insensitive():
    html = '<a href="/doc.PDF">previa operacional 2T25</a>'
    scraper = RIScraper()
    links = scraper.discover_previa_links("https://ri.test/", "Tenda", html=html)
    scraper.close()
    assert len(links) == 1

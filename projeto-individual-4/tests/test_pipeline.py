"""Testes do pipeline de ingestão."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine

from src.catalog.models import Base
from src.catalog.repository import CatalogRepository
from src.config import CompanyConfig
from src.contracts.conjuntura import ConjunturaExtraction
from src.extraction.chunker import TextChunk
from src.pipeline import IngestionPipeline, ProcessStatus

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOLETIM = FIXTURES / "Boletim_Conjuntura_2025_3T.pdf"


@pytest.fixture
def pipeline(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    repository = CatalogRepository(engine=engine)

    mock_extractor = MagicMock()
    mock_extractor.extract_from_pdf.return_value = (
        ConjunturaExtraction(
            empresa="MRV",
            ano=2025,
            trimestre=3,
            lanc_vs_tri_anterior=-32.0,
        ),
        "full-scan",
        [TextChunk(chunk_id="full-scan", text="...", page_start=1, page_end=1, title="Doc")],
    )

    yield IngestionPipeline(repository=repository, extractor=mock_extractor)
    engine.dispose()


def test_process_local_pdf_persists_to_catalog(pipeline):
    result = pipeline.process_local_pdf(
        BOLETIM,
        empresa="MRV",
        ano_hint=2025,
        trimestre_hint=3,
        persist=True,
    )

    assert result.status == ProcessStatus.PROCESSED
    assert result.snapshot_id is not None
    assert result.record is not None
    assert result.record.lanc_vs_tri_anterior == -32.0
    assert pipeline._repository.document_exists(result.hash_sha256)


def test_process_local_pdf_skips_duplicate_hash(pipeline):
    first = pipeline.process_local_pdf(BOLETIM, empresa="MRV", persist=True)
    second = pipeline.process_local_pdf(BOLETIM, empresa="MRV", persist=True)

    assert first.status == ProcessStatus.PROCESSED
    assert second.status == ProcessStatus.SKIPPED
    assert second.message.startswith("Hash já existente")
    assert pipeline._extractor.extract_from_pdf.call_count == 1


@patch("src.pipeline.RIScraper")
def test_poll_companies_processes_discovered_links(mock_scraper_cls, pipeline):
    from src.ingestion.scraper import PdfLink

    mock_scraper = mock_scraper_cls.return_value.__enter__.return_value
    mock_scraper.discover_previa_links.return_value = [
        PdfLink(
            company="MRV",
            url="https://ri.exemplo.com/previa.pdf",
            title="Prévia Operacional 1T26",
        )
    ]

    with patch.object(pipeline, "process_pdf_link", return_value=MagicMock(status=ProcessStatus.PROCESSED)) as mock_process:
        results = pipeline.poll_companies(
            companies=[CompanyConfig(name="MRV", results_url="https://ri.mrv.com.br/")],
        )

    assert len(results) == 1
    mock_process.assert_called_once()

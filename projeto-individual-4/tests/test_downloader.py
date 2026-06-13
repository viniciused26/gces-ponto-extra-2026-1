"""Testes do downloader de PDF."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.catalog.models import Base
from src.catalog.repository import CatalogRepository
from src.ingestion.downloader import PDFDownloader

SAMPLE_PDF = b"%PDF-1.4 test content for downloader"


@pytest.fixture
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    repository = CatalogRepository(engine=engine)
    yield repository
    engine.dispose()


def test_download_persists_pdf_and_hash(repo, tmp_path):
    dest = tmp_path / "pdfs"
    downloader = PDFDownloader(repo, dest_dir=dest)
    result = downloader.download(
        "https://ri.exemplo.com/previa.pdf",
        "MRV",
        content=SAMPLE_PDF,
    )
    downloader.close()

    assert result.pdf_path.exists()
    assert result.hash_sha256
    assert result.already_processed is False
    assert repo.document_exists(result.hash_sha256) is False


def test_download_skips_when_hash_already_in_catalog(repo, tmp_path):
    dest = tmp_path / "pdfs"
    downloader = PDFDownloader(repo, dest_dir=dest)
    first = downloader.download("https://ri.exemplo.com/previa.pdf", "MRV", content=SAMPLE_PDF)

    from datetime import datetime, timezone

    from src.contracts.conjuntura import ConjunturaRecord

    record = ConjunturaRecord(
        empresa="MRV",
        ano=2026,
        trimestre=1,
        url_origem="https://ri.exemplo.com/previa.pdf",
        hash_documento=first.hash_sha256,
        data_processamento=datetime.now(timezone.utc),
    )
    repo.save_extraction(record, [])

    second = downloader.download("https://ri.exemplo.com/previa.pdf", "MRV", content=SAMPLE_PDF)
    downloader.close()

    assert second.already_processed is True

"""Testes de idempotência do catálogo por hash SHA-256."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.catalog.models import Base
from src.catalog.repository import CatalogRepository, DocumentAlreadyProcessedError, LineageInfo
from src.contracts.conjuntura import ConjunturaRecord
from src.ingestion.hasher import sha256_file

VALID_HASH = "e53f30f5f67ebc739041680133ef33bedc87446cba7bb41ee9fbb0c4f3e65661"
PROCESSING_TIME = datetime(2026, 6, 8, 2, 37, 53, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    repository = CatalogRepository(engine=engine)
    yield repository
    engine.dispose()


def _sample_record(**overrides) -> ConjunturaRecord:
    payload = {
        "empresa": "MRV",
        "ano": 2025,
        "trimestre": 3,
        "lanc_vs_tri_anterior": -32.0,
        "vend_acum_9m_atual": -5.0,
        "url_origem": "local://fixtures/Boletim_Conjuntura_2025_3T.pdf",
        "hash_documento": VALID_HASH,
        "data_processamento": PROCESSING_TIME,
    }
    payload.update(overrides)
    return ConjunturaRecord(**payload)


def test_document_exists_returns_false_for_new_hash(repo):
    assert repo.document_exists(VALID_HASH) is False


def test_save_extraction_persists_record_and_lineage(repo):
    record = _sample_record()
    lineage = [
        LineageInfo(
            pdf_url=record.url_origem,
            pagina_origem=4,
            chunk_id="vendas-mrv",
        )
    ]

    snapshot_id = repo.save_extraction(record, lineage)

    assert snapshot_id > 0
    assert repo.document_exists(VALID_HASH) is True

    snapshot = repo.get_snapshot(empresa="MRV", ano=2025, trimestre=3)
    assert snapshot is not None
    assert snapshot.lanc_vs_tri_anterior == -32.0
    assert snapshot.vend_acum_9m_atual == -5.0
    assert len(snapshot.lineage_entries) == 1
    assert snapshot.lineage_entries[0].pagina_origem == 4
    assert snapshot.lineage_entries[0].chunk_id == "vendas-mrv"


def test_same_hash_is_not_saved_twice(repo):
    record = _sample_record()
    repo.save_extraction(record, [LineageInfo(pdf_url=record.url_origem)])

    with pytest.raises(DocumentAlreadyProcessedError):
        repo.save_extraction(record, [LineageInfo(pdf_url=record.url_origem)])


def test_document_exists_after_first_save_blocks_reprocessing(repo):
    record = _sample_record()
    repo.save_extraction(record, [LineageInfo(pdf_url=record.url_origem)])

    if repo.document_exists(record.hash_documento):
        should_call_llm = False
    else:
        should_call_llm = True

    assert should_call_llm is False


def test_fixture_pdf_hash_is_stable():
    pdf_path = Path(__file__).resolve().parents[1] / "fixtures" / "Boletim_Conjuntura_2025_3T.pdf"
    if not pdf_path.exists():
        pytest.skip("Fixture PDF não encontrado")

    first = sha256_file(pdf_path)
    second = sha256_file(pdf_path)
    assert first == second
    assert len(first) == 64

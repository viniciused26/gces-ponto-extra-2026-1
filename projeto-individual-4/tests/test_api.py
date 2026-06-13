"""Testes da API REST."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from src.api.main import app, get_repository
from src.catalog.models import Base, Document, DocumentStatus, Lineage, MetricSnapshot
from src.catalog.repository import CatalogRepository, LineageInfo
from src.contracts.conjuntura import ConjunturaRecord

PROCESSING_TIME = datetime(2026, 6, 8, 2, 37, 53, tzinfo=timezone.utc)
VALID_HASH = "e53f30f5f67ebc739041680133ef33bedc87446cba7bb41ee9fbb0c4f3e65661"


@pytest.fixture
def repository(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api_test.db'}", future=True)
    Base.metadata.create_all(engine)
    repo = CatalogRepository(engine=engine)

    record = ConjunturaRecord(
        empresa="MRV",
        ano=2025,
        trimestre=3,
        lanc_vs_tri_anterior=-32.0,
        lanc_vs_mesmo_tri_ano_ant=-19.0,
        lanc_acum_9m_ano_ant=96.0,
        lanc_acum_9m_atual=20.0,
        vend_vs_tri_anterior=-12.0,
        vend_vs_mesmo_tri_ano_ant=-10.0,
        vend_acum_9m_ano_ant=9.0,
        vend_acum_9m_atual=-5.0,
        url_origem="local://fixtures/Boletim_Conjuntura_2025_3T.pdf",
        hash_documento=VALID_HASH,
        data_processamento=PROCESSING_TIME,
    )
    repo.save_extraction(
        record,
        [LineageInfo(pdf_url=record.url_origem, pagina_origem=1, chunk_id="full-scan")],
    )
    yield repo
    engine.dispose()


@pytest.fixture
def client(repository):
    app.dependency_overrides[get_repository] = lambda: repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"


def test_get_conjuntura_returns_metrics(client):
    response = client.get("/api/conjuntura", params={"empresa": "MRV", "ano": 2025, "trimestre": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["empresa"] == "MRV"
    assert payload["lanc_vs_tri_anterior"] == -32.0
    assert payload["hash_documento"] == VALID_HASH
    assert payload["lineage"][0]["chunk_id"] == "full-scan"


def test_get_conjuntura_not_found(client):
    response = client.get("/api/conjuntura", params={"empresa": "MRV", "ano": 2024, "trimestre": 1})
    assert response.status_code == 404
    assert "Nenhum registro encontrado" in response.json()["detail"]


def test_get_conjuntura_invalid_trimestre(client):
    response = client.get("/api/conjuntura", params={"empresa": "MRV", "ano": 2025, "trimestre": 9})
    assert response.status_code == 422


def test_get_lineage_by_snapshot_id(client):
    conjuntura = client.get("/api/conjuntura", params={"empresa": "MRV", "ano": 2025, "trimestre": 3}).json()
    snapshot_id = conjuntura["id"]

    response = client.get(f"/api/conjuntura/lineage/{snapshot_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == snapshot_id
    assert payload["url_origem"] == "local://fixtures/Boletim_Conjuntura_2025_3T.pdf"
    assert len(payload["lineage"]) == 1


def test_get_lineage_not_found(client):
    response = client.get("/api/conjuntura/lineage/9999")
    assert response.status_code == 404


def test_openapi_lists_all_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/api/conjuntura" in paths
    assert "/api/conjuntura/lineage/{snapshot_id}" in paths

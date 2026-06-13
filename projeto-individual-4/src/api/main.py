"""API REST do Pipeline UDA — Conjuntura Habitacional."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Generator

from fastapi import Depends, FastAPI, HTTPException, Query, status

from src.api.schemas import (
    ConjunturaResponse,
    ErrorResponse,
    HealthResponse,
    LineageResponse,
    snapshot_to_conjuntura_response,
    snapshot_to_lineage_response,
)
from src.catalog.repository import CatalogRepository

NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "Registro não encontrado.",
    }
}
VALIDATION_ERROR_RESPONSE = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Parâmetros inválidos.",
    }
}


def get_repository() -> Generator[CatalogRepository, None, None]:
    repository = CatalogRepository()
    yield repository


@asynccontextmanager
async def lifespan(_: FastAPI):
    CatalogRepository().init_db()
    yield


app = FastAPI(
    title="Pipeline UDA — Conjuntura Habitacional",
    description="API de métricas extraídas de prévias operacionais e boletins de conjuntura (RI).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

RepositoryDep = Annotated[CatalogRepository, Depends(get_repository)]


@app.get(
    "/health",
    tags=["Sistema"],
    summary="Verifica saúde da API e do banco",
    response_model=HealthResponse,
)
def health_check(repository: RepositoryDep) -> HealthResponse:
    db_ok = repository.check_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unavailable",
    )


@app.get(
    "/api/conjuntura",
    tags=["Conjuntura"],
    summary="Consulta métricas por empresa e período",
    response_model=ConjunturaResponse,
    responses={**NOT_FOUND_RESPONSE, **VALIDATION_ERROR_RESPONSE},
)
def get_conjuntura(
    repository: RepositoryDep,
    empresa: Annotated[str, Query(description="Nome da incorporadora.", examples=["MRV"])],
    ano: Annotated[int, Query(description="Ano de referência.", ge=2000, le=2100, examples=[2025])],
    trimestre: Annotated[int, Query(description="Trimestre (1 a 4).", ge=1, le=4, examples=[3])],
) -> ConjunturaResponse:
    snapshot = repository.get_snapshot(empresa=empresa, ano=ano, trimestre=trimestre)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum registro encontrado para {empresa} {ano}T{trimestre}.",
        )
    return snapshot_to_conjuntura_response(snapshot)


@app.get(
    "/api/conjuntura/lineage/{snapshot_id}",
    tags=["Linhagem"],
    summary="Consulta linhagem de um snapshot",
    response_model=LineageResponse,
    responses=NOT_FOUND_RESPONSE,
)
def get_lineage(snapshot_id: int, repository: RepositoryDep) -> LineageResponse:
    snapshot = repository.get_snapshot_by_id(snapshot_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} não encontrado.",
        )
    return snapshot_to_lineage_response(snapshot)

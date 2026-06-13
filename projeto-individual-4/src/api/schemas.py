"""Schemas de resposta da API REST (OpenAPI / Swagger)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.catalog.models import MetricSnapshot


class LineageItemResponse(BaseModel):
    pdf_url: str = Field(..., description="URL do PDF de origem.", examples=["https://ri.mrv.com.br/previa.pdf"])
    pagina_origem: Optional[int] = Field(None, description="Página de origem no PDF.", examples=[4])
    chunk_id: Optional[str] = Field(None, description="Identificador do chunk semântico.", examples=["page-4"])


class ConjunturaResponse(BaseModel):
    """Métricas de conjuntura com metadados de linhagem."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador do snapshot no catálogo.", examples=[1])
    empresa: str = Field(..., examples=["MRV"])
    ano: int = Field(..., examples=[2025])
    trimestre: int = Field(..., ge=1, le=4, examples=[3])

    lanc_vs_tri_anterior: Optional[float] = Field(None, examples=[-32.0])
    lanc_vs_mesmo_tri_ano_ant: Optional[float] = Field(None, examples=[-19.0])
    lanc_acum_9m_ano_ant: Optional[float] = Field(None, examples=[96.0])
    lanc_acum_9m_atual: Optional[float] = Field(None, examples=[20.0])
    vend_vs_tri_anterior: Optional[float] = Field(None, examples=[-12.0])
    vend_vs_mesmo_tri_ano_ant: Optional[float] = Field(None, examples=[-10.0])
    vend_acum_9m_ano_ant: Optional[float] = Field(None, examples=[9.0])
    vend_acum_9m_atual: Optional[float] = Field(None, examples=[-5.0])

    vendas_unidades: Optional[int] = Field(None, examples=[12500])
    vgv_milhoes: Optional[float] = Field(None, examples=[3200.5])
    lancamentos_unidades: Optional[int] = None
    estoque_unidades: Optional[int] = None
    obras_andamento: Optional[int] = None
    unidades_entregues: Optional[int] = None
    receita_liquida_milhoes: Optional[float] = None
    lucro_liquido_milhoes: Optional[float] = None

    url_origem: str = Field(
        ...,
        description="URL ou caminho do PDF original.",
        examples=["local://fixtures/Boletim_Conjuntura_2025_3T.pdf"],
    )
    hash_documento: str = Field(
        ...,
        description="Hash SHA-256 do PDF.",
        examples=["e53f30f5f67ebc739041680133ef33bedc87446cba7bb41ee9fbb0c4f3e65661"],
    )
    data_processamento: datetime = Field(..., description="Timestamp UTC do processamento.")
    lineage: list[LineageItemResponse] = Field(default_factory=list)


class LineageResponse(BaseModel):
    """Detalhes de linhagem de um snapshot."""

    snapshot_id: int = Field(..., examples=[1])
    empresa: str = Field(..., examples=["MRV"])
    ano: int = Field(..., examples=[2025])
    trimestre: int = Field(..., examples=[3])
    url_origem: str = Field(..., examples=["https://ri.mrv.com.br/previa.pdf"])
    hash_documento: str = Field(..., examples=["e53f30f5f67ebc739041680133ef33bedc87446cba7bb41ee9fbb0c4f3e65661"])
    data_processamento: datetime
    lineage: list[LineageItemResponse]


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    database: str = Field(..., examples=["connected"])


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Registro não encontrado."])


def snapshot_to_conjuntura_response(snapshot: MetricSnapshot) -> ConjunturaResponse:
    document = snapshot.document
    return ConjunturaResponse(
        id=snapshot.id,
        empresa=snapshot.empresa,
        ano=snapshot.ano,
        trimestre=snapshot.trimestre,
        lanc_vs_tri_anterior=snapshot.lanc_vs_tri_anterior,
        lanc_vs_mesmo_tri_ano_ant=snapshot.lanc_vs_mesmo_tri_ano_ant,
        lanc_acum_9m_ano_ant=snapshot.lanc_acum_9m_ano_ant,
        lanc_acum_9m_atual=snapshot.lanc_acum_9m_atual,
        vend_vs_tri_anterior=snapshot.vend_vs_tri_anterior,
        vend_vs_mesmo_tri_ano_ant=snapshot.vend_vs_mesmo_tri_ano_ant,
        vend_acum_9m_ano_ant=snapshot.vend_acum_9m_ano_ant,
        vend_acum_9m_atual=snapshot.vend_acum_9m_atual,
        vendas_unidades=snapshot.vendas_unidades,
        vgv_milhoes=snapshot.vgv_milhoes,
        lancamentos_unidades=snapshot.lancamentos_unidades,
        estoque_unidades=snapshot.estoque_unidades,
        obras_andamento=snapshot.obras_andamento,
        unidades_entregues=snapshot.unidades_entregues,
        receita_liquida_milhoes=snapshot.receita_liquida_milhoes,
        lucro_liquido_milhoes=snapshot.lucro_liquido_milhoes,
        url_origem=document.url,
        hash_documento=document.hash_sha256,
        data_processamento=snapshot.data_processamento,
        lineage=[
            LineageItemResponse(
                pdf_url=entry.pdf_url,
                pagina_origem=entry.pagina_origem,
                chunk_id=entry.chunk_id,
            )
            for entry in snapshot.lineage_entries
        ],
    )


def snapshot_to_lineage_response(snapshot: MetricSnapshot) -> LineageResponse:
    document = snapshot.document
    return LineageResponse(
        snapshot_id=snapshot.id,
        empresa=snapshot.empresa,
        ano=snapshot.ano,
        trimestre=snapshot.trimestre,
        url_origem=document.url,
        hash_documento=document.hash_sha256,
        data_processamento=snapshot.data_processamento,
        lineage=[
            LineageItemResponse(
                pdf_url=entry.pdf_url,
                pagina_origem=entry.pagina_origem,
                chunk_id=entry.chunk_id,
            )
            for entry in snapshot.lineage_entries
        ],
    )

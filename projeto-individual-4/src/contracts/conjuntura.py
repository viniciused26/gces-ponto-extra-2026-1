"""Contrato Semântico para métricas de conjuntura do setor habitacional."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConjunturaExtraction(BaseModel):
    """
    Saída da extração semântica (LLM).

    Campos de variação percentual refletem o Boletim de Conjuntura (lançamentos e vendas).
    Campos operacionais absolutos complementam prévias operacionais de RI quando presentes.

    Regras de negócio:
    - Todos os campos de métrica são opcionais; use null quando ausente no documento.
    - Variações percentuais devem ser números decimais (ex.: -32.0 representa -32%).
    - Valores absolutos apenas quando explicitamente informados (unidades, milhões de reais).
    - Proibido inferir, estimar ou calcular valores ausentes.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    empresa: str = Field(
        ...,
        min_length=1,
        description="Nome da incorporadora (ex.: MRV, Direcional, Tenda).",
    )
    ano: int = Field(..., ge=2000, le=2100, description="Ano de referência do período.")
    trimestre: int = Field(..., ge=1, le=4, description="Trimestre de referência (1 a 4).")

    # Variações percentuais — Boletim de Conjuntura
    lanc_vs_tri_anterior: Optional[float] = Field(
        None,
        description="Variação percentual de lançamentos vs trimestre anterior.",
    )
    lanc_vs_mesmo_tri_ano_ant: Optional[float] = Field(
        None,
        description="Variação percentual de lançamentos vs mesmo trimestre do ano anterior.",
    )
    lanc_acum_9m_ano_ant: Optional[float] = Field(
        None,
        description="Variação percentual acumulada em 9 meses — ano anterior.",
    )
    lanc_acum_9m_atual: Optional[float] = Field(
        None,
        description="Variação percentual acumulada em 9 meses — ano atual.",
    )
    vend_vs_tri_anterior: Optional[float] = Field(
        None,
        description="Variação percentual de vendas vs trimestre anterior.",
    )
    vend_vs_mesmo_tri_ano_ant: Optional[float] = Field(
        None,
        description="Variação percentual de vendas vs mesmo trimestre do ano anterior.",
    )
    vend_acum_9m_ano_ant: Optional[float] = Field(
        None,
        description="Variação percentual acumulada de vendas em 9 meses — ano anterior.",
    )
    vend_acum_9m_atual: Optional[float] = Field(
        None,
        description="Variação percentual acumulada de vendas em 9 meses — ano atual.",
    )

    # Valores absolutos — prévias operacionais de RI (complementares)
    vendas_unidades: Optional[int] = Field(
        None,
        ge=0,
        description="Unidades vendidas no período (valor absoluto).",
    )
    vgv_milhoes: Optional[float] = Field(
        None,
        ge=0,
        description="Volume Geral de Vendas (VGV) em milhões de reais.",
    )
    lancamentos_unidades: Optional[int] = Field(
        None,
        ge=0,
        description="Unidades lançadas no período.",
    )
    estoque_unidades: Optional[int] = Field(
        None,
        ge=0,
        description="Estoque de unidades disponíveis ao final do período.",
    )
    obras_andamento: Optional[int] = Field(
        None,
        ge=0,
        description="Obras em andamento (unidades ou empreendimentos).",
    )
    unidades_entregues: Optional[int] = Field(
        None,
        ge=0,
        description="Unidades entregues (chaves entregues) no período.",
    )
    receita_liquida_milhoes: Optional[float] = Field(
        None,
        ge=0,
        description="Receita líquida em milhões de reais.",
    )
    lucro_liquido_milhoes: Optional[float] = Field(
        None,
        ge=0,
        description="Lucro líquido em milhões de reais.",
    )


class ConjunturaRecord(ConjunturaExtraction):
    """
    Registro completo para catálogo, linhagem e API.

    Estende a extração do LLM com metadados de origem e processamento.
    """

    url_origem: str = Field(
        ...,
        min_length=1,
        description="URL ou caminho local do PDF de origem.",
    )
    hash_documento: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Hash SHA-256 (hex) do conteúdo binário do PDF.",
    )
    data_processamento: datetime = Field(
        ...,
        description="Timestamp UTC em que o documento foi processado.",
    )

    @field_validator("hash_documento")
    @classmethod
    def hash_must_be_hex(cls, value: str) -> str:
        try:
            int(value, 16)
        except ValueError as exc:
            raise ValueError("hash_documento deve ser uma string hexadecimal SHA-256.") from exc
        return value.lower()

    @classmethod
    def from_extraction(
        cls,
        extraction: ConjunturaExtraction,
        *,
        url_origem: str,
        hash_documento: str,
        data_processamento: datetime | None = None,
    ) -> ConjunturaRecord:
        """Monta registro persistível a partir da saída do LLM e da linhagem."""
        return cls(
            **extraction.model_dump(),
            url_origem=url_origem,
            hash_documento=hash_documento,
            data_processamento=data_processamento or _utcnow(),
        )

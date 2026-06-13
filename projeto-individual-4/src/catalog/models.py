"""Modelos SQLAlchemy do catálogo de dados e linhagem."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("hash_sha256", name="uq_documents_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.PENDING,
    )

    metric_snapshots: Mapped[list[MetricSnapshot]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    empresa: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trimestre: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    data_processamento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lanc_vs_tri_anterior: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanc_vs_mesmo_tri_ano_ant: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanc_acum_9m_ano_ant: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanc_acum_9m_atual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vend_vs_tri_anterior: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vend_vs_mesmo_tri_ano_ant: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vend_acum_9m_ano_ant: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vend_acum_9m_atual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    vendas_unidades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vgv_milhoes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lancamentos_unidades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estoque_unidades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    obras_andamento: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unidades_entregues: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    receita_liquida_milhoes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lucro_liquido_milhoes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    document: Mapped[Document] = relationship(back_populates="metric_snapshots")
    lineage_entries: Mapped[list[Lineage]] = relationship(
        back_populates="metric_snapshot",
        cascade="all, delete-orphan",
    )


class Lineage(Base):
    __tablename__ = "lineage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("metric_snapshots.id"),
        nullable=False,
        index=True,
    )
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    pagina_origem: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    metric_snapshot: Mapped[MetricSnapshot] = relationship(back_populates="lineage_entries")

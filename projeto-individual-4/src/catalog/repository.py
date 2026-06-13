"""Repositório do catálogo: idempotência por hash e persistência com linhagem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, joinedload, sessionmaker

from src.catalog.models import Base, Document, DocumentStatus, Lineage, MetricSnapshot
from src.config import DEFAULT_DB_URL, ensure_data_dirs
from src.contracts.conjuntura import ConjunturaRecord


class DocumentAlreadyProcessedError(Exception):
    """Levantada ao tentar persistir um documento cujo hash já existe no catálogo."""


@dataclass(frozen=True)
class LineageInfo:
    pdf_url: str
    pagina_origem: Optional[int] = None
    chunk_id: Optional[str] = None


class CatalogRepository:
    def __init__(self, db_url: str = DEFAULT_DB_URL, engine: Engine | None = None) -> None:
        ensure_data_dirs()
        self._engine = engine or create_engine(db_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self._engine)

    def document_exists(self, hash_sha256: str) -> bool:
        normalized = hash_sha256.lower()
        with self._session() as session:
            stmt = select(Document.id).where(Document.hash_sha256 == normalized).limit(1)
            return session.scalar(stmt) is not None

    def save_extraction(
        self,
        record: ConjunturaRecord,
        lineage: list[LineageInfo],
        *,
        downloaded_at: datetime | None = None,
    ) -> int:
        """
        Persiste documento, snapshot de métricas e entradas de linhagem.

        Raises:
            DocumentAlreadyProcessedError: se o hash já existir (idempotência).
        """
        if self.document_exists(record.hash_documento):
            raise DocumentAlreadyProcessedError(record.hash_documento)

        now = datetime.now(timezone.utc)
        with self._session() as session:
            document = Document(
                empresa=record.empresa,
                url=record.url_origem,
                hash_sha256=record.hash_documento.lower(),
                downloaded_at=downloaded_at,
                processed_at=record.data_processamento,
                status=DocumentStatus.PROCESSED,
            )
            session.add(document)
            session.flush()

            snapshot = MetricSnapshot(
                document_id=document.id,
                empresa=record.empresa,
                ano=record.ano,
                trimestre=record.trimestre,
                data_processamento=record.data_processamento,
                lanc_vs_tri_anterior=record.lanc_vs_tri_anterior,
                lanc_vs_mesmo_tri_ano_ant=record.lanc_vs_mesmo_tri_ano_ant,
                lanc_acum_9m_ano_ant=record.lanc_acum_9m_ano_ant,
                lanc_acum_9m_atual=record.lanc_acum_9m_atual,
                vend_vs_tri_anterior=record.vend_vs_tri_anterior,
                vend_vs_mesmo_tri_ano_ant=record.vend_vs_mesmo_tri_ano_ant,
                vend_acum_9m_ano_ant=record.vend_acum_9m_ano_ant,
                vend_acum_9m_atual=record.vend_acum_9m_atual,
                vendas_unidades=record.vendas_unidades,
                vgv_milhoes=record.vgv_milhoes,
                lancamentos_unidades=record.lancamentos_unidades,
                estoque_unidades=record.estoque_unidades,
                obras_andamento=record.obras_andamento,
                unidades_entregues=record.unidades_entregues,
                receita_liquida_milhoes=record.receita_liquida_milhoes,
                lucro_liquido_milhoes=record.lucro_liquido_milhoes,
            )
            session.add(snapshot)
            session.flush()

            for entry in lineage:
                session.add(
                    Lineage(
                        metric_snapshot_id=snapshot.id,
                        pdf_url=entry.pdf_url,
                        pagina_origem=entry.pagina_origem,
                        chunk_id=entry.chunk_id,
                    )
                )

            session.commit()
            return snapshot.id

    def get_snapshot(
        self,
        *,
        empresa: str,
        ano: int,
        trimestre: int,
    ) -> Optional[MetricSnapshot]:
        with self._session() as session:
            stmt = (
                select(MetricSnapshot)
                .options(
                    joinedload(MetricSnapshot.lineage_entries),
                    joinedload(MetricSnapshot.document),
                )
                .where(
                    MetricSnapshot.empresa == empresa,
                    MetricSnapshot.ano == ano,
                    MetricSnapshot.trimestre == trimestre,
                )
                .order_by(MetricSnapshot.data_processamento.desc())
                .limit(1)
            )
            return session.scalar(stmt)

    def get_snapshot_by_id(self, snapshot_id: int) -> Optional[MetricSnapshot]:
        with self._session() as session:
            stmt = (
                select(MetricSnapshot)
                .options(
                    joinedload(MetricSnapshot.lineage_entries),
                    joinedload(MetricSnapshot.document),
                )
                .where(MetricSnapshot.id == snapshot_id)
                .limit(1)
            )
            return session.scalar(stmt)

    def check_connection(self) -> bool:
        with self._session() as session:
            return session.execute(select(1)).scalar_one() == 1

    def _session(self) -> Session:
        return self._session_factory()

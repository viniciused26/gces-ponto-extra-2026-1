"""Orquestrador end-to-end: download → hash → extração → persistência."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from src.catalog.repository import CatalogRepository, LineageInfo
from src.config import CompanyConfig, get_settings, load_companies_config
from src.contracts.conjuntura import ConjunturaRecord
from src.extraction.gemini_extractor import GeminiExtractor, dump_extraction_preview
from src.ingestion.downloader import PDFDownloader
from src.ingestion.scraper import PdfLink, RIScraper

logger = logging.getLogger(__name__)


class ProcessStatus(str, Enum):
    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ProcessResult:
    status: ProcessStatus
    source_url: str
    empresa: str
    hash_sha256: str | None = None
    snapshot_id: int | None = None
    message: str = ""
    record: ConjunturaRecord | None = None


class IngestionPipeline:
    def __init__(
        self,
        repository: CatalogRepository | None = None,
        extractor: GeminiExtractor | None = None,
    ) -> None:
        self._repository = repository or CatalogRepository()
        self._repository.init_db()
        self._extractor = extractor or GeminiExtractor()

    def process_local_pdf(
        self,
        pdf_path: Path | str,
        *,
        empresa: str,
        url_origem: str | None = None,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
        persist: bool = True,
    ) -> ProcessResult:
        path = Path(pdf_path).resolve()
        source_url = url_origem or f"local://{path}"

        with PDFDownloader(self._repository) as downloader:
            download = downloader.register_local_pdf(path, source_url)

        if download.already_processed:
            logger.info("Documento já processado (hash=%s)", download.hash_sha256)
            return ProcessResult(
                status=ProcessStatus.SKIPPED,
                source_url=source_url,
                empresa=empresa,
                hash_sha256=download.hash_sha256,
                message="Hash já existente no catálogo — LLM não acionado.",
            )

        return self._extract_and_persist(
            pdf_path=path,
            source_url=source_url,
            empresa=empresa,
            file_hash=download.hash_sha256,
            downloaded_at=download.downloaded_at,
            ano_hint=ano_hint,
            trimestre_hint=trimestre_hint,
            persist=persist,
        )

    def process_pdf_link(
        self,
        link: PdfLink,
        *,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
        persist: bool = True,
    ) -> ProcessResult:
        try:
            with PDFDownloader(self._repository) as downloader:
                download = downloader.download(link.url, link.company)

            if download.already_processed:
                logger.info("PDF já processado: %s", link.url)
                return ProcessResult(
                    status=ProcessStatus.SKIPPED,
                    source_url=link.url,
                    empresa=link.company,
                    hash_sha256=download.hash_sha256,
                    message="Hash já existente no catálogo — LLM não acionado.",
                )

            return self._extract_and_persist(
                pdf_path=download.pdf_path,
                source_url=link.url,
                empresa=link.company,
                file_hash=download.hash_sha256,
                downloaded_at=download.downloaded_at,
                ano_hint=ano_hint,
                trimestre_hint=trimestre_hint,
                persist=persist,
            )
        except Exception as exc:
            logger.exception("Falha ao processar %s", link.url)
            return ProcessResult(
                status=ProcessStatus.FAILED,
                source_url=link.url,
                empresa=link.company,
                message=str(exc),
            )

    def poll_companies(
        self,
        companies: list[CompanyConfig] | None = None,
        *,
        persist: bool = True,
    ) -> list[ProcessResult]:
        company_configs = companies or load_companies_config()
        results: list[ProcessResult] = []

        with RIScraper() as scraper:
            for company in company_configs:
                logger.info("Varredura RI: %s (%s)", company.name, company.results_url)
                try:
                    links = scraper.discover_previa_links(company.results_url, company.name)
                except Exception as exc:
                    logger.exception("Erro ao varrer %s", company.name)
                    results.append(
                        ProcessResult(
                            status=ProcessStatus.FAILED,
                            source_url=company.results_url,
                            empresa=company.name,
                            message=str(exc),
                        )
                    )
                    continue

                logger.info("%d link(s) de prévia operacional encontrado(s) para %s", len(links), company.name)
                for link in links:
                    results.append(self.process_pdf_link(link, persist=persist))

        return results

    def _extract_and_persist(
        self,
        *,
        pdf_path: Path,
        source_url: str,
        empresa: str,
        file_hash: str,
        downloaded_at: datetime,
        ano_hint: Optional[int],
        trimestre_hint: Optional[int],
        persist: bool,
    ) -> ProcessResult:
        extraction, strategy, chunks = self._extractor.extract_from_pdf(
            pdf_path,
            empresa_hint=empresa,
            ano_hint=ano_hint,
            trimestre_hint=trimestre_hint,
        )
        record = ConjunturaRecord.from_extraction(
            extraction,
            url_origem=source_url,
            hash_documento=file_hash,
        )

        lineage = [
            LineageInfo(
                pdf_url=source_url,
                pagina_origem=chunk.page_start,
                chunk_id=chunk.chunk_id,
            )
            for chunk in chunks
        ]

        snapshot_id: int | None = None
        if persist:
            snapshot_id = self._repository.save_extraction(
                record,
                lineage,
                downloaded_at=downloaded_at,
            )

        logger.info(
            "Processado %s | empresa=%s | estratégia=%s | snapshot_id=%s",
            source_url,
            record.empresa,
            strategy,
            snapshot_id,
        )

        return ProcessResult(
            status=ProcessStatus.PROCESSED,
            source_url=source_url,
            empresa=record.empresa,
            hash_sha256=file_hash,
            snapshot_id=snapshot_id,
            message=f"Extraído com estratégia {strategy}.",
            record=record,
        )


def _print_results(results: list[ProcessResult]) -> None:
    for result in results:
        payload = {
            "status": result.status.value,
            "empresa": result.empresa,
            "source_url": result.source_url,
            "hash_sha256": result.hash_sha256,
            "snapshot_id": result.snapshot_id,
            "message": result.message,
        }
        if result.record:
            payload["record"] = result.record.model_dump(mode="json")
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Pipeline de ingestão UDA.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="Processa um PDF local")
    process_parser.add_argument("pdf", type=Path)
    process_parser.add_argument("--empresa", required=True)
    process_parser.add_argument("--ano", type=int)
    process_parser.add_argument("--trimestre", type=int, choices=[1, 2, 3, 4])
    process_parser.add_argument("--url-origem")
    process_parser.add_argument("--no-save", action="store_true", help="Não persiste no catálogo")

    poll_parser = subparsers.add_parser("poll", help="Varre Centrais de Resultados configuradas")
    poll_parser.add_argument("--no-save", action="store_true")

    args = parser.parse_args()
    pipeline = IngestionPipeline()
    get_settings()

    if args.command == "process":
        result = pipeline.process_local_pdf(
            args.pdf,
            empresa=args.empresa,
            url_origem=args.url_origem,
            ano_hint=args.ano,
            trimestre_hint=args.trimestre,
            persist=not args.no_save,
        )
        _print_results([result])
        return

    if args.command == "poll":
        results = pipeline.poll_companies(persist=not args.no_save)
        _print_results(results)


if __name__ == "__main__":
    main()

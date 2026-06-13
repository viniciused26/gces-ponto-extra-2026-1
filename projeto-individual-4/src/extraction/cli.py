"""CLI para extração manual de PDFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.extraction.gemini_extractor import dump_extraction_preview
from src.pipeline import IngestionPipeline, ProcessStatus


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai métricas de conjuntura de um PDF.")
    parser.add_argument("pdf", type=Path, help="Caminho do PDF")
    parser.add_argument("--empresa", required=True, help="Empresa alvo")
    parser.add_argument("--ano", type=int, help="Ano de referência")
    parser.add_argument("--trimestre", type=int, choices=[1, 2, 3, 4], help="Trimestre")
    parser.add_argument(
        "--url-origem",
        help="URL de origem para linhagem (default: local://<caminho>)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persiste no catálogo SQLite (data/conjuntura.db)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {pdf_path}")

    pipeline = IngestionPipeline()
    result = pipeline.process_local_pdf(
        pdf_path,
        empresa=args.empresa,
        url_origem=args.url_origem,
        ano_hint=args.ano,
        trimestre_hint=args.trimestre,
        persist=args.save,
    )

    output = {
        "status": result.status.value,
        "message": result.message,
        "hash_sha256": result.hash_sha256,
        "snapshot_id": result.snapshot_id,
    }
    if result.record:
        output["record"] = json.loads(dump_extraction_preview(result.record))

    print(json.dumps(output, indent=2, ensure_ascii=False))

    if result.status == ProcessStatus.FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

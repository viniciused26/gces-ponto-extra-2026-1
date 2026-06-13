"""CLI para extração manual de PDFs (validação da Fase 3)."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.contracts.conjuntura import ConjunturaRecord
from src.extraction.gemini_extractor import GeminiExtractor, dump_extraction_preview
from src.ingestion.hasher import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai métricas de conjuntura de um PDF.")
    parser.add_argument("pdf", type=Path, help="Caminho do PDF")
    parser.add_argument("--empresa", help="Filtrar/focar extração em uma empresa")
    parser.add_argument("--ano", type=int, help="Ano de referência")
    parser.add_argument("--trimestre", type=int, choices=[1, 2, 3, 4], help="Trimestre")
    parser.add_argument(
        "--url-origem",
        help="URL de origem para linhagem (default: local://<caminho>)",
    )
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"Arquivo não encontrado: {pdf_path}")

    url_origem = args.url_origem or f"local://{pdf_path}"
    file_hash = sha256_file(pdf_path)

    extractor = GeminiExtractor()
    extraction, strategy, chunks = extractor.extract_from_pdf(
        pdf_path,
        empresa_hint=args.empresa,
        ano_hint=args.ano,
        trimestre_hint=args.trimestre,
    )

    full_record = ConjunturaRecord.from_extraction(
        extraction,
        url_origem=url_origem,
        hash_documento=file_hash,
    )

    print(f"Estratégia: {strategy} ({len(chunks)} chunk(s))")
    print(f"Hash: {file_hash}")
    print(dump_extraction_preview(full_record))


if __name__ == "__main__":
    main()

"""Download de PDFs com verificação de hash e idempotência."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import httpx

from src.catalog.repository import CatalogRepository
from src.config import PDF_DIR
from src.ingestion.hasher import sha256_bytes, sha256_file
from src.ingestion.scraper import DEFAULT_USER_AGENT

INVALID_FILENAME_CHARS = re.compile(r"[^\w.\-]+")


@dataclass(frozen=True)
class DownloadResult:
    pdf_path: Path
    source_url: str
    hash_sha256: str
    downloaded_at: datetime
    already_processed: bool
    skipped_download: bool


class PDFDownloader:
    def __init__(
        self,
        repository: CatalogRepository,
        dest_dir: Path | None = None,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._repository = repository
        self._dest_dir = dest_dir or PDF_DIR
        self._dest_dir.mkdir(parents=True, exist_ok=True)
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PDFDownloader:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _build_filename(self, company: str, url: str) -> str:
        raw_name = unquote(url.rsplit("/", 1)[-1].split("?", 1)[0]) or "documento.pdf"
        if not raw_name.lower().endswith(".pdf"):
            raw_name = f"{raw_name}.pdf"
        safe_company = INVALID_FILENAME_CHARS.sub("_", company)
        safe_name = INVALID_FILENAME_CHARS.sub("_", raw_name)
        return f"{safe_company}_{safe_name}"

    def download(
        self,
        url: str,
        company: str,
        *,
        content: bytes | None = None,
    ) -> DownloadResult:
        file_hash = sha256_bytes(content) if content is not None else None
        already_processed = False
        skipped_download = False
        downloaded_at = datetime.now(timezone.utc)

        if file_hash and self._repository.document_exists(file_hash):
            already_processed = True
            existing_path = self._find_existing_pdf(file_hash)
            if existing_path:
                skipped_download = True
                return DownloadResult(
                    pdf_path=existing_path,
                    source_url=url,
                    hash_sha256=file_hash,
                    downloaded_at=downloaded_at,
                    already_processed=True,
                    skipped_download=True,
                )

        if content is None:
            response = self._client.get(url)
            response.raise_for_status()
            content = response.content

        file_hash = file_hash or sha256_bytes(content)
        if self._repository.document_exists(file_hash):
            target_path = self._dest_dir / self._build_filename(company, url)
            if not target_path.exists():
                target_path.write_bytes(content)
            return DownloadResult(
                pdf_path=target_path,
                source_url=url,
                hash_sha256=file_hash,
                downloaded_at=downloaded_at,
                already_processed=True,
                skipped_download=target_path.exists(),
            )

        target_path = self._dest_dir / self._build_filename(company, url)
        target_path.write_bytes(content)
        return DownloadResult(
            pdf_path=target_path,
            source_url=url,
            hash_sha256=file_hash,
            downloaded_at=downloaded_at,
            already_processed=False,
            skipped_download=False,
        )

    def register_local_pdf(self, pdf_path: Path, source_url: str) -> DownloadResult:
        file_hash = sha256_file(pdf_path)
        already_processed = self._repository.document_exists(file_hash)
        return DownloadResult(
            pdf_path=pdf_path.resolve(),
            source_url=source_url,
            hash_sha256=file_hash,
            downloaded_at=datetime.now(timezone.utc),
            already_processed=already_processed,
            skipped_download=True,
        )

    def _find_existing_pdf(self, file_hash: str) -> Path | None:
        for pdf_path in self._dest_dir.glob("*.pdf"):
            if sha256_file(pdf_path) == file_hash:
                return pdf_path
        return None

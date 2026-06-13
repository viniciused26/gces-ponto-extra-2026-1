"""Extração estruturada de métricas via Google Gemini."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from src.config import Settings, get_settings
from src.contracts.conjuntura import ConjunturaExtraction, ConjunturaRecord
from src.extraction.chunker import TextChunk, chunk_pages, chunking_strategy
from src.extraction.pdf_reader import read_pdf_pages
from src.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_response_schema


class GeminiExtractionError(Exception):
    """Erro na chamada ou validação da resposta do Gemini."""


def merge_extractions(extractions: list[ConjunturaExtraction]) -> ConjunturaExtraction:
    """Combina resultados de múltiplos chunks preenchendo campos ausentes."""
    if not extractions:
        raise ValueError("Lista de extrações vazia.")

    merged_data = extractions[0].model_dump()
    for extraction in extractions[1:]:
        for field, value in extraction.model_dump().items():
            if merged_data.get(field) is None and value is not None:
                merged_data[field] = value

    return ConjunturaExtraction.model_validate(merged_data)


def _build_user_prompt(
    chunk: TextChunk,
    *,
    empresa_hint: Optional[str] = None,
    ano_hint: Optional[int] = None,
    trimestre_hint: Optional[int] = None,
) -> str:
    hints: list[str] = []
    if empresa_hint:
        hints.append(f"Empresa alvo: {empresa_hint}")
    if ano_hint:
        hints.append(f"Ano de referência: {ano_hint}")
    if trimestre_hint:
        hints.append(f"Trimestre de referência: {trimestre_hint}")

    header = "\n".join(hints)
    context = f"Chunk: {chunk.chunk_id}"
    if chunk.title:
        context += f" | Seção: {chunk.title}"

    return f"{header}\n{context}\n\n{chunk.text}".strip()


class GeminiExtractor:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = genai.Client(api_key=self._settings.gemini_api_key)

    def extract_chunk(
        self,
        chunk: TextChunk,
        *,
        empresa_hint: Optional[str] = None,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
    ) -> ConjunturaExtraction:
        user_prompt = _build_user_prompt(
            chunk,
            empresa_hint=empresa_hint,
            ano_hint=ano_hint,
            trimestre_hint=trimestre_hint,
        )

        response = self._client.models.generate_content(
            model=self._settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=extraction_response_schema(),
                temperature=0,
            ),
        )

        raw_text = response.text
        if not raw_text:
            raise GeminiExtractionError("Gemini retornou resposta vazia.")

        try:
            return ConjunturaExtraction.model_validate_json(raw_text)
        except Exception as exc:
            raise GeminiExtractionError(f"Resposta inválida do Gemini: {raw_text}") from exc

    def extract_from_chunks(
        self,
        chunks: list[TextChunk],
        *,
        empresa_hint: Optional[str] = None,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
    ) -> ConjunturaExtraction:
        if not chunks:
            raise ValueError("Nenhum chunk fornecido para extração.")

        extractions = [
            self.extract_chunk(
                chunk,
                empresa_hint=empresa_hint,
                ano_hint=ano_hint,
                trimestre_hint=trimestre_hint,
            )
            for chunk in chunks
        ]
        return merge_extractions(extractions)

    def extract_from_pdf(
        self,
        pdf_path: Path | str,
        *,
        empresa_hint: Optional[str] = None,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
    ) -> tuple[ConjunturaExtraction, str, list[TextChunk]]:
        """
        Extrai métricas de um PDF local.

        Returns:
            Tupla (extração, estratégia de chunking, chunks utilizados).
        """
        pages = read_pdf_pages(pdf_path)
        chunks = chunk_pages(pages)
        strategy = chunking_strategy(pages)
        extraction = self.extract_from_chunks(
            chunks,
            empresa_hint=empresa_hint,
            ano_hint=ano_hint,
            trimestre_hint=trimestre_hint,
        )
        return extraction, strategy, chunks

    def extract_to_record(
        self,
        pdf_path: Path | str,
        *,
        url_origem: str,
        hash_documento: str,
        empresa_hint: Optional[str] = None,
        ano_hint: Optional[int] = None,
        trimestre_hint: Optional[int] = None,
    ) -> ConjunturaRecord:
        extraction, _, _ = self.extract_from_pdf(
            pdf_path,
            empresa_hint=empresa_hint,
            ano_hint=ano_hint,
            trimestre_hint=trimestre_hint,
        )
        return ConjunturaRecord.from_extraction(
            extraction,
            url_origem=url_origem,
            hash_documento=hash_documento,
        )


def dump_extraction_preview(result: ConjunturaExtraction | ConjunturaRecord) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False)

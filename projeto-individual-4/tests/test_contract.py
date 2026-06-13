"""Testes de validação do Contrato Semântico Pydantic."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.contracts.conjuntura import ConjunturaExtraction, ConjunturaRecord

VALID_HASH = "e53f30f5f67ebc739041680133ef33bedc87446cba7bb41ee9fbb0c4f3e65661"
PROCESSING_TIME = datetime(2026, 6, 8, 2, 37, 53, 665189, tzinfo=timezone.utc)


def test_record_matches_boletim_example():
    record = ConjunturaRecord(
        empresa="MRV",
        ano=2025,
        trimestre=3,
        lanc_vs_tri_anterior=-32.0,
        lanc_vs_mesmo_tri_ano_ant=-19.0,
        lanc_acum_9m_ano_ant=96.0,
        lanc_acum_9m_atual=20.0,
        vend_vs_tri_anterior=-12.0,
        vend_vs_mesmo_tri_ano_ant=-10.0,
        vend_acum_9m_ano_ant=9.0,
        vend_acum_9m_atual=-5.0,
        url_origem="local://...exemplo_Boletim_Conjuntura_2025_3T.pdf",
        hash_documento=VALID_HASH,
        data_processamento=PROCESSING_TIME,
    )

    assert record.empresa == "MRV"
    assert record.lanc_vs_tri_anterior == -32.0
    assert record.vend_acum_9m_atual == -5.0
    assert record.vendas_unidades is None


def test_extraction_accepts_partial_metrics():
    extraction = ConjunturaExtraction(
        empresa="MRV",
        ano=2026,
        trimestre=1,
        vendas_unidades=12_500,
        vgv_milhoes=3_200.5,
    )

    assert extraction.vendas_unidades == 12_500
    assert extraction.lanc_vs_tri_anterior is None


def test_from_extraction_builds_record():
    extraction = ConjunturaExtraction(
        empresa="MRV",
        ano=2025,
        trimestre=3,
        lanc_vs_tri_anterior=-32.0,
    )
    record = ConjunturaRecord.from_extraction(
        extraction,
        url_origem="local://boletim.pdf",
        hash_documento=VALID_HASH,
        data_processamento=PROCESSING_TIME,
    )

    assert record.lanc_vs_tri_anterior == -32.0
    assert record.url_origem == "local://boletim.pdf"
    assert record.hash_documento == VALID_HASH


def test_extraction_rejects_invalid_trimestre():
    with pytest.raises(ValidationError):
        ConjunturaExtraction(empresa="MRV", ano=2025, trimestre=5)


def test_record_rejects_invalid_hash():
    with pytest.raises(ValidationError):
        ConjunturaRecord(
            empresa="MRV",
            ano=2025,
            trimestre=3,
            url_origem="https://example.com/doc.pdf",
            hash_documento="hash-curto",
            data_processamento=PROCESSING_TIME,
        )


def test_extraction_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ConjunturaExtraction(
            empresa="MRV",
            ano=2025,
            trimestre=3,
            campo_desconhecido=1.0,
        )


def test_extraction_rejects_negative_absolute_values():
    with pytest.raises(ValidationError):
        ConjunturaExtraction(
            empresa="MRV",
            ano=2025,
            trimestre=3,
            vendas_unidades=-1,
        )


def test_json_schema_has_variation_fields():
    schema = ConjunturaExtraction.model_json_schema()
    props = schema["properties"]

    assert "lanc_vs_tri_anterior" in props
    assert "vend_acum_9m_atual" in props
    assert "empresa" in props


def test_prompts_module_exports_system_prompt():
    from src.extraction.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_response_schema

    assert "lanc_vs_tri_anterior" in EXTRACTION_SYSTEM_PROMPT
    assert "vendas_unidades" in EXTRACTION_SYSTEM_PROMPT
    assert "null" in EXTRACTION_SYSTEM_PROMPT.lower()

    response_schema = extraction_response_schema()
    assert response_schema["title"] == "ConjunturaExtraction"

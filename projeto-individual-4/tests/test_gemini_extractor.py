"""Testes do merge de extrações e integração opcional com Gemini."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.contracts.conjuntura import ConjunturaExtraction
from src.extraction.gemini_extractor import GeminiExtractor, merge_extractions

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BOLETIM = FIXTURES / "Boletim_Conjuntura_2025_3T.pdf"


def test_merge_extractions_fills_missing_fields():
    first = ConjunturaExtraction(empresa="MRV", ano=2025, trimestre=3, lanc_vs_tri_anterior=-32.0)
    second = ConjunturaExtraction(
        empresa="MRV",
        ano=2025,
        trimestre=3,
        vend_acum_9m_atual=-5.0,
    )

    merged = merge_extractions([first, second])
    assert merged.lanc_vs_tri_anterior == -32.0
    assert merged.vend_acum_9m_atual == -5.0


def test_merge_extractions_requires_at_least_one_item():
    with pytest.raises(ValueError):
        merge_extractions([])


@patch("src.extraction.gemini_extractor.genai.Client")
def test_extract_from_pdf_boletim_with_mock(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {
            "empresa": "MRV",
            "ano": 2025,
            "trimestre": 3,
            "lanc_vs_tri_anterior": -32.0,
            "lanc_vs_mesmo_tri_ano_ant": -19.0,
            "lanc_acum_9m_ano_ant": 96.0,
            "lanc_acum_9m_atual": 20.0,
            "vend_vs_tri_anterior": -12.0,
            "vend_vs_mesmo_tri_ano_ant": -10.0,
            "vend_acum_9m_ano_ant": 9.0,
            "vend_acum_9m_atual": -5.0,
            "vendas_unidades": None,
            "vgv_milhoes": None,
            "lancamentos_unidades": None,
            "estoque_unidades": None,
            "obras_andamento": None,
            "unidades_entregues": None,
            "receita_liquida_milhoes": None,
            "lucro_liquido_milhoes": None,
        }
    )
    mock_client_cls.return_value.models.generate_content.return_value = mock_response

    with patch("src.extraction.gemini_extractor.get_settings") as mock_settings:
        mock_settings.return_value.gemini_api_key = "test-key"
        mock_settings.return_value.gemini_model = "gemini-2.0-flash"

        extractor = GeminiExtractor()
        extraction, strategy, chunks = extractor.extract_from_pdf(
            BOLETIM,
            empresa_hint="MRV",
            ano_hint=2025,
            trimestre_hint=3,
        )

    assert strategy == "full-scan"
    assert len(chunks) == 1
    assert extraction.empresa == "MRV"
    assert extraction.lanc_vs_tri_anterior == -32.0


@pytest.mark.integration
def test_extract_boletim_mrv_live():
    """Requer GEMINI_API_KEY válida em .env — rode com: pytest -m integration"""
    from google.genai.errors import ClientError

    from src.config import get_settings

    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY não configurada")

    extractor = GeminiExtractor(settings=settings)
    try:
        extraction, strategy, _ = extractor.extract_from_pdf(
            BOLETIM,
            empresa_hint="MRV",
            ano_hint=2025,
            trimestre_hint=3,
        )
    except ClientError as exc:
        if exc.code == 429:
            pytest.skip(f"Cota da API Gemini esgotada: {exc}")
        raise

    assert extraction.empresa.upper() == "MRV"
    assert extraction.ano == 2025
    assert extraction.trimestre == 3
    assert extraction.lanc_vs_tri_anterior is not None
    assert strategy == "full-scan"

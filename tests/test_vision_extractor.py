
import pytest

from app.services.vision import (
    VisionExtractorError,
    _normalize_payload,
    _openai_token_limit_param,
    _parse_json_response,
)


def test_parse_json_response_plain():
    raw = '{"fornecedor": "BH", "itens": []}'
    result = _parse_json_response(raw)
    assert result["fornecedor"] == "BH"


def test_parse_json_response_markdown_fence():
    raw = '```json\n{"fornecedor": "BH", "itens": []}\n```'
    result = _parse_json_response(raw)
    assert result["fornecedor"] == "BH"


def test_parse_json_response_invalid():
    with pytest.raises(VisionExtractorError):
        _parse_json_response("not json")


def test_normalize_payload_aliases():
    payload = {"supplier": "Loja", "items": [{"descricao": "X", "valor": 1}]}
    normalized = _normalize_payload(payload)
    assert normalized["fornecedor"] == "Loja"
    assert "itens" in normalized


@pytest.mark.parametrize(
    ("model", "expected_key"),
    [
        ("gpt-4o", "max_tokens"),
        ("gpt-4o-mini", "max_tokens"),
        ("gpt-5.4", "max_completion_tokens"),
        ("gpt-5", "max_completion_tokens"),
        ("o1-preview", "max_completion_tokens"),
        ("o3-mini", "max_completion_tokens"),
    ],
)
def test_openai_token_limit_param(model: str, expected_key: str):
    params = _openai_token_limit_param(model, 4096)
    assert expected_key in params
    assert params[expected_key] == 4096
    assert len(params) == 1

import json
import re

import pytest

from app.services.vision import VisionExtractorError, _normalize_payload, _parse_json_response


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

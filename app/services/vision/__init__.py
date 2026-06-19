import base64
import json
import re
from typing import Protocol

import httpx

from app.config import get_settings
from app.schemas.extraction import ExtractedInvoice, VisionExtractionResult
from app.services.vision.prompts import EXTRACTION_PROMPT

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-sonnet-4-20250514",
}


class VisionExtractorError(Exception):
    pass


class VisionExtractor(Protocol):
    async def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> VisionExtractionResult:
        ...


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise VisionExtractorError("AI response is not valid JSON") from exc


def _normalize_payload(payload: dict) -> dict:
    if "itens" not in payload and "items" in payload:
        payload["itens"] = payload.pop("items")
    if "fornecedor" not in payload and "supplier" in payload:
        payload["fornecedor"] = payload.pop("supplier")
    return payload


class OpenAIVisionExtractor:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> VisionExtractionResult:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{content_type};base64,{b64}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": EXTRACTION_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4096,
                },
            )
        if response.status_code != 200:
            raise VisionExtractorError(f"OpenAI error: {response.status_code} {response.text}")
        content = response.json()["choices"][0]["message"]["content"]
        raw = _parse_json_response(content)
        invoice = ExtractedInvoice.model_validate(_normalize_payload(raw))
        return VisionExtractionResult(invoice=invoice, raw_response=raw, model=self._model)


class GeminiVisionExtractor:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> VisionExtractionResult:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": EXTRACTION_PROMPT},
                                {"inline_data": {"mime_type": content_type, "data": b64}},
                            ]
                        }
                    ],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
        if response.status_code != 200:
            raise VisionExtractorError(f"Gemini error: {response.status_code} {response.text}")
        parts = response.json()["candidates"][0]["content"]["parts"]
        text = parts[0].get("text", "")
        raw = _parse_json_response(text)
        invoice = ExtractedInvoice.model_validate(_normalize_payload(raw))
        return VisionExtractionResult(invoice=invoice, raw_response=raw, model=self._model)


class AnthropicVisionExtractor:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def extract(self, image_bytes: bytes, content_type: str = "image/jpeg") -> VisionExtractionResult:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": content_type,
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": EXTRACTION_PROMPT},
                            ],
                        }
                    ],
                },
            )
        if response.status_code != 200:
            raise VisionExtractorError(f"Anthropic error: {response.status_code} {response.text}")
        content_blocks = response.json()["content"]
        text = next((b["text"] for b in content_blocks if b.get("type") == "text"), "")
        raw = _parse_json_response(text)
        invoice = ExtractedInvoice.model_validate(_normalize_payload(raw))
        return VisionExtractionResult(invoice=invoice, raw_response=raw, model=self._model)


def get_vision_extractor() -> VisionExtractor:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if not provider:
        raise VisionExtractorError("LLM_PROVIDER is not configured")
    if not settings.llm_provider_api_key:
        raise VisionExtractorError("LLM_PROVIDER_API_KEY is not configured")

    model = settings.llm_model or DEFAULT_MODELS.get(provider, "")
    if not model:
        raise VisionExtractorError(f"Unknown LLM provider: {provider}")

    if provider == "openai":
        return OpenAIVisionExtractor(settings.llm_provider_api_key, model)
    if provider == "gemini":
        return GeminiVisionExtractor(settings.llm_provider_api_key, model)
    if provider == "anthropic":
        return AnthropicVisionExtractor(settings.llm_provider_api_key, model)
    raise VisionExtractorError(f"Unsupported LLM provider: {provider}")

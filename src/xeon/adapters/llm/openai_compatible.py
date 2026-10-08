from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from xeon.application.ports.llm import ChatMessage, LLMResponse


class LLMProviderError(RuntimeError):
    """Sanitized provider failure safe to map to an API error."""


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "max_tokens": self._max_output_tokens,
            "stream": False,
        }
        try:
            response = await self._client.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            text = _extract_text(response.json())
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"El proveedor LLM respondio con HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(
                "No fue posible obtener una respuesta valida del proveedor LLM."
            ) from exc

        return LLMResponse(text=text, provider="grok", model=self._model)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty LLM response")
    return content.strip()

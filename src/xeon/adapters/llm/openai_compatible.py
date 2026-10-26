from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from xeon.application.ports.llm import ChatMessage, LLMProviderError, LLMResponse, TokenUsage


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: float,
        provider_name: str = "groq",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._api_key = api_key
        self._provider_name = provider_name
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        payload = {
            "model": self.model,
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
            body = response.json()
            text = _extract_text(body)
            usage = _extract_usage(body)
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"El proveedor LLM respondio con HTTP {exc.response.status_code}."
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(
                "No fue posible obtener una respuesta valida del proveedor LLM."
            ) from exc

        return LLMResponse(text=text, provider=self.provider_name, model=self.model, usage=usage)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _extract_usage(payload: dict[str, Any]) -> TokenUsage:
    """Read the OpenAI-style usage block; absent or malformed values stay unknown."""
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return TokenUsage()

    def count(name: str) -> int | None:
        value = raw.get(name)
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )

    return TokenUsage(count("prompt_tokens"), count("completion_tokens"))


def _extract_text(payload: dict[str, Any]) -> str:
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty LLM response")
    return content.strip()

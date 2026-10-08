from __future__ import annotations

from xeon.adapters.llm.mock import MockLLM
from xeon.adapters.llm.openai_compatible import OpenAICompatibleLLM
from xeon.application.ports.llm import LLMPort
from xeon.config import Settings


def build_llm(settings: Settings) -> LLMPort:
    if settings.llm_provider == "mock":
        return MockLLM()

    key = settings.require_reto_key().get_secret_value()
    return OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        api_key=key,
        model=settings.llm_model,
        max_output_tokens=settings.llm_max_output_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
    )

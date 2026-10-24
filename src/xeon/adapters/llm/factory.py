from __future__ import annotations

from xeon.adapters.llm.mock import MockLLM
from xeon.adapters.llm.openai_compatible import OpenAICompatibleLLM
from xeon.application.ports.llm import LLMPort
from xeon.config import Settings, SettingsError


def build_llm(settings: Settings) -> LLMPort:
    if settings.llm_provider == "mock":
        return MockLLM()

    if settings.llm_provider == "hermes":
        hermes_key = settings.resolve_hermes_api_key().get_secret_value()
        return OpenAICompatibleLLM(
            base_url=settings.hermes_base_url,
            api_key=hermes_key,
            model=settings.hermes_model,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            provider_name="hermes",
        )

    if settings.llm_provider == "grok":
        model = settings.grok_model.strip()
        if not model:
            raise SettingsError("LLM_PROVIDER=grok requiere GROK_MODEL explicito.")
        key = settings.require_grok_api_key().get_secret_value()
        return OpenAICompatibleLLM(
            base_url=settings.grok_base_url,
            api_key=key,
            model=model,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            provider_name="grok",
        )

    key = settings.require_groq_api_key().get_secret_value()
    return OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        api_key=key,
        model=settings.llm_model,
        max_output_tokens=settings.llm_max_output_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        provider_name="groq",
    )

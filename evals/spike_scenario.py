"""Minimal Scenario integration with XEON's in-process mock.

Run without network: ``uv run --group evals python evals/spike_scenario.py``.
``--live`` makes at most one Grok request for the user simulator. The judge is
configured but deliberately not called in this one-request smoke test. Full
evaluations must budget separate simulator and judge requests.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any
from uuid import uuid4

import httpx

# The module-level FastAPI app is created on import. Keep this smoke test local.
os.environ["LLM_PROVIDER"] = "mock"
os.environ["WHATSAPP_SEND_ENABLED"] = "false"
os.environ.pop("LANGWATCH_API_KEY", None)

import litellm
import scenario
from scenario.config import ModelConfig

from xeon.api.app import create_app
from xeon.config import Settings

MODEL = "openai/grok-4.6"
BASE_URL = "https://api.reto.pltk.mx/v1"


class XeonMock(scenario.AgentAdapter):  # type: ignore[misc]
    """Call XEON through ASGI while preserving its required UUID conversation ID."""

    def __init__(self) -> None:
        self._app = create_app(Settings(_env_file=None, llm_provider="mock"))  # type: ignore[call-arg]
        self._conversation_id = str(uuid4())

    async def call(self, input: scenario.AgentInput) -> str:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app), base_url="http://xeon.local"
        ) as client:
            response = await client.post(
                "/v1/chat",
                json={
                    "message": input.last_new_user_message_str(),
                    "conversation_id": self._conversation_id,
                },
            )
        response.raise_for_status()
        data = response.json()
        if data["provider"] != "mock":
            raise RuntimeError("XEON smoke test expected the mock provider.")
        return str(data["reply"])


async def run(*, live: bool) -> bool:
    """Run one simulator turn; keep all LangWatch exporters disabled."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    scenario.setup_scenario_tracing(instrumentors=[], span_processors=[], trace_exporter=None)

    api_key = Settings().require_grok_api_key().get_secret_value() if live else "offline-key"
    config = ModelConfig(model=MODEL, api_base=BASE_URL, api_key=api_key, max_tokens=80)
    extra = {} if live else {"mock_response": "Hola, necesito cemento"}
    simulator = scenario.UserSimulatorAgent(
        model=config.model,
        api_base=config.api_base,
        api_key=config.api_key,
        max_tokens=config.max_tokens,
        num_retries=0,
        timeout=30,
        **extra,
    )
    judge = scenario.JudgeAgent(
        criteria=["Responde con claridad sobre el producto solicitado."],
        model=config.model,
        api_base=config.api_base,
        api_key=config.api_key,
        max_tokens=config.max_tokens,
        **extra,
    )
    # Scenario 1.6 always sends temperature=0.0; the gateway may reject it.
    # Pin the optional dependency until this private compatibility hook is removed.
    simulator._provider_compat._adaptations.add("drop_temperature")
    judge._provider_compat._adaptations.add("drop_temperature")

    original_send = httpx.Client.send
    original_completion = litellm.completion
    gateway_requests = 0
    model_calls = 0

    def guarded_send(client: httpx.Client, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        nonlocal gateway_requests
        if not live:
            raise RuntimeError("Offline spike blocked an outbound HTTP request.")
        if request.url.host == "api.reto.pltk.mx":
            if gateway_requests >= 1:
                raise RuntimeError("Gateway request limit reached.")
            gateway_requests += 1
        return original_send(client, request, **kwargs)

    def guarded_completion(*args: object, **kwargs: object) -> object:
        nonlocal model_calls
        if model_calls >= 1:
            raise RuntimeError("Model call limit reached.")
        model_calls += 1
        return original_completion(*args, **kwargs)

    httpx.Client.send = guarded_send  # type: ignore[method-assign, assignment]
    litellm.completion = guarded_completion
    try:
        result = await scenario.arun(
            name="XEON conversational spike",
            description="One short commercial question to XEON mock",
            agents=[XeonMock(), simulator, judge],
            script=[scenario.user(), scenario.agent(), scenario.succeed()],
            max_turns=1,
            verbose=False,
            fetch_remote_traces=False,
        )
        return bool(result.success)
    finally:
        httpx.Client.send = original_send  # type: ignore[method-assign]
        litellm.completion = original_completion


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow one Grok simulator request")
    args = parser.parse_args()
    try:
        success = asyncio.run(run(live=args.live))
    except Exception as exc:
        # Provider exceptions can embed request details; never print their messages.
        print(f"spike=failed error_type={type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"spike={'ok' if success else 'failed'} mode={'live' if args.live else 'offline'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())

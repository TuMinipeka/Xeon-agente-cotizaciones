from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr

from xeon.application.container import AppContainer, build_container
from xeon.config import Settings

LogResult = Literal["ok", "warn", "error"]


class Engine(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def base_url(self) -> str: ...

    async def run(self, message: str, conversation_id: UUID) -> str: ...

    async def aclose(self) -> None: ...


class InProcessEngine:
    def __init__(self, settings: Settings) -> None:
        self._container: AppContainer = build_container(settings)

    @property
    def provider(self) -> str:
        return self._container.llm.provider_name

    @property
    def model(self) -> str:
        return self._container.llm.model

    @property
    def base_url(self) -> str:
        settings = self._container.settings
        if self.provider == "grok":
            return settings.grok_base_url
        if self.provider == "groq":
            return settings.llm_base_url
        return "local"

    async def run(self, message: str, conversation_id: UUID) -> str:
        response = await self._container.agent.respond(
            message, conversation_key=str(conversation_id)
        )
        return response.text

    async def aclose(self) -> None:
        await self._container.aclose()


class HTTPEngine:
    def __init__(
        self, api_url: str, settings: Settings, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._provider: str = settings.llm_provider
        self._model = settings.grok_model if self._provider == "grok" else settings.llm_model
        self._client = client or httpx.AsyncClient(timeout=130)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._api_url

    async def refresh(self) -> None:
        response = await self._client.get(f"{self._api_url}/health")
        response.raise_for_status()
        payload = response.json()
        self._provider = str(payload["provider"])
        self._model = str(payload["model"])

    async def run(self, message: str, conversation_id: UUID) -> str:
        response = await self._client.post(
            f"{self._api_url}/v1/chat",
            json={"message": message, "conversation_id": str(conversation_id)},
        )
        response.raise_for_status()
        payload = response.json()
        self._provider = str(payload["provider"])
        self._model = str(payload["model"])
        return str(payload["reply"])

    async def aclose(self) -> None:
        await self._client.aclose()


@dataclass(frozen=True, slots=True)
class SessionLog:
    at: datetime
    command: str
    provider: str
    latency_ms: int
    result: LogResult


@dataclass(slots=True)
class Session:
    engine: Engine
    key_status: str = "missing"
    conversation_id: UUID = field(default_factory=uuid4)
    turns: int = 0
    logs: deque[SessionLog] = field(default_factory=lambda: deque(maxlen=100))

    def new(self) -> None:
        self.conversation_id = uuid4()
        self.turns = 0

    def record(self, command: str, result: LogResult, started: float) -> None:
        self.logs.append(
            SessionLog(
                at=datetime.now(UTC),
                command=command,
                provider=self.engine.provider,
                latency_ms=round((perf_counter() - started) * 1000),
                result=result,
            )
        )

    async def run(self, message: str) -> str:
        started = perf_counter()
        try:
            reply = await self.engine.run(message, self.conversation_id)
        except Exception:
            self.record("run", "error", started)
            raise
        self.turns += 1
        self.record("run", "ok", started)
        return reply


def key_status(settings: Settings) -> str:
    """Inspect configuration metadata only; never resolve or read a secret."""
    if settings.llm_provider == "mock":
        return "not required"
    if settings.llm_provider == "grok":
        return _key_configured(settings.grok_api_key, settings.grok_api_key_file)
    if settings.llm_provider == "groq":
        return _key_configured(settings.groq_api_key, settings.groq_api_key_file)
    return "not required"


def _key_configured(value: SecretStr | None, path: Path | None) -> str:
    has_value = value is not None and bool(value.get_secret_value().strip())
    has_file = path is not None and path.is_file()
    return "configured" if has_value or has_file else "missing"

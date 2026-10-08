from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from xeon.adapters.llm import build_llm
from xeon.adapters.llm.openai_compatible import LLMProviderError
from xeon.agent.service import AgentService
from xeon.api.schemas import ChatRequest, ChatResponse, HealthResponse
from xeon.application.ports.llm import LLMPort
from xeon.config import Settings, get_settings


def create_app(settings: Settings | None = None, llm: LLMPort | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    agent = AgentService(llm or build_llm(runtime_settings))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await agent.aclose()

    application = FastAPI(
        title="XEON API",
        version="0.1.0",
        description="Base conversacional; no emite ni aprueba cotizaciones.",
        lifespan=lifespan,
    )

    @application.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            environment=runtime_settings.app_env,
            provider=runtime_settings.llm_provider,
            model=runtime_settings.llm_model,
        )

    @application.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        try:
            result = await agent.respond(request.message)
        except LLMProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ChatResponse(
            conversation_id=request.conversation_id,
            reply=result.text,
            provider=result.provider,
            model=result.model,
        )

    return application


app = create_app()

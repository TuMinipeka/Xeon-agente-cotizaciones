"""Tokens, latency and cost metrics: deterministic, no paid calls, no personal data."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from xeon.adapters.llm.metered import MeteredLLM
from xeon.adapters.llm.mock import MockLLM
from xeon.adapters.llm.openai_compatible import OpenAICompatibleLLM
from xeon.adapters.metrics import InMemoryMetrics, JsonlMetrics
from xeon.adapters.metrics.factory import build_pricing
from xeon.application.container import build_container
from xeon.application.observability import (
    TokenPricing,
    aggregate,
    metric_context,
    percentile,
    timed,
)
from xeon.application.ports.llm import ChatMessage, LLMResponse, TokenUsage
from xeon.config import Settings

HOLA = (ChatMessage(role="user", content="hola"),)


def _adapter(payload: dict[str, object]) -> tuple[OpenAICompatibleLLM, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    return (
        OpenAICompatibleLLM(
            base_url="https://provider.example/v1",
            api_key="test-secret",
            model="m",
            max_output_tokens=64,
            timeout_seconds=5,
            provider_name="grok",
            client=client,
        ),
        client,
    )


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128}, (120, 8)),
        ({"prompt_tokens": 5}, (5, None)),
        ({"prompt_tokens": "7", "completion_tokens": True}, (None, None)),
        (None, (None, None)),
    ],
)
def test_openai_compatible_reads_reported_usage_or_leaves_it_unknown(
    usage: object, expected: tuple[int | None, int | None]
) -> None:
    async def run() -> TokenUsage | None:
        payload: dict[str, object] = {"choices": [{"message": {"content": "ok"}}]}
        if usage is not None:
            payload["usage"] = usage
        adapter, client = _adapter(payload)
        result = await adapter.complete(HOLA)
        await client.aclose()
        return result.usage

    found = asyncio.run(run())
    assert found is not None
    assert (found.prompt_tokens, found.completion_tokens) == expected
    assert found.known is (None not in expected)


def test_mock_reports_zero_tokens_as_a_fact() -> None:
    result = asyncio.run(MockLLM().complete(HOLA))
    assert result.usage == TokenUsage(0, 0)


class _StubLLM:
    provider_name = "grok"
    model = "stub-model"

    def __init__(self, text: str, usage: TokenUsage | None) -> None:
        self.text, self.usage = text, usage

    async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
        return LLMResponse(self.text, self.provider_name, self.model, self.usage)

    async def aclose(self) -> None:
        return None


def test_metered_llm_prices_known_usage_and_never_estimates_unknown() -> None:
    pricing = TokenPricing(Decimal("2"), Decimal("10"), "supuesto")
    metrics = InMemoryMetrics()

    async def run() -> None:
        with metric_context(task="S01", step="inicio"):
            await MeteredLLM(
                _StubLLM("x", TokenUsage(1_000_000, 500_000)), metrics, pricing
            ).complete(HOLA)
            await MeteredLLM(_StubLLM("x", None), metrics, pricing).complete(HOLA)

    asyncio.run(run())
    known, unknown = metrics.events
    assert (known.task, known.step, known.stage) == ("S01", "inicio", "llm")
    assert known.usage_known and known.estimated_cost == Decimal("7")
    assert known.cost_unit == "supuesto"
    assert not unknown.usage_known
    assert unknown.prompt_tokens is None and unknown.estimated_cost is None


def test_timed_proxy_records_sync_async_and_failures() -> None:
    class Target:
        value = 3

        def add(self, a: int, b: int) -> int:
            return a + b

        async def slow(self) -> str:
            return "ok"

        def boom(self) -> None:
            raise RuntimeError("fallo")

    metrics = InMemoryMetrics()
    target = timed(Target(), metrics, "catalogo")
    assert target.value == 3 and target.add(1, 2) == 3
    assert asyncio.run(target.slow()) == "ok"
    with pytest.raises(RuntimeError):
        target.boom()
    assert [(e.operation, e.ok) for e in metrics.events] == [
        ("add", True),
        ("slow", True),
        ("boom", False),
    ]
    only = InMemoryMetrics()
    selective = timed(Target(), only, "ejecutor", methods=("add",))
    selective.add(1, 1)
    asyncio.run(selective.slow())
    assert [e.operation for e in only.events] == ["add"]


def test_percentile_and_aggregate_by_task() -> None:
    assert percentile([10, 20, 30, 40], 0.50) == 20
    assert percentile([10, 20, 30, 40], 0.95) == 40
    rows: list[dict[str, object]] = [
        {
            "stage": "llm",
            "task": "S1",
            "duration_ms": 100,
            "usage_known": True,
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "estimated_cost": "0.5",
            "cost_unit": "u",
        },
        {"stage": "llm", "task": "S1", "duration_ms": 300, "usage_known": False},
        {"stage": "turno", "task": "S1", "duration_ms": 50},
        {"stage": "turno", "task": "S2", "duration_ms": 7},
    ]
    report = aggregate(rows)  # type: ignore[arg-type]
    assert report["S1"]["llm_calls"] == 2
    assert report["S1"]["usage_unknown_calls"] == 1
    assert (report["S1"]["prompt_tokens"], report["S1"]["completion_tokens"]) == (10, 2)
    assert report["S1"]["estimated_cost"] == "0.5"
    assert report["S1"]["stages"]["llm"] == {"count": 2, "p50_ms": 100.0, "p95_ms": 300.0}
    assert report["S2"]["llm_calls"] == 0 and report["S2"]["estimated_cost"] is None


def test_pricing_requires_both_rates() -> None:
    assert build_pricing(Settings(llm_provider="mock", _env_file=None)) is None
    settings = Settings(
        llm_provider="mock",
        llm_price_input_per_mtok=Decimal("1"),
        llm_price_output_per_mtok=Decimal("3"),
        _env_file=None,
    )
    pricing = build_pricing(settings)
    assert pricing is not None and pricing.unit == "unidad-no-documentada"


def test_funnel_turn_emits_stages_and_tokens_without_personal_data(tmp_path: Path) -> None:
    secret_text = "quiero algo secreto-del-cliente 3001234567"
    path = tmp_path / "metrics.jsonl"
    settings = Settings(
        llm_provider="mock",
        metrics_path=path,
        llm_price_input_per_mtok=Decimal("1"),
        llm_price_output_per_mtok=Decimal("2"),
        _env_file=None,
    )

    async def run() -> None:
        llm = _StubLLM('{"choice":"start:products"}', TokenUsage(200, 10))
        container = build_container(settings, llm=llm, metrics=JsonlMetrics(path))
        try:
            with metric_context(task="S99"):
                reply = await container.agent.respond_reply(secret_text, conversation_key="k-1")
            assert reply.step == "producto"
        finally:
            await container.aclose()

    asyncio.run(run())
    lines = path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    stages = {event["stage"] for event in events}
    assert {"llm", "turno"} <= stages
    llm_event = next(event for event in events if event["stage"] == "llm")
    assert llm_event["task"] == "S99" and llm_event["step"] == "inicio"
    assert (llm_event["prompt_tokens"], llm_event["completion_tokens"]) == (200, 10)
    assert Decimal(llm_event["estimated_cost"]) == Decimal("0.00022")
    blob = "\n".join(lines)
    assert "secreto-del-cliente" not in blob and "3001234567" not in blob and "k-1" not in blob


def test_catalog_and_stock_stages_are_timed() -> None:
    metrics = InMemoryMetrics()
    container = build_container(Settings(llm_provider="mock", _env_file=None), metrics=metrics)
    container.catalog.search_candidates("cemento")
    container.inventory.list_snapshots("CEM-50")
    assert {(event.stage, event.operation) for event in metrics.events} >= {
        ("catalogo", "search_candidates"),
        ("inventario", "list_snapshots"),
    }

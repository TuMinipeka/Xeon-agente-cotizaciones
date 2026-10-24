from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest

from evals.runner import CallBudget, _network_guard, run
from evals.sut import XEONSUT
from xeon.adapters.llm.mock import MockLLM
from xeon.application.ports.llm import ChatMessage, LLMResponse


def test_concurrent_cases_are_isolated_ordered_and_report_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    active = 0
    peak = 0
    llms: list[SlowMockLLM] = []
    instances: list[tuple[int, int, int]] = []

    class SlowMockLLM(MockLLM):
        def __init__(self, delay: float) -> None:
            self.delay = delay
            self.calls = 0

        async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(self.delay)
                self.calls += 1
                return await super().complete(messages)
            finally:
                active -= 1

    def build_slow(_settings: object) -> SlowMockLLM:
        llm = SlowMockLLM(0.03 if len(llms) == 0 else 0.005)
        llms.append(llm)
        return llm

    class TrackingSUT(XEONSUT):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)  # type: ignore[arg-type]
            instances.append(
                (id(self.container), id(self.container.conversation_memory), id(self.quotes))
            )

    monkeypatch.setattr("evals.sut.build_llm", build_slow)
    monkeypatch.setattr("evals.runner.XEONSUT", TrackingSUT)
    report, _ = asyncio.run(
        run(
            ids=["S02", "S01"],
            reps=2,
            max_calls=20,
            concurrency=4,
            mode="offline",
            output_root=tmp_path,
        )
    )
    assert peak > 1
    assert len(set(instances)) == 4
    assert len(llms) == 4 and all(llm.calls == 2 for llm in llms)
    assert [(case["id"], case["rep"]) for case in report["cases"]] == [
        ("S01", 1),
        ("S01", 2),
        ("S02", 1),
        ("S02", 2),
    ]
    assert all(case["status"] == "PASS" for case in report["cases"])
    assert "S01 rep=1 PASS calls=" in capsys.readouterr().out


def test_concurrent_global_budget_is_hard_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class SlowMockLLM(MockLLM):
        async def complete(self, messages: Sequence[ChatMessage]) -> LLMResponse:
            await asyncio.sleep(0.01)
            return await super().complete(messages)

    monkeypatch.setattr("evals.sut.build_llm", lambda _settings: SlowMockLLM())
    report, _ = asyncio.run(
        run(
            ids=["S01", "S02"],
            reps=3,
            max_calls=3,
            concurrency=6,
            mode="offline",
            output_root=tmp_path,
        )
    )
    assert report["calls"] == 3
    assert len(report["cases"]) == 6
    assert all(case["status"] == "ERROR" and case["origin"] == "infra" for case in report["cases"])
    assert [(case["id"], case["rep"]) for case in report["cases"]] == [
        ("S01", 1),
        ("S01", 2),
        ("S01", 3),
        ("S02", 1),
        ("S02", 2),
        ("S02", 3),
    ]


def test_gateway_429_retries_once_without_network() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429 if attempts == 1 else 200)

    async def exercise() -> None:
        budget = CallBudget(2)
        budget.count()
        with _network_guard("live", budget, instrument_live=False):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                response = await client.get("https://api.reto.pltk.mx/v1/test")
        assert response.status_code == 200
        assert budget.used == 2

    asyncio.run(exercise())
    assert attempts == 2


def test_gateway_timeout_retries_once_and_respects_budget() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("simulated", request=request)

    async def exercise() -> None:
        budget = CallBudget(2)
        budget.count()
        with _network_guard("live", budget, instrument_live=False):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with pytest.raises(httpx.ReadTimeout):
                    await client.get("https://api.reto.pltk.mx/v1/test")
        assert budget.used == 2

    asyncio.run(exercise())
    assert attempts == 2


def test_offline_runner_isolated_and_reported(tmp_path: Path) -> None:
    report, path = asyncio.run(
        run(ids=["S01"], reps=2, max_calls=20, mode="offline", output_root=tmp_path)
    )
    assert len(report["cases"]) == 2
    assert all(case["id"] == "S01" for case in report["cases"])
    assert report["calls"] >= 2
    assert path.joinpath("report.json").exists()
    stored = json.loads(path.joinpath("report.json").read_text(encoding="utf-8"))
    assert stored["provenance"]["seed"]
    assert stored["cases"][0]["evidence"]["drafts"]
    assert "Eres XEON, un asistente comercial" not in path.joinpath("report.json").read_text(
        encoding="utf-8"
    )


def test_call_budget_aborts_cleanly(tmp_path: Path) -> None:
    report, _ = asyncio.run(
        run(ids=["S01"], reps=2, max_calls=1, mode="offline", output_root=tmp_path)
    )
    assert report["calls"] == 1
    assert [case["status"] for case in report["cases"]] == ["ERROR", "ERROR"]
    assert all(case["origin"] == "infra" for case in report["cases"])
    assert report["cases"][-1]["origin"] == "infra"


def test_fixture_drift_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def changed_seed() -> None:
        raise RuntimeError("seed drift")

    monkeypatch.setattr("evals.runner.export", changed_seed)
    report, path = asyncio.run(
        run(ids=["S01"], reps=1, max_calls=10, mode="offline", output_root=tmp_path)
    )
    assert report["cases"][0]["status"] == "ERROR"
    assert report["cases"][0]["origin"] == "fixture"
    assert path.joinpath("report.json").exists()

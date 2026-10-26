from __future__ import annotations

import asyncio
import inspect
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest

from evals.judge import JUDGE_TIMEOUT_RETRY, build_judge
from evals.report import append_case, resume_report, write_manifest
from evals.runner import CallBudget, _network_guard, main, run
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

    from evals import runner as runner_module

    original_offline = runner_module._offline

    async def slow_journey(*args: object, **kwargs: object) -> object:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.02)
            return await original_offline(*args, **kwargs)  # type: ignore[arg-type]
        finally:
            active -= 1

    monkeypatch.setattr("evals.runner._offline", slow_journey)
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
    assert len(llms) == 4 and all(llm.calls == 0 for llm in llms)
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
    del tmp_path, monkeypatch
    budget = CallBudget(3)
    for _ in range(3):
        budget.count()
    assert budget.used == 3 and budget.reached
    with pytest.raises(Exception, match="tope de llamadas"):
        budget.count()


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


def test_judge_timeout_retries_once_and_counts_each_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    pytest.importorskip("litellm", reason="requiere el grupo evals")
    from litellm.exceptions import Timeout

    judge = build_judge(
        ["Responder con claridad"],
        model="openai/grok-4.6",
        api_base="https://api.reto.pltk.mx/v1",
        api_key="fake",
    )
    assert judge._extra_params["timeout"] == 120
    budget = CallBudget(2)
    calls = 0

    def failing_completion(**_kwargs: object) -> str:
        nonlocal calls
        budget.count()
        calls += 1
        if calls == 1:
            raise Timeout(message="simulated", model="grok-4.6", llm_provider="openai")
        return "judged"

    monkeypatch.setattr(judge._provider_compat, "completion", failing_completion)
    monkeypatch.setattr("evals.judge.time.sleep", lambda _seconds: None)
    assert judge._completion() == "judged"
    assert calls == budget.used == 2
    assert JUDGE_TIMEOUT_RETRY.get() is False


def test_judge_does_not_retry_non_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    pytest.importorskip("litellm", reason="requiere el grupo evals")
    judge = build_judge(
        ["Responder con claridad"],
        model="openai/grok-4.6",
        api_base="https://api.reto.pltk.mx/v1",
        api_key="fake",
    )
    calls = 0

    def failing_completion(**_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise ValueError("simulated")

    monkeypatch.setattr(judge._provider_compat, "completion", failing_completion)
    with pytest.raises(ValueError, match="simulated"):
        judge._completion()
    assert calls == 1


def test_judge_timeout_has_no_nested_transport_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("simulated", request=request)

    async def exercise() -> None:
        budget = CallBudget(2)
        budget.count()
        token = JUDGE_TIMEOUT_RETRY.set(True)
        try:
            with _network_guard("live", budget, instrument_live=False):
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    with pytest.raises(httpx.ReadTimeout):
                        await client.get("https://api.reto.pltk.mx/v1/test")
        finally:
            JUDGE_TIMEOUT_RETRY.reset(token)
        assert budget.used == 1

    asyncio.run(exercise())
    assert attempts == 1


def test_offline_runner_isolated_and_reported(tmp_path: Path) -> None:
    report, path = asyncio.run(
        run(ids=["S01"], reps=2, max_calls=20, mode="offline", output_root=tmp_path)
    )
    assert len(report["cases"]) == 2
    assert all(case["id"] == "S01" for case in report["cases"])
    assert report["calls"] == 0
    assert path.joinpath("report.json").exists()
    journal = path.joinpath("cases.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(journal) == 2
    # Cases finish concurrently; the journal records completion order, not rep order.
    assert sorted(json.loads(line)["case"]["rep"] for line in journal) == [1, 2]
    stored = json.loads(path.joinpath("report.json").read_text(encoding="utf-8"))
    assert stored["provenance"]["seed"]
    assert stored["cases"][0]["evidence"]["drafts"]
    assert "Eres XEON, un asistente comercial" not in path.joinpath("report.json").read_text(
        encoding="utf-8"
    )
    path.joinpath("report.json").unlink()
    path.joinpath("report.md").unlink()
    recovered = resume_report(path)
    assert recovered["recovered_from_journal"] is True
    assert [case["status"] for case in recovered["cases"]] == ["PASS", "PASS"]
    assert path.joinpath("report.json").exists()


def test_interrupted_journal_recovers_finished_case_and_marks_missing_infra(tmp_path: Path) -> None:
    write_manifest(
        tmp_path,
        {
            "fingerprint": "interrupted",
            "provenance": {"seed": "test", "scenarios": ["S01"]},
            "mode": "offline",
            "max_calls": 10,
            "jobs": [
                {"id": "S01", "rep": 1, "severity": "high"},
                {"id": "S01", "rep": 2, "severity": "high"},
            ],
        },
    )
    append_case(
        tmp_path,
        {
            "id": "S01",
            "rep": 1,
            "status": "PASS",
            "origin": "agent",
            "severity": "high",
            "checks": [],
            "transcript": [],
        },
        2,
    )
    with tmp_path.joinpath("cases.jsonl").open("a", encoding="utf-8") as journal:
        journal.write('{"case":')
    report = resume_report(tmp_path)
    assert report["calls"] == 2
    assert [case["status"] for case in report["cases"]] == ["PASS", "ERROR"]
    assert report["cases"][1]["origin"] == "infra"
    assert tmp_path.joinpath("report.md").exists()


def test_resume_report_cli_never_starts_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_manifest(
        tmp_path,
        {
            "fingerprint": "resume-cli",
            "provenance": {"seed": "test", "scenarios": ["S01"]},
            "mode": "offline",
            "max_calls": 10,
            "jobs": [{"id": "S01", "rep": 1, "severity": "high"}],
        },
    )
    monkeypatch.setattr(sys, "argv", ["evals.runner", "--resume-report", str(tmp_path)])
    assert main() == 2
    assert inspect.signature(run).parameters["concurrency"].default == 3


def test_unparseable_amount_is_evaluator_error_without_stalling_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MalformedAmountSUT(XEONSUT):
        async def respond(self, message: str) -> dict[str, object]:
            response = await super().respond(message)
            response["reply"] = "Total $2.00.000"
            return response

    monkeypatch.setattr("evals.runner.XEONSUT", MalformedAmountSUT)
    report, _ = asyncio.run(
        run(ids=["S01"], reps=1, max_calls=10, mode="offline", output_root=tmp_path)
    )
    case = report["cases"][0]
    assert case["status"] == "ERROR"
    assert case["origin"] == "evaluator"
    assert any(
        check["name"] == "no_invented_amounts" and "2.00.000" in check["evidence"]
        for check in case["checks"]
    )


def test_local_journey_needs_no_paid_call_budget(tmp_path: Path) -> None:
    report, _ = asyncio.run(
        run(ids=["S01"], reps=2, max_calls=1, mode="offline", output_root=tmp_path)
    )
    assert report["calls"] == 0
    assert [case["status"] for case in report["cases"]] == ["PASS", "PASS"]


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


def test_offline_report_saves_observability_with_zero_tokens(tmp_path: Path) -> None:
    report, path = asyncio.run(
        run(
            ids=["S01"],
            reps=1,
            max_calls=5,
            concurrency=1,
            mode="offline",
            output_root=tmp_path,
        )
    )
    row = report["observability"]["S01"]
    assert row["llm_calls"] == 0
    assert (row["prompt_tokens"], row["completion_tokens"]) == (0, 0)
    assert {"turno", "ejecutor"} <= set(row["stages"])
    assert report["cases"][0]["observability"] == row
    assert (path / "observability.jsonl").read_text(encoding="utf-8").strip()

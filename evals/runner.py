"""Run isolated XEON conversation evaluations: python -m evals.runner."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import httpx
import yaml

from evals.checks import EvalView, run_check
from evals.judge import JUDGE_TIMEOUT_RETRY, build_judge, semantic_verdict
from evals.reference.oracle import FIXTURES, FixtureMismatch, Oracle
from evals.report import (
    append_case,
    append_observability,
    metrics,
    resume_report,
    write_manifest,
    write_report,
)
from evals.sut import XEONSUT
from scripts.export_eval_fixtures import export
from xeon.adapters.metrics import event_to_json
from xeon.application.observability import aggregate, metric_context
from xeon.config import Settings

ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ROOT / "evals" / "scenarios" / "personas"
CHECKS = ROOT / "evals" / "scenarios" / "checks"
JOURNEYS = ROOT / "evals" / "scenarios" / "journeys.yaml"
MODEL = "openai/grok-4.6"
BASE_URL = "https://api.reto.pltk.mx/v1"

_SECRET_RE = re.compile(
    r"(pk_|xai-|sk-)[A-Za-z0-9_\-]{8,}|(Bearer|api[_-]?key)\s*[:=]?\s*\S+", re.I
)


def _safe_error(exc: BaseException) -> str:
    return _SECRET_RE.sub("<redactado>", str(exc))[:300]


class BudgetExceeded(RuntimeError):
    pass


class CallBudget:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.used = 0
        self.exhausted = False
        self._lock = Lock()

    def count(self) -> None:
        with self._lock:
            if self.used >= self.maximum:
                self.exhausted = True
                raise BudgetExceeded("Se alcanzo el tope de llamadas de la corrida.")
            self.used += 1

    @property
    def reached(self) -> bool:
        with self._lock:
            return self.used >= self.maximum


@contextmanager
def _network_guard(mode: str, budget: CallBudget, *, instrument_live: bool = True) -> Any:
    original_sync_send = httpx.Client.send
    original_async_send = httpx.AsyncClient.send
    original_completion: Any = None
    litellm: Any = None
    previous_cost_map = os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP")
    if mode == "live" and instrument_live:
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
        os.environ.pop("LANGWATCH_API_KEY", None)
        import litellm as litellm_module
        import scenario

        litellm = litellm_module
        original_completion = litellm.completion
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
        scenario.setup_scenario_tracing(instrumentors=[], span_processors=[], trace_exporter=None)

    def permitted(client: httpx.Client | httpx.AsyncClient, request: httpx.Request) -> bool:
        if isinstance(client, httpx.AsyncClient) and isinstance(
            client._transport, httpx.ASGITransport
        ):
            return True
        return mode == "live" and request.url.host == "api.reto.pltk.mx"

    def guarded_sync_send(
        client: httpx.Client, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        if not permitted(client, request):
            raise RuntimeError("La guarda de red bloqueo un destino externo.")
        for attempt in range(2):
            if attempt:
                budget.count()
            try:
                response = original_sync_send(client, request, **kwargs)
            except httpx.TimeoutException:
                if attempt or JUDGE_TIMEOUT_RETRY.get():
                    raise
            else:
                if response.status_code != 429 or attempt:
                    return response
                response.close()
            time.sleep(0.2)
        raise AssertionError("Reintento de gateway inalcanzable.")

    async def guarded_async_send(
        client: httpx.AsyncClient, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        if not permitted(client, request):
            raise RuntimeError("La guarda de red bloqueo un destino externo.")
        if isinstance(client._transport, httpx.ASGITransport):
            return await original_async_send(client, request, **kwargs)
        for attempt in range(2):
            if attempt:
                budget.count()
            try:
                response = await original_async_send(client, request, **kwargs)
            except httpx.TimeoutException:
                if attempt or JUDGE_TIMEOUT_RETRY.get():
                    raise
            else:
                if response.status_code != 429 or attempt:
                    return response
                await response.aclose()
            await asyncio.sleep(0.2)
        raise AssertionError("Reintento de gateway inalcanzable.")

    def counted_completion(*args: Any, **kwargs: Any) -> Any:
        budget.count()
        return original_completion(*args, **kwargs)

    httpx.Client.send = guarded_sync_send  # type: ignore[method-assign, assignment]
    httpx.AsyncClient.send = guarded_async_send  # type: ignore[method-assign, assignment]
    if litellm is not None:
        litellm.completion = counted_completion
    try:
        yield
    finally:
        httpx.Client.send = original_sync_send  # type: ignore[method-assign]
        httpx.AsyncClient.send = original_async_send  # type: ignore[method-assign]
        if litellm is not None:
            litellm.completion = original_completion
        if mode == "live" and instrument_live:
            if previous_cost_map is None:
                os.environ.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
            else:
                os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = previous_cost_map


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except OSError, subprocess.CalledProcessError:
        return "unknown"


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"YAML invalido: {path.name}")
    return value


def _select(raw: str) -> list[str]:
    if raw == "all":
        return [path.stem for path in sorted(PERSONAS.glob("S*.yaml"))]
    selected = [item.strip().upper() for item in raw.split(",") if item.strip()]
    if not selected or any(not item.startswith("S") or not item[1:].isdigit() for item in selected):
        raise ValueError("--scenarios requiere IDs S01..S22 separados por coma o all.")
    return selected


def _fingerprint(ids: list[str], oracle: Oracle, mode: str) -> tuple[str, dict[str, Any]]:
    details = {
        "commit": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "scenarios": ids,
        "model": "grok-4.6" if mode == "live" else "mock-xeon-v1",
        "seed": oracle.fingerprint,
        "started_at": datetime.now(UTC).isoformat(),
    }
    value = hashlib.sha256(json.dumps(details, sort_keys=True).encode()).hexdigest()[:16]
    return value, details


async def _offline(
    sut: XEONSUT, persona: dict[str, Any], canary: str | None
) -> tuple[list[str], list[dict[str, Any]], tuple[str, ...]]:
    journey = _load(JOURNEYS)[str(persona["id"])]
    messages: list[str] = [str(persona["first_message"])]
    expected_steps: list[str] = [str(journey["first_step"])]
    if canary:
        canary_response = await sut.client.post(
            "/v1/chat",
            json={"message": f"Necesito cemento. {canary}", "conversation_id": str(uuid4())},
        )
        canary_response.raise_for_status()
    responses = [await sut.respond(messages[0])]
    for action in journey["actions"]:
        if not isinstance(action, list) or len(action) != 3:
            raise ValueError("Accion de recorrido guiado invalida.")
        kind, raw_value, step = action
        kind = str(kind)
        value = str(raw_value)
        step = str(step)
        if kind == "click":
            turn_response = await sut.click(raw_value if isinstance(raw_value, int) else value)
        elif kind == "text":
            turn_response = await sut.respond(value)
        else:
            raise ValueError("Accion de recorrido desconocida.")
        messages.append(value)
        responses.append(turn_response)
        expected_steps.append(step)
    return messages, responses, tuple(expected_steps)


async def _live(
    sut: XEONSUT,
    persona: dict[str, Any],
    criteria: list[str],
    api_key: str,
    canary: str | None,
) -> tuple[list[str], list[dict[str, Any]], dict[str, str]]:
    import scenario

    user_messages: list[str] = []
    responses: list[dict[str, Any]] = []

    class SUTAdapter(scenario.AgentAdapter):  # type: ignore[misc]
        async def call(self, input: Any) -> str:
            message = str(input.last_new_user_message_str())
            user_messages.append(message)
            response = await sut.respond(message)
            responses.append(response)
            return str(response["reply"])

    simulator = scenario.UserSimulatorAgent(
        model=MODEL,
        api_base=BASE_URL,
        api_key=api_key,
        max_tokens=128,
        num_retries=0,
        timeout=30,
        persona="\n".join(
            (
                str(persona["persona"]),
                str(persona["goal"]),
                *[str(item) for item in persona["behaviors"]],
                "Cuando XEON ofrezca opciones, pulsa una enviando su id exacto o su numero. "
                "Sigue el embudo antes de pedir el resumen; no inventes opciones.",
            )
        ),
    )
    simulator._provider_compat._adaptations.add("drop_temperature")
    judge = build_judge(criteria, model=MODEL, api_base=BASE_URL, api_key=api_key)
    if canary:
        response = await sut.client.post(
            "/v1/chat",
            json={"message": f"Necesito cemento. {canary}", "conversation_id": str(uuid4())},
        )
        response.raise_for_status()
    turns = min(8, int(persona.get("max_turns", 8)))
    script = [step for _ in range(turns) for step in (scenario.user(), scenario.agent())]
    script.append(scenario.judge())
    result = await scenario.arun(
        name=str(persona["id"]),
        description=str(persona["goal"]),
        agents=[SUTAdapter(), simulator, judge],
        script=script,
        max_turns=turns,
        verbose=False,
        fetch_remote_traces=False,
    )
    confidence = 0.0 if result.inconclusive_criteria else 1.0 if result.failed_criteria else None
    verdict = semantic_verdict(bool(result.success), str(result.reasoning), confidence=confidence)
    return user_messages, responses, verdict


async def run(
    *,
    ids: list[str],
    reps: int,
    max_calls: int,
    mode: str,
    concurrency: int = 3,
    output_root: Path = ROOT / "reports" / "evals",
) -> tuple[dict[str, Any], Path]:
    if reps < 1 or not 1 <= max_calls <= 600 or concurrency < 1:
        raise ValueError("--reps y --concurrency deben ser positivos; --max-calls entre 1 y 600.")
    try:
        export()
        oracle = Oracle(FIXTURES)
    except (RuntimeError, OSError) as exc:
        fingerprint = hashlib.sha256(
            f"fixture-error:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:16]
        fixture_cases = [
            {
                "id": scenario_id,
                "rep": rep,
                "status": "ERROR",
                "origin": "fixture",
                "severity": "blocker",
                "evidence": type(exc).__name__,
                "checks": [],
                "transcript": [],
            }
            for scenario_id in ids
            for rep in range(1, reps + 1)
        ]
        report = {
            "fingerprint": fingerprint,
            "mode": mode,
            "calls": 0,
            "max_calls": max_calls,
            "cases": fixture_cases,
            "metrics": metrics(fixture_cases),
            "provenance": {"seed": "unverified", "scenarios": ids},
        }
        path = output_root / fingerprint
        write_manifest(
            path,
            {
                "fingerprint": fingerprint,
                "provenance": report["provenance"],
                "mode": mode,
                "max_calls": max_calls,
                "jobs": [
                    {"id": case["id"], "rep": case["rep"], "severity": case["severity"]}
                    for case in fixture_cases
                ],
            },
        )
        for case in fixture_cases:
            append_case(path, case, 0)
        write_report(path, report)
        return report, path
    fingerprint, provenance = _fingerprint(ids, oracle, mode)
    budget = CallBudget(max_calls)
    cases: list[dict[str, Any]] = []
    api_key = ""
    if mode == "live":
        api_key = Settings().require_grok_api_key().get_secret_value()
    jobs: list[tuple[str, int, dict[str, Any], dict[str, Any]]] = []
    for scenario_id in sorted(ids):
        persona = _load(PERSONAS / f"{scenario_id}.yaml")
        checks = _load(CHECKS / f"{scenario_id}.yaml")
        if persona.get("id") != scenario_id or checks.get("id") != scenario_id:
            raise ValueError(f"IDs de persona y checks no coinciden: {scenario_id}")
        for rep in range(1, reps + 1):
            jobs.append((scenario_id, rep, persona, checks))

    path = output_root / fingerprint
    write_manifest(
        path,
        {
            "fingerprint": fingerprint,
            "provenance": provenance,
            "mode": mode,
            "max_calls": max_calls,
            "jobs": [
                {"id": scenario_id, "rep": rep, "severity": checks["severity"]}
                for scenario_id, rep, _, checks in jobs
            ],
        },
    )

    semaphore = asyncio.Semaphore(concurrency)

    observed: list[dict[str, Any]] = []

    async def process_case(
        scenario_id: str, rep: int, persona: dict[str, Any], checks: dict[str, Any]
    ) -> dict[str, Any]:
        with metric_context(task=scenario_id):
            return await run_case(scenario_id, rep, persona, checks)

    async def run_case(
        scenario_id: str, rep: int, persona: dict[str, Any], checks: dict[str, Any]
    ) -> dict[str, Any]:
        async with semaphore:
            if budget.reached:
                case = {
                    "id": scenario_id,
                    "rep": rep,
                    "status": "ERROR",
                    "origin": "infra",
                    "severity": checks["severity"],
                    "evidence": "Tope de llamadas agotado.",
                    "checks": [],
                    "transcript": [],
                }
            else:
                sut: XEONSUT | None = None
                try:
                    settings = Settings(  # type: ignore[call-arg]
                        _env_file=None,
                        llm_provider="mock" if mode == "offline" else "grok",
                        grok_model="grok-4.6",
                        whatsapp_send_enabled=False,
                        xeon_api_auth_disabled=True,  # in-process harness, no network exposure
                    )
                    sut = XEONSUT(settings, on_llm_call=budget.count)
                    canary = (
                        f"canario-otra-conversacion-{uuid4().hex}" if scenario_id == "S11" else None
                    )
                    if mode == "offline":
                        messages, responses, expected_steps = await _offline(sut, persona, canary)
                        judge_verdict = None
                    else:
                        messages, responses, judge_verdict = await _live(
                            sut, persona, list(checks.get("judge", [])), api_key, canary
                        )
                        expected_steps = ()
                    view = EvalView(
                        oracle,
                        responses,
                        sut.llm.tool_contexts(),
                        sut.drafts(),
                        mode,
                        messages,
                        canary,
                        expected_steps,
                    )
                    required_checks = [
                        {"type": "step_flow"},
                        {"type": "options_offered"},
                        {"type": "no_freeform_solution"},
                    ]
                    if scenario_id == "S21":
                        required_checks.append({"type": "confirmation_state"})
                    results = [
                        run_check(spec, view) for spec in [*checks["checks"], *required_checks]
                    ]
                    status = (
                        "ERROR"
                        if any(item.status == "ERROR" for item in results)
                        else "FAIL"
                        if any(item.status == "FAIL" for item in results)
                        else "PASS"
                    )
                    origin = "evaluator" if status == "ERROR" else "agent"
                    if judge_verdict and judge_verdict["status"] == "FAIL" and status == "PASS":
                        status = "FAIL"
                    case = {
                        "id": scenario_id,
                        "rep": rep,
                        "status": status,
                        "origin": origin,
                        "severity": checks["severity"],
                        "category": checks["category"],
                        "checks": [asdict(item) for item in results],
                        "judge": judge_verdict,
                        "transcript": [
                            {"user": message, "assistant": response.get("reply", "")}
                            for message, response in zip(messages, responses, strict=False)
                        ],
                        "expected": [item.expected for item in results if item.expected],
                        "obtained": [item.actual for item in results if item.actual],
                        "evidence": {
                            "tool_contexts": sut.llm.tool_contexts(),
                            "drafts": sut.drafts(),
                            "token_estimate": sut.llm.token_estimate,
                        },
                        "observability": aggregate(sut.metrics.events).get(scenario_id, {}),
                    }
                except Exception as exc:
                    case = {
                        "id": scenario_id,
                        "rep": rep,
                        "status": "ERROR",
                        "origin": "infra",
                        "severity": checks["severity"],
                        "evidence": (
                            f"{type(exc).__name__}: {_safe_error(exc)}; llamada={budget.used}"
                        ),
                        "checks": [],
                        "transcript": [],
                    }
                finally:
                    if sut is not None:
                        rows = [event_to_json(event) for event in sut.metrics.events]
                        append_observability(path, rows)
                        observed.extend(rows)
                        await sut.aclose()
            append_case(path, case, budget.used)
            print(f"{scenario_id} rep={rep} {case['status']} calls={budget.used}", flush=True)
            return case

    with _network_guard(mode, budget):
        cases = list(await asyncio.gather(*(process_case(*job) for job in jobs)))
    cases.sort(key=lambda case: (case["id"], case["rep"]))
    report = {
        "fingerprint": fingerprint,
        "provenance": provenance,
        "mode": mode,
        "calls": budget.used,
        "max_calls": max_calls,
        "cases": cases,
        "metrics": metrics(cases),
        "observability": aggregate(observed),
    }
    write_report(path, report)
    return report, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default="all")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--max-calls", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--mode", choices=("live", "offline"), default="offline")
    parser.add_argument("--resume-report", type=Path)
    args = parser.parse_args()
    if args.mode == "offline":
        os.environ["LLM_PROVIDER"] = "mock"
    os.environ["WHATSAPP_SEND_ENABLED"] = "false"
    os.environ.pop("LANGWATCH_API_KEY", None)
    try:
        if args.resume_report is not None:
            path = args.resume_report
            report = resume_report(path)
        else:
            report, path = asyncio.run(
                run(
                    ids=_select(args.scenarios),
                    reps=args.reps,
                    max_calls=args.max_calls,
                    mode=args.mode,
                    concurrency=args.concurrency,
                )
            )
    except (ValueError, FixtureMismatch, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Evaluacion no iniciada: {type(exc).__name__}.\n")
    counts = {
        status: sum(case["status"] == status for case in report["cases"])
        for status in ("PASS", "FAIL", "ERROR")
    }
    print(f"{path} PASS={counts['PASS']} FAIL={counts['FAIL']} ERROR={counts['ERROR']}")
    return 2 if counts["ERROR"] else 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

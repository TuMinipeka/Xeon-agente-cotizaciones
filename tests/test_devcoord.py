from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from xeon.devcoord.contracts import (
    AcceptanceResult,
    AgentCheckResult,
    NextDirective,
    QualityDecision,
    QualityReview,
    WorkerReport,
    WorkOrder,
)
from xeon.devcoord.coordinator import AgenticCoordinator, CommandResult, SubprocessCommandRunner
from xeon.devcoord.gates import evaluate_worker_evidence


def _work_order() -> WorkOrder:
    return WorkOrder(
        work_order_id="HU-001-run",
        story_id="HU-001",
        title="Crear una cotizacion sintetica",
        objective="Completar una sola historia sin cambiar reglas comerciales.",
        acceptance_criteria=({"id": "AC-1", "text": "Crear un borrador con SKU exacto."},),
        allowed_paths=("src/xeon/**", "tests/**", "docs/**", "README.md"),
        required_checks=("ruff_check", "mypy", "pytest"),
    )


def _verified_checks() -> tuple[AgentCheckResult, ...]:
    return (
        AgentCheckResult(check="ruff_check", exit_code=0, summary="passed"),
        AgentCheckResult(check="ruff_format", exit_code=0, summary="passed"),
        AgentCheckResult(check="mypy", exit_code=0, summary="passed"),
        AgentCheckResult(check="pytest", exit_code=0, summary="passed"),
    )


def _worker_report(*, business_rule_changes: tuple[str, ...] = ()) -> WorkerReport:
    return WorkerReport(
        work_order_id="HU-001-run",
        story_id="HU-001",
        iteration=1,
        status="completed",
        summary="Se implemento la historia.",
        changed_files=("src/xeon/application/quote_draft.py", "tests/test_quote_draft.py"),
        commits=(
            {
                "sha": "abc1234",
                "message": "Feat: :sparkles: CompleteSyntheticQuote",
            },
        ),
        acceptance_results=(
            AcceptanceResult(criterion_id="AC-1", status="passed", evidence="pytest: pass"),
        ),
        reported_checks=(AgentCheckResult(check="pytest", exit_code=0, summary="1 passed"),),
        business_rule_changes=business_rule_changes,
    )


def test_gate_approves_complete_evidence_from_allowed_paths() -> None:
    findings = evaluate_worker_evidence(
        _work_order(),
        _worker_report(),
        actual_changed_files=(
            "src/xeon/application/quote_draft.py",
            "tests/test_quote_draft.py",
        ),
        actual_commit_messages=("Feat: :sparkles: CompleteSyntheticQuote",),
        verified_checks=_verified_checks(),
        worktree_clean=True,
    )

    assert findings == ()


def test_gate_blocks_declared_business_rule_change() -> None:
    findings = evaluate_worker_evidence(
        _work_order(),
        _worker_report(business_rule_changes=("Cambiar el redondeo monetario.",)),
        actual_changed_files=("src/xeon/domain/money.py",),
        actual_commit_messages=("Feat: :sparkles: ChangeMoneyRounding",),
        verified_checks=_verified_checks(),
        worktree_clean=True,
    )

    assert any(item.code == "business_rule_change_requires_human" for item in findings)
    assert any(item.blocking for item in findings)


def test_gate_rejects_paths_outside_work_order() -> None:
    findings = evaluate_worker_evidence(
        _work_order(),
        _worker_report(),
        actual_changed_files=("compose.yaml",),
        actual_commit_messages=("Feat: :sparkles: CompleteSyntheticQuote",),
        verified_checks=_verified_checks(),
        worktree_clean=True,
    )

    assert any(item.code == "changed_path_not_allowed" and item.blocking for item in findings)


def test_gate_blocks_secret_and_env_paths() -> None:
    findings = evaluate_worker_evidence(
        _work_order(),
        _worker_report(),
        actual_changed_files=("secrets/reto_key.txt", ".env"),
        actual_commit_messages=("Feat: :sparkles: CompleteSyntheticQuote",),
        verified_checks=_verified_checks(),
        worktree_clean=True,
    )

    assert {item.code for item in findings if item.blocking} >= {"forbidden_secret_path"}


def test_gate_blocks_report_from_another_iteration() -> None:
    findings = evaluate_worker_evidence(
        _work_order(),
        _worker_report().model_copy(update={"iteration": 2}),
        expected_iteration=1,
        actual_changed_files=(
            "src/xeon/application/quote_draft.py",
            "tests/test_quote_draft.py",
        ),
        actual_commit_messages=("Feat: :sparkles: CompleteSyntheticQuote",),
        verified_checks=_verified_checks(),
        worktree_clean=True,
    )

    assert any(item.code == "report_iteration_mismatch" for item in findings)
    assert any(item.blocking for item in findings)


def test_next_directive_contains_only_review_actions() -> None:
    review = QualityReview(
        work_order_id="HU-001-run",
        story_id="HU-001",
        iteration=1,
        decision=QualityDecision.CHANGES_REQUESTED,
        summary="La evidencia no cubre un criterio.",
        required_actions=("Agrega una prueba de integracion para AC-1.",),
    )

    directive = NextDirective.from_review(review)

    assert directive.next_iteration == 2
    assert directive.actions == review.required_actions
    assert directive.constraints == (
        "No ampliar el alcance de la orden.",
        "No modificar reglas de negocio sin autorizacion humana.",
    )


@pytest.mark.skipif(os.name != "nt", reason="Regression exclusiva de shims npm en Windows")
def test_command_runner_resolves_kilo_cmd_without_enabling_a_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kilo_shim = tmp_path / "kilo.CMD"
    kilo_shim.write_text("@exit /b 99\n", encoding="utf-8")
    kilo_entry = tmp_path / "node_modules" / "@kilocode" / "cli" / "bin" / "kilo"
    kilo_entry.parent.mkdir(parents=True)
    kilo_entry.write_text(
        "import sys\nprint(sys.argv[1])\n",
        encoding="utf-8",
    )
    original_which = shutil.which

    def fake_which(command: str) -> str | None:
        if command == "kilo":
            return str(kilo_shim)
        if command in {"node", "node.exe"}:
            return sys.executable
        return original_which(command)

    monkeypatch.setattr(shutil, "which", fake_which)

    result = SubprocessCommandRunner().run(("kilo", "safe&literal"), cwd=tmp_path)

    assert result.exit_code == 0
    assert result.stdout.strip() == "safe&literal"


def test_command_runner_decodes_utf8_independent_of_windows_code_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")

    result = SubprocessCommandRunner().run(
        (
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(bytes((0xCF, 0x8F)))",
        ),
        cwd=tmp_path,
    )

    assert result.exit_code == 0
    assert result.stdout == "Ϗ"


@pytest.mark.skipif(os.name != "nt", reason="Fallback exclusivo de Codex Desktop en Windows")
def test_command_runner_finds_codex_desktop_outside_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_executable = tmp_path / "OpenAI" / "Codex" / "bin" / "build-id" / "codex.exe"
    codex_executable.parent.mkdir(parents=True)
    codex_executable.touch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    original_which = shutil.which

    def fake_which(command: str) -> str | None:
        if command == "codex":
            return None
        return original_which(command)

    captured: dict[str, tuple[str, ...]] = {}

    def fake_run(argv: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "codex-cli test", "")

    monkeypatch.setattr(shutil, "which", fake_which)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = SubprocessCommandRunner().run(("codex", "--version"), cwd=tmp_path)

    assert result.exit_code == 0
    assert captured["argv"] == (str(codex_executable), "--version")


class _FakeRunner:
    def __init__(
        self,
        report: WorkerReport,
        review: QualityReview | tuple[QualityReview, ...],
    ) -> None:
        self.report = report
        self.reviews = review if isinstance(review, tuple) else (review,)
        self.calls: list[tuple[str, ...]] = []
        self.worker_iteration = 0
        self.review_index = 0

    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        stdin: str | None = None,
        timeout_seconds: int = 900,
    ) -> CommandResult:
        del cwd, stdin, timeout_seconds
        self.calls.append(argv)
        if argv[:3] == ("git", "branch", "--show-current"):
            return CommandResult(0, "developer/daniel\n", "")
        if argv[:2] == ("git", "status"):
            return CommandResult(0, "", "")
        if argv[:3] == ("git", "rev-parse", "HEAD"):
            return CommandResult(0, "base123\n", "")
        if argv[:3] == ("kilo", "run", "--auto"):
            self.worker_iteration += 1
            report_path = Path(argv[-1])
            report = self.report.model_copy(update={"iteration": self.worker_iteration})
            report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            return CommandResult(0, '{"type":"done"}\n', "")
        if argv[:3] == ("git", "diff", "--name-only"):
            return CommandResult(
                0,
                "src/xeon/application/quote_draft.py\ntests/test_quote_draft.py\n",
                "",
            )
        if argv[:3] == ("git", "log", "--format=%s"):
            return CommandResult(0, "Feat: :sparkles: CompleteSyntheticQuote\n", "")
        if argv[0] == "uv":
            return CommandResult(0, "passed\n", "")
        if argv[:2] == ("codex", "exec"):
            output_index = argv.index("--output-last-message") + 1
            review = self.reviews[self.review_index]
            self.review_index += 1
            Path(argv[output_index]).write_text(review.model_dump_json(indent=2), encoding="utf-8")
            return CommandResult(0, "", "")
        raise AssertionError(f"Unexpected command: {argv}")


def test_coordinator_runs_worker_checks_and_read_only_codex_review(tmp_path: Path) -> None:
    work_order_path = tmp_path / "work-order.json"
    work_order_path.write_text(_work_order().model_dump_json(indent=2), encoding="utf-8")
    runner = _FakeRunner(
        _worker_report(),
        QualityReview(
            work_order_id="HU-001-run",
            story_id="HU-001",
            iteration=1,
            decision=QualityDecision.APPROVED,
            summary="La HU cumple el contrato y conserva la arquitectura.",
        ),
    )

    result = AgenticCoordinator(root=tmp_path, runner=runner).run(
        work_order_path=work_order_path,
        runs_root=tmp_path / "runs",
        execute=True,
    )

    assert result.decision is QualityDecision.APPROVED
    assert any(call[:3] == ("kilo", "run", "--auto") for call in runner.calls)
    codex_call = next(call for call in runner.calls if call[:2] == ("codex", "exec"))
    assert "read-only" in codex_call
    state = json.loads((tmp_path / "runs" / "HU-001-run" / "state.json").read_text())
    assert state["decision"] == "APPROVED"


def test_coordinator_turns_review_actions_into_second_worker_iteration(tmp_path: Path) -> None:
    work_order_path = tmp_path / "work-order.json"
    work_order_path.write_text(_work_order().model_dump_json(indent=2), encoding="utf-8")
    runner = _FakeRunner(
        _worker_report(),
        (
            QualityReview(
                work_order_id="HU-001-run",
                story_id="HU-001",
                iteration=1,
                decision=QualityDecision.CHANGES_REQUESTED,
                summary="Falta demostrar compatibilidad.",
                required_actions=("Agrega la prueba de compatibilidad solicitada.",),
            ),
            QualityReview(
                work_order_id="HU-001-run",
                story_id="HU-001",
                iteration=2,
                decision=QualityDecision.APPROVED,
                summary="La correccion demuestra compatibilidad.",
            ),
        ),
    )

    result = AgenticCoordinator(root=tmp_path, runner=runner).run(
        work_order_path=work_order_path,
        runs_root=tmp_path / "runs",
        execute=True,
    )

    assert result.decision is QualityDecision.APPROVED
    assert result.iterations == 2
    kilo_calls = [call for call in runner.calls if call[:3] == ("kilo", "run", "--auto")]
    assert len(kilo_calls) == 2
    directive = NextDirective.model_validate_json(
        (tmp_path / "runs" / "HU-001-run" / "next-directive-2.json").read_text()
    )
    assert directive.actions == ("Agrega la prueba de compatibilidad solicitada.",)

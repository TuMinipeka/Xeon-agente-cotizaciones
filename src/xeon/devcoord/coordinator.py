from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from xeon.devcoord.contracts import (
    AgentCheckResult,
    NextDirective,
    QualityDecision,
    QualityFinding,
    QualityReview,
    WorkerReport,
    WorkOrder,
)
from xeon.devcoord.gates import evaluate_worker_evidence
from xeon.devcoord.prompts import coordinator_prompt, worker_prompt

CHECK_COMMANDS: dict[str, tuple[str, ...]] = {
    "ruff_check": ("uv", "run", "ruff", "check", "."),
    "ruff_format": ("uv", "run", "ruff", "format", "--check", "."),
    "mypy": ("uv", "run", "mypy", "src"),
    "pytest": ("uv", "run", "pytest"),
}


class CoordinationError(RuntimeError):
    """Raised when the autonomous cycle cannot safely continue."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        stdin: str | None = None,
        timeout_seconds: int = 900,
    ) -> CommandResult: ...


def _resolve_command(argv: tuple[str, ...]) -> tuple[str, ...]:
    executable = shutil.which(argv[0])
    if executable is None:
        raise CoordinationError(f"No se encontro el ejecutable requerido '{argv[0]}' en PATH.")
    executable_path = Path(executable)
    if os.name != "nt" or executable_path.suffix.lower() not in {".cmd", ".bat"}:
        return (str(executable_path), *argv[1:])

    if executable_path.stem.lower() != "kilo":
        raise CoordinationError(
            f"El ejecutable '{argv[0]}' es un shim de Windows no soportado: {executable_path}"
        )

    kilo_entry = executable_path.parent / "node_modules" / "@kilocode" / "cli" / "bin" / "kilo"
    adjacent_node = executable_path.with_name("node.exe")
    node = str(adjacent_node) if adjacent_node.is_file() else shutil.which("node.exe")
    if node is None or not kilo_entry.is_file():
        raise CoordinationError(
            "Kilo se encontro como shim .CMD, pero no se pudo resolver su ejecutable Node seguro."
        )
    return (node, str(kilo_entry), *argv[1:])


class SubprocessCommandRunner:
    def run(
        self,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        stdin: str | None = None,
        timeout_seconds: int = 900,
    ) -> CommandResult:
        resolved_argv = _resolve_command(argv)
        try:
            completed = subprocess.run(
                resolved_argv,
                cwd=cwd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout or ""
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else exc.stderr or "timeout"
            )
            return CommandResult(124, stdout, stderr)
        except OSError as exc:
            raise CoordinationError(f"No se pudo iniciar '{argv[0]}': {exc}") from exc
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    status: str
    decision: QualityDecision | None
    run_directory: Path
    iterations: int


class AgenticCoordinator:
    def __init__(self, root: Path, runner: CommandRunner | None = None) -> None:
        self._root = root.resolve()
        self._runner = runner or SubprocessCommandRunner()

    def run(
        self,
        *,
        work_order_path: Path,
        runs_root: Path,
        execute: bool = False,
    ) -> CoordinationResult:
        order_path = work_order_path.resolve()
        work_order = WorkOrder.model_validate_json(order_path.read_text(encoding="utf-8"))
        run_directory = runs_root.resolve() / work_order.work_order_id
        run_directory.mkdir(parents=True, exist_ok=True)

        if not execute:
            self._write_state(run_directory, "DRY_RUN", None, 0)
            return CoordinationResult("DRY_RUN", None, run_directory, 0)

        self._preflight(work_order)
        base_commit = self._git(("rev-parse", "HEAD")).stdout.strip()
        directive_path: Path | None = None

        for iteration in range(1, work_order.max_iterations + 1):
            report_path = run_directory / f"grok-report-{iteration}.json"
            worker_instructions = worker_prompt(
                order_path,
                report_path,
                iteration=iteration,
                base_commit=base_commit,
                directive_path=directive_path,
            )
            (run_directory / f"grok-prompt-{iteration}.md").write_text(
                worker_instructions, encoding="utf-8"
            )
            worker_run = self._runner.run(
                (
                    "kilo",
                    "run",
                    "--auto",
                    "--format",
                    "json",
                    "--agent",
                    "xeon-worker",
                    worker_instructions,
                    str(report_path),
                ),
                cwd=self._root,
            )
            (run_directory / f"grok-events-{iteration}.jsonl").write_text(
                worker_run.stdout, encoding="utf-8"
            )
            (run_directory / f"grok-stderr-{iteration}.txt").write_text(
                worker_run.stderr, encoding="utf-8"
            )
            if worker_run.exit_code != 0 or not report_path.exists():
                review = self._blocked_review(
                    work_order,
                    iteration,
                    "Kilo/Grok no produjo un reporte valido.",
                    code="worker_execution_failed",
                )
                self._save_review(run_directory, review)
                return self._finish(run_directory, review, iteration)

            try:
                report = WorkerReport.model_validate_json(report_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError) as exc:
                review = self._blocked_review(
                    work_order,
                    iteration,
                    f"El reporte de Grok no cumple WorkerReport 1.0: {exc}",
                    code="invalid_worker_report",
                )
                self._save_review(run_directory, review)
                return self._finish(run_directory, review, iteration)

            changed_files = self._lines(
                self._git(("diff", "--name-only", f"{base_commit}..HEAD")).stdout
            )
            commit_messages = self._lines(
                self._git(("log", "--format=%s", f"{base_commit}..HEAD")).stdout
            )
            worktree_clean = not self._git(("status", "--porcelain")).stdout.strip()
            verified_checks = self._run_checks(work_order)
            evidence_path = run_directory / f"verified-evidence-{iteration}.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "base_commit": base_commit,
                        "changed_files": changed_files,
                        "commit_messages": commit_messages,
                        "worktree_clean": worktree_clean,
                        "checks": [item.model_dump(mode="json") for item in verified_checks],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            findings = evaluate_worker_evidence(
                work_order,
                report,
                expected_iteration=iteration,
                actual_changed_files=changed_files,
                actual_commit_messages=commit_messages,
                verified_checks=verified_checks,
                worktree_clean=worktree_clean,
            )
            if any(item.blocking for item in findings):
                review = QualityReview(
                    work_order_id=work_order.work_order_id,
                    story_id=work_order.story_id,
                    iteration=iteration,
                    decision=QualityDecision.BLOCKED,
                    summary=(
                        "El ciclo se detuvo por una condicion que requiere intervencion humana."
                    ),
                    findings=findings,
                    required_actions=("Revisar el bloqueo y emitir una nueva orden autorizada.",),
                )
            else:
                review = self._run_codex_review(
                    work_order,
                    order_path,
                    report_path,
                    evidence_path,
                    findings,
                    run_directory,
                    iteration,
                )
                if findings and review.decision is QualityDecision.APPROVED:
                    review = review.model_copy(
                        update={
                            "decision": QualityDecision.CHANGES_REQUESTED,
                            "summary": (
                                "Codex no puede aprobar mientras existan fallos deterministas."
                            ),
                            "findings": (*review.findings, *findings),
                            "required_actions": tuple(item.message for item in findings),
                        }
                    )

            self._save_review(run_directory, review)
            if review.decision is QualityDecision.APPROVED:
                return self._finish(run_directory, review, iteration)
            if review.decision is QualityDecision.BLOCKED:
                return self._finish(run_directory, review, iteration)
            if iteration >= work_order.max_iterations:
                break
            directive = NextDirective.from_review(review)
            directive_path = run_directory / f"next-directive-{directive.next_iteration}.json"
            directive_path.write_text(directive.model_dump_json(indent=2), encoding="utf-8")

        final_review = QualityReview(
            work_order_id=work_order.work_order_id,
            story_id=work_order.story_id,
            iteration=work_order.max_iterations,
            decision=QualityDecision.BLOCKED,
            summary="Se alcanzo el maximo de iteraciones sin aprobacion.",
            required_actions=("Solicitar revision humana antes de continuar.",),
        )
        self._save_review(run_directory, final_review)
        return self._finish(run_directory, final_review, work_order.max_iterations)

    def _preflight(self, order: WorkOrder) -> None:
        branch = self._git(("branch", "--show-current")).stdout.strip()
        if branch != order.branch or branch == "main":
            raise CoordinationError(
                f"La orden exige {order.branch}; rama actual: {branch or 'detached'}"
            )
        if self._git(("status", "--porcelain")).stdout.strip():
            raise CoordinationError("El ciclo autonomo requiere un worktree limpio al iniciar.")

    def _run_checks(self, order: WorkOrder) -> tuple[AgentCheckResult, ...]:
        evidence: list[AgentCheckResult] = []
        for name in order.required_checks:
            result = self._runner.run(CHECK_COMMANDS[name], cwd=self._root)
            combined = (result.stdout + "\n" + result.stderr).strip()
            evidence.append(
                AgentCheckResult(
                    check=name,
                    exit_code=result.exit_code,
                    summary=combined[-4_000:] or "sin salida",
                )
            )
        return tuple(evidence)

    def _run_codex_review(
        self,
        order: WorkOrder,
        order_path: Path,
        report_path: Path,
        evidence_path: Path,
        findings: tuple[QualityFinding, ...],
        run_directory: Path,
        iteration: int,
    ) -> QualityReview:
        schema_path = run_directory / "quality-review.schema.json"
        schema_path.write_text(
            json.dumps(QualityReview.model_json_schema(), indent=2), encoding="utf-8"
        )
        output_path = run_directory / f"codex-review-{iteration}.json"
        prompt = coordinator_prompt(
            order, order_path, report_path, evidence_path, findings
        ).replace("{iteration}", str(iteration))
        (run_directory / f"codex-prompt-{iteration}.md").write_text(prompt, encoding="utf-8")
        result = self._runner.run(
            (
                "codex",
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ),
            cwd=self._root,
            stdin=prompt,
        )
        if result.exit_code != 0 or not output_path.exists():
            return self._blocked_review(
                order,
                iteration,
                "Codex no produjo una revision estructurada.",
                code="coordinator_execution_failed",
            )
        try:
            review = QualityReview.model_validate_json(output_path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            return self._blocked_review(
                order,
                iteration,
                f"La revision de Codex no cumple QualityReview 1.0: {exc}",
                code="invalid_quality_review",
            )
        if (
            review.work_order_id != order.work_order_id
            or review.story_id != order.story_id
            or review.iteration != iteration
        ):
            return self._blocked_review(
                order,
                iteration,
                "La revision de Codex no corresponde al ciclo actual.",
                code="quality_review_identity_mismatch",
            )
        return review

    def _git(self, args: tuple[str, ...]) -> CommandResult:
        result = self._runner.run(("git", *args), cwd=self._root)
        if result.exit_code != 0:
            raise CoordinationError(result.stderr.strip() or f"git {' '.join(args)} fallo")
        return result

    @staticmethod
    def _lines(value: str) -> tuple[str, ...]:
        return tuple(line.strip() for line in value.splitlines() if line.strip())

    @staticmethod
    def _blocked_review(
        order: WorkOrder, iteration: int, message: str, *, code: str
    ) -> QualityReview:
        return QualityReview(
            work_order_id=order.work_order_id,
            story_id=order.story_id,
            iteration=iteration,
            decision=QualityDecision.BLOCKED,
            summary=message,
            findings=(
                QualityFinding(
                    severity="critical",
                    blocking=True,
                    code=code,
                    message=message,
                ),
            ),
            required_actions=("Solicitar intervencion humana antes de reintentar.",),
        )

    @staticmethod
    def _save_review(run_directory: Path, review: QualityReview) -> Path:
        path = run_directory / f"quality-review-{review.iteration}.json"
        path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _finish(
        self, run_directory: Path, review: QualityReview, iteration: int
    ) -> CoordinationResult:
        self._write_state(run_directory, review.decision.value, review.decision, iteration)
        return CoordinationResult(review.decision.value, review.decision, run_directory, iteration)

    @staticmethod
    def _write_state(
        run_directory: Path,
        status: str,
        decision: QualityDecision | None,
        iterations: int,
    ) -> None:
        (run_directory / "state.json").write_text(
            json.dumps(
                {
                    "status": status,
                    "decision": decision.value if decision is not None else None,
                    "iterations": iterations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

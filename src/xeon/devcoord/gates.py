from __future__ import annotations

import fnmatch
import re

from xeon.devcoord.contracts import (
    AgentCheckResult,
    FindingSeverity,
    QualityFinding,
    WorkerReport,
    WorkOrder,
)

_COMMIT_PATTERN = re.compile(
    r"^(Feat|Fix|Docs|Test|Refactor|Chore|Ci): :[a-z0-9_+-]+: [A-Z][A-Za-z0-9]*$"
)


def _is_forbidden_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    name = normalized.rsplit("/", 1)[-1]
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    return normalized == "secrets" or normalized.startswith("secrets/")


def _finding(
    code: str,
    message: str,
    *,
    severity: FindingSeverity = "high",
    blocking: bool = False,
    path: str | None = None,
) -> QualityFinding:
    return QualityFinding(
        severity=severity,
        blocking=blocking,
        code=code,
        message=message,
        path=path,
    )


def _path_allowed(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def evaluate_worker_evidence(
    work_order: WorkOrder,
    report: WorkerReport,
    *,
    expected_iteration: int | None = None,
    actual_changed_files: tuple[str, ...],
    actual_commit_messages: tuple[str, ...],
    verified_checks: tuple[AgentCheckResult, ...],
    worktree_clean: bool,
) -> tuple[QualityFinding, ...]:
    findings: list[QualityFinding] = []

    if report.work_order_id != work_order.work_order_id or report.story_id != work_order.story_id:
        findings.append(
            _finding("report_identity_mismatch", "El reporte no pertenece a esta orden de trabajo.")
        )
    if expected_iteration is not None and report.iteration != expected_iteration:
        findings.append(
            _finding(
                "report_iteration_mismatch",
                "El reporte de Grok no pertenece a la iteracion solicitada.",
                severity="critical",
                blocking=True,
            )
        )
    if report.status != "completed":
        findings.append(
            _finding(
                "worker_did_not_complete",
                f"Grok termino el ciclo con estado {report.status}.",
                severity="critical",
                blocking=True,
            )
        )
    if report.business_rule_changes and not work_order.business_rule_changes_allowed:
        findings.append(
            _finding(
                "business_rule_change_requires_human",
                "Se declararon cambios de reglas de negocio sin autorizacion humana explicita.",
                severity="critical",
                blocking=True,
            )
        )

    reported_paths = {path.replace("\\", "/") for path in report.changed_files}
    actual_paths = {path.replace("\\", "/") for path in actual_changed_files}
    if reported_paths != actual_paths:
        findings.append(
            _finding(
                "changed_files_mismatch",
                "Los archivos declarados por Grok no coinciden con el diff real de Git.",
            )
        )
    for path in sorted(actual_paths):
        if _is_forbidden_path(path):
            findings.append(
                _finding(
                    "forbidden_secret_path",
                    "El ciclo autonomo no puede tocar secretos ni archivos .env.",
                    severity="critical",
                    blocking=True,
                    path=path,
                )
            )
            continue
        if not _path_allowed(path, work_order.allowed_paths):
            findings.append(
                _finding(
                    "changed_path_not_allowed",
                    "El archivo esta fuera del alcance autorizado por la HU.",
                    severity="critical",
                    blocking=True,
                    path=path,
                )
            )

    expected_criteria = {criterion.id for criterion in work_order.acceptance_criteria}
    passed_criteria = {
        result.criterion_id
        for result in report.acceptance_results
        if result.status == "passed" and result.evidence.strip()
    }
    for criterion_id in sorted(expected_criteria - passed_criteria):
        findings.append(
            _finding(
                "acceptance_criterion_not_proven",
                f"No hay evidencia aprobatoria para {criterion_id}.",
            )
        )

    checks_by_name = {result.check: result for result in verified_checks}
    for check in work_order.required_checks:
        result = checks_by_name.get(check)
        if result is None or result.exit_code != 0:
            findings.append(
                _finding(
                    "required_check_failed",
                    f"La verificacion independiente {check} no paso.",
                )
            )

    if not actual_commit_messages:
        findings.append(_finding("missing_commit", "Grok no creo un commit revisable."))
    for message in actual_commit_messages:
        if _COMMIT_PATTERN.fullmatch(message) is None:
            findings.append(
                _finding(
                    "invalid_commit_message",
                    f"El commit no cumple Type: :emoji: ActionInCamelCase: {message}",
                )
            )
    reported_commit_messages = {commit.message for commit in report.commits}
    if reported_commit_messages != set(actual_commit_messages):
        findings.append(
            _finding(
                "commit_evidence_mismatch",
                "Los commits declarados por Grok no coinciden con el historial real de Git.",
            )
        )
    if not worktree_clean:
        findings.append(
            _finding(
                "dirty_worktree_after_worker",
                "Grok dejo cambios sin commit al terminar su reporte.",
            )
        )

    return tuple(findings)

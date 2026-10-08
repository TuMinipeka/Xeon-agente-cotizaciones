from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROTOCOL_VERSION: Final[Literal["1.0"]] = "1.0"
Identifier = str
CheckName = Literal["ruff_check", "ruff_format", "mypy", "pytest"]
FindingSeverity = Literal["critical", "high", "medium", "low", "info"]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AcceptanceCriterion(StrictContract):
    id: Identifier = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
    text: str = Field(min_length=5, max_length=500)


class WorkOrder(StrictContract):
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION
    work_order_id: Identifier = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
    story_id: Identifier = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
    title: str = Field(min_length=5, max_length=160)
    objective: str = Field(min_length=10, max_length=2_000)
    backlog_source: str = "XeonContexto.md"
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = Field(min_length=1)
    allowed_paths: tuple[str, ...] = Field(min_length=1)
    required_checks: tuple[CheckName, ...] = (
        "ruff_check",
        "ruff_format",
        "mypy",
        "pytest",
    )
    branch: str = "developer/daniel"
    max_iterations: int = Field(default=3, ge=1, le=3)
    business_rule_changes_allowed: bool = False

    @field_validator("allowed_paths")
    @classmethod
    def validate_relative_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        for path in paths:
            normalized = path.replace("\\", "/")
            if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
                raise ValueError("allowed_paths solo acepta patrones relativos al repositorio")
        return paths

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        criterion_ids = [criterion.id for criterion in self.acceptance_criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("acceptance_criteria no acepta identificadores duplicados")
        if len(self.allowed_paths) != len(set(self.allowed_paths)):
            raise ValueError("allowed_paths no acepta patrones duplicados")
        if len(self.required_checks) != len(set(self.required_checks)):
            raise ValueError("required_checks no acepta controles duplicados")
        if self.branch == "main":
            raise ValueError("una orden autonoma nunca puede ejecutarse en main")
        return self


class CommitEvidence(StrictContract):
    sha: str = Field(min_length=7, max_length=64)
    message: str = Field(min_length=5, max_length=200)


class AcceptanceResult(StrictContract):
    criterion_id: Identifier
    status: Literal["passed", "failed", "not_run"]
    evidence: str = Field(min_length=3, max_length=2_000)


class AgentCheckResult(StrictContract):
    check: CheckName
    exit_code: int
    summary: str = Field(min_length=1, max_length=4_000)


class WorkerReport(StrictContract):
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION
    work_order_id: Identifier
    story_id: Identifier
    iteration: int = Field(ge=1, le=3)
    status: Literal["completed", "blocked", "failed"]
    summary: str = Field(min_length=5, max_length=4_000)
    changed_files: tuple[str, ...] = ()
    commits: tuple[CommitEvidence, ...] = ()
    acceptance_results: tuple[AcceptanceResult, ...] = ()
    reported_checks: tuple[AgentCheckResult, ...] = ()
    business_rule_changes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class QualityDecision(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    BLOCKED = "BLOCKED"


class QualityFinding(StrictContract):
    severity: FindingSeverity
    blocking: bool = False
    code: str = Field(min_length=3, max_length=80)
    message: str = Field(min_length=5, max_length=2_000)
    path: str | None = None


class QualityReview(StrictContract):
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION
    work_order_id: Identifier
    story_id: Identifier
    iteration: int = Field(ge=1, le=3)
    decision: QualityDecision
    summary: str = Field(min_length=5, max_length=4_000)
    findings: tuple[QualityFinding, ...] = ()
    required_actions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.decision is QualityDecision.CHANGES_REQUESTED and not self.required_actions:
            raise ValueError("CHANGES_REQUESTED requiere acciones concretas")
        if self.decision is QualityDecision.APPROVED and (self.findings or self.required_actions):
            raise ValueError("APPROVED no puede conservar hallazgos ni acciones pendientes")
        return self


class NextDirective(StrictContract):
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION
    work_order_id: Identifier
    story_id: Identifier
    source_review_iteration: int = Field(ge=1, le=2)
    next_iteration: int = Field(ge=2, le=3)
    actions: tuple[str, ...] = Field(min_length=1)
    constraints: tuple[str, ...] = (
        "No ampliar el alcance de la orden.",
        "No modificar reglas de negocio sin autorizacion humana.",
    )

    @classmethod
    def from_review(cls, review: QualityReview) -> NextDirective:
        if review.decision is not QualityDecision.CHANGES_REQUESTED:
            raise ValueError("Solo CHANGES_REQUESTED puede producir una nueva directiva")
        if not review.required_actions:
            raise ValueError("La revision debe indicar acciones concretas")
        return cls(
            work_order_id=review.work_order_id,
            story_id=review.story_id,
            source_review_iteration=review.iteration,
            next_iteration=review.iteration + 1,
            actions=review.required_actions,
        )

"""Write evidence-backed JSON and Markdown summaries without credentials."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _safe(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"(?:sk-|xai-|pk_)[A-Za-z0-9_-]{8,}", "[REDACTED]", value)
        value = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)\S+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)(Bearer\s+)\S+", r"\1[REDACTED]", value)
        return value
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    return value


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(
        json.dumps(_safe(manifest), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_case(path: Path, case: dict[str, Any], calls: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = {"case": _safe(case), "calls": calls}
    with (path / "cases.jsonl").open("a", encoding="utf-8") as journal:
        journal.write(json.dumps(record, ensure_ascii=False) + "\n")
        journal.flush()
        os.fsync(journal.fileno())


def append_observability(path: Path, events: list[dict[str, Any]]) -> None:
    """Persist raw metric events (no personal data) for scripts/cost_report.py."""
    if not events:
        return
    path.mkdir(parents=True, exist_ok=True)
    with (path / "observability.jsonl").open("a", encoding="utf-8") as journal:
        for event in events:
            journal.write(json.dumps(event, ensure_ascii=False) + "\n")


def resume_report(path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    journal = path / "cases.jsonl"
    records: list[dict[str, Any]] = []
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines(keepends=True):
            if not line.endswith("\n"):
                break  # An interrupted write may leave only the final line incomplete.
            records.append(json.loads(line))
    finished = {(item["case"]["id"], item["case"]["rep"]): item["case"] for item in records}
    if len(finished) != len(records):
        raise ValueError("El journal contiene casos duplicados.")
    planned = {(item["id"], item["rep"]): item for item in manifest["jobs"]}
    if not finished.keys() <= planned.keys():
        raise ValueError("El journal contiene casos ajenos a la corrida.")
    cases = [
        finished.get(
            key,
            {
                "id": key[0],
                "rep": key[1],
                "status": "ERROR",
                "origin": "infra",
                "severity": job["severity"],
                "evidence": "Corrida interrumpida antes de terminar este caso.",
                "checks": [],
                "transcript": [],
            },
        )
        for key, job in sorted(planned.items())
    ]
    report = {
        "fingerprint": manifest["fingerprint"],
        "provenance": manifest["provenance"],
        "mode": manifest["mode"],
        "calls": max((int(item["calls"]) for item in records), default=0),
        "max_calls": manifest["max_calls"],
        "cases": cases,
        "metrics": metrics(cases),
        "recovered_from_journal": True,
    }
    write_report(path, report)
    return report


def metrics(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    groups = {
        "quote_accuracy": {"quote_matches_oracle"},
        "hallucination_rate": {"no_invented_amounts", "no_invented_stock"},
        "attack_resistance": {"no_internal_leak"},
        "scope_compliance": {"out_of_scope_handled"},
    }
    result: dict[str, float | None] = {}
    for label, check_types in groups.items():
        observed = [
            check
            for case in cases
            for check in case.get("checks", [])
            if check["name"] in check_types
            and check["status"] in {"PASS", "FAIL"}
            and (label != "attack_resistance" or case.get("category") == "adversarial")
            and (label != "hallucination_rate" or check["actual"] not in ("", "[]"))
        ]
        result[label] = (
            round(
                sum(
                    item["status"] == ("FAIL" if label == "hallucination_rate" else "PASS")
                    for item in observed
                )
                / len(observed),
                4,
            )
            if observed
            else None
        )
    return result


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    safe = _safe(report)
    (path / "report.json").write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# XEON conversational evaluation",
        "",
        f"Run: `{safe['fingerprint']}` | mode: `{safe['mode']}` | calls: {safe['calls']}",
        "",
        "## Calculated metrics",
        "",
    ]
    lines.extend(
        f"- {key}: {value if value is not None else 'n/a'}"
        for key, value in safe["metrics"].items()
    )
    lines.extend(["", "## Cases", ""])
    for case in safe["cases"]:
        lines.extend(
            [
                f"### {case['id']} rep {case['rep']}: {case['status']}",
                "",
                f"Origin: {case['origin']} | severity: {case['severity']}",
                "",
            ]
        )
        for check in case.get("checks", []):
            lines.append(
                f"- {check['name']}: {check['status']}; expected={check['expected']}; "
                f"actual={check['actual']}; {check['evidence']}"
            )
        lines.extend(["", "Transcript:", ""])
        for turn in case.get("transcript", []):
            lines.extend([f"- User: {turn['user']}", f"- XEON: {turn['assistant']}"])
        evidence = case.get("evidence")
        if isinstance(evidence, dict):
            lines.extend(["", "Verified tool contexts and saved DRAFTs:", "", "```text"])
            lines.extend(str(item) for item in evidence.get("tool_contexts", []))
            lines.extend(["```", "", "```json"])
            lines.append(json.dumps(evidence.get("drafts", []), ensure_ascii=False, indent=2))
            lines.extend(["```", ""])
        else:
            lines.extend(["", f"Evidence: {evidence}", ""])
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

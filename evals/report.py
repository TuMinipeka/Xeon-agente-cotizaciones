"""Write evidence-backed JSON and Markdown summaries without credentials."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _safe(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", value)
        value = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)\S+", r"\1[REDACTED]", value)
        return value
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    return value


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

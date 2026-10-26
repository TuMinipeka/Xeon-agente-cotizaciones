from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.cost_report import load, main, render
from xeon.application.observability import aggregate


def _events() -> list[dict[str, object]]:
    return [
        {
            "stage": "llm",
            "task": "S16",
            "duration_ms": 120.0,
            "usage_known": True,
            "prompt_tokens": 300,
            "completion_tokens": 20,
            "estimated_cost": "0.0004",
            "cost_unit": "supuesto",
        },
        {"stage": "llm", "task": "S16", "duration_ms": 900.0, "usage_known": False},
        {"stage": "turno", "task": "S16", "duration_ms": 1500.0},
    ]


def test_cost_report_reads_a_report_folder_and_prints_a_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "observability.jsonl").write_text(
        "\n".join(json.dumps(event) for event in _events()) + "\n", encoding="utf-8"
    )
    assert main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "S16 | 2 | 300/20 | 1 | 0.0004 supuesto" in out
    assert "llm 120.0/900.0" in out
    assert main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["S16"]["usage_unknown_calls"] == 1


def test_cost_report_fails_clearly_without_a_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="No existe"):
        load(tmp_path)


def test_render_marks_missing_cost_as_unavailable() -> None:
    assert "n/d" in render(aggregate([{"stage": "turno", "task": "x", "duration_ms": 1.0}]))

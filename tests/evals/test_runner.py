from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from evals.runner import run


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

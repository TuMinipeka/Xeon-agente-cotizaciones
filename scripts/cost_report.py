"""Aggregate XEON metric events (JSONL) by task: calls, tokens, latency p50/p95 and cost.

Reads `observability.jsonl` from an evaluation report folder or a production metrics file
(`METRICS_PATH`). Cost uses the configured rates, which are an assumption: the gateway's
unit is not documented.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from xeon.application.observability import aggregate


def load(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        path = path / "observability.jsonl"
    if not path.is_file():
        raise SystemExit(f"No existe el archivo de metricas: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def render(report: dict[str, dict[str, Any]]) -> str:
    header = "tarea | llamadas LLM | tokens in/out | uso desconocido | costo (supuesto)"
    lines = [header + " | etapas p50/p95 ms"]
    for task, row in report.items():
        stages = "; ".join(
            f"{name} {data['p50_ms']}/{data['p95_ms']}" for name, data in row["stages"].items()
        )
        cost = (
            "n/d"
            if row["estimated_cost"] is None
            else f"{row['estimated_cost']} {row['cost_unit']}"
        )
        lines.append(
            f"{task} | {row['llm_calls']} | {row['prompt_tokens']}/{row['completion_tokens']} | "
            f"{row['usage_unknown_calls']} | {cost} | {stages}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Carpeta de un reporte de evals o archivo JSONL")
    parser.add_argument("--json", action="store_true", help="Salida JSON en lugar de tabla")
    args = parser.parse_args(argv)
    report = aggregate(load(args.path))
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

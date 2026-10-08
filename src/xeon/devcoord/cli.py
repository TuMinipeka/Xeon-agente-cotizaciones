from __future__ import annotations

import argparse
import json
from pathlib import Path

from xeon.devcoord.contracts import AcceptanceCriterion, WorkOrder
from xeon.devcoord.coordinator import AgenticCoordinator, CoordinationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordina Grok y Codex por una HU verificable.")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("new", help="Crea una orden local ignorada por Git.")
    create.add_argument("--story-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--criterion", action="append", required=True, metavar="ID=TEXTO")
    create.add_argument("--allowed-path", action="append", required=True)

    run = commands.add_parser("run", help="Prepara o ejecuta el ciclo autonomo.")
    run.add_argument("work_order", type=Path)
    run.add_argument("--execute", action="store_true")
    return parser


def _criterion(value: str) -> AcceptanceCriterion:
    identifier, separator, text = value.partition("=")
    if not separator:
        raise ValueError("Cada --criterion debe usar ID=TEXTO")
    return AcceptanceCriterion(id=identifier, text=text)


def main() -> None:
    args = _parser().parse_args()
    root = Path.cwd()
    if args.command == "new":
        order = WorkOrder(
            work_order_id=f"{args.story_id}-run",
            story_id=args.story_id,
            title=args.title,
            objective=args.objective,
            acceptance_criteria=tuple(_criterion(value) for value in args.criterion),
            allowed_paths=tuple(args.allowed_path),
        )
        target = root / ".agentic" / "work-orders" / f"{order.work_order_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(order.model_dump_json(indent=2), encoding="utf-8")
        print(target)
        return

    try:
        result = AgenticCoordinator(root).run(
            work_order_path=args.work_order,
            runs_root=root / ".agentic" / "runs",
            execute=args.execute,
        )
    except (CoordinationError, OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            {
                "status": result.status,
                "decision": result.decision.value if result.decision is not None else None,
                "run_directory": str(result.run_directory),
                "iterations": result.iterations,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

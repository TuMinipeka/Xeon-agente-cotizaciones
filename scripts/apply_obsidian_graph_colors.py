"""Aplica los grupos de color del grafo de Obsidian definidos en wiki/index.md.

Obsidian guarda graph.json desde memoria: ejecutar con Obsidian cerrado.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WIKI_GROUPS: list[tuple[str, str]] = [
    ("tag:#xeon/decision", "#FF8A65"),
    ("tag:#xeon/estado", "#FFD54F"),
    ("tag:#xeon/arquitectura", "#4FC3F7"),
    ("tag:#xeon/interfaz", "#00D9A3"),
    ("tag:#xeon/producto", "#B388FF"),
    ("tag:#xeon/operacion OR file:log.md", "#F06292"),
    ("tag:#xeon/fuente OR path:raw", "#90A4AE"),
    ("tag:#xeon/hub", "#6FFFD3"),
]
ROOT_EXTRA: list[tuple[str, str]] = [
    ("path:docs", "#26A69A"),
    (
        "file:README.md OR file:AGENTS.md OR file:CONTRIBUTING.md "
        "OR file:CLAUDE.md OR file:GEMINI.md",
        "#EAFBF5",
    ),
]
VAULTS: dict[Path, list[tuple[str, str]]] = {
    ROOT / "wiki" / ".obsidian": WIKI_GROUPS,
    ROOT / ".obsidian": WIKI_GROUPS + ROOT_EXTRA,
}


def obsidian_running() -> bool:
    if sys.platform != "win32":
        return False
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return "Obsidian.exe" in result.stdout


def color_group(query: str, hex_color: str) -> dict[str, object]:
    return {"query": query, "color": {"a": 1, "rgb": int(hex_color.lstrip("#"), 16)}}


def main() -> int:
    if obsidian_running() and "--force" not in sys.argv:
        print("Cierra Obsidian antes de aplicar los colores (o usa --force).")
        return 1
    for config_dir, groups in VAULTS.items():
        if not config_dir.is_dir():
            continue
        graph = config_dir / "graph.json"
        data = json.loads(graph.read_text(encoding="utf-8")) if graph.exists() else {}
        data["colorGroups"] = [color_group(query, color) for query, color in groups]
        graph.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"{graph.relative_to(ROOT)}: {len(groups)} grupos de color")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

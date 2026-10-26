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
# Capas del grafo de codigo (etiquetas xeon-grafo/* de build_graphify_map.py). Van despues de
# las paginas xeon/*: en Obsidian gana el primer grupo que coincide, asi que las notas puente
# (xeon/hub) conservan el color de hub. graphify/INFERRED no tiene grupo: es la confianza de las
# aristas y colorearia los nodos por encima de su capa.
LAYER_GROUPS: list[tuple[str, str]] = [
    ("tag:#xeon-grafo/dominio", "#7986CB"),
    ("tag:#xeon-grafo/aplicacion", "#66BB6A"),
    ("tag:#xeon-grafo/agente", "#E53935"),
    ("tag:#xeon-grafo/adaptadores", "#26C6DA"),
    ("tag:#xeon-grafo/api", "#1E88E5"),
    ("tag:#xeon-grafo/canal", "#C6FF00"),
    ("tag:#xeon-grafo/config", "#8D6E63"),
    ("tag:#xeon-grafo/pruebas", "#E040FB"),
    ("tag:#xeon-grafo/evaluacion", "#D84315"),
    ("tag:#xeon-grafo/scripts", "#9E9D24"),
    ("tag:#xeon-grafo/docs", "#80CBC4"),
    ("tag:#xeon-grafo/wiki", "#D7CCC8"),
    ("tag:#xeon-grafo/externo", "#757575"),
    ("tag:#xeon-grafo/comunidad", "#455A64"),
    ("tag:#xeon-grafo/hub", "#FFFFFF"),
    ("tag:#xeon-grafo/puente", "#18FFFF"),
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
    ROOT / "wiki" / ".obsidian": WIKI_GROUPS + LAYER_GROUPS,
    ROOT / ".obsidian": WIKI_GROUPS + ROOT_EXTRA + LAYER_GROUPS,
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
        data["collapse-color-groups"] = False
        data["showOrphans"] = True
        graph.write_text(json.dumps(data, indent=2), encoding="utf-8")
        saved = len(json.loads(graph.read_text(encoding="utf-8"))["colorGroups"])
        status = "OK" if saved == len(groups) else "REVISAR"
        print(f"{graph.relative_to(ROOT)}: {saved}/{len(groups)} grupos de color ({status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

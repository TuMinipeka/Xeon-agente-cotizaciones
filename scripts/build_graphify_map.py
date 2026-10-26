"""Build XEON's local Graphify graph and its Obsidian view without an LLM."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from graphify.detect import detect
from graphify.export import _obsidian_safe_stem

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "graphify-out"
AST_ROOT = ROOT / ".bootstrap" / "graphify-ast"
AST_OUT = AST_ROOT / "graphify-out"
GRAPH = OUT / "graph.json"
VAULT = ROOT / "wiki" / "graph"
GENERATED = VAULT / "generated"
BLOCKED_DIRS = {"secrets", "video", "reports", ".venv", ".bootstrap", ".cache"}
BLOCKED_SUFFIXES = {
    ".mp4",
    ".mp3",
    ".mov",
    ".wav",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)|\[\[([^\]]+)\]\]")
WIKI_PAGES = (
    "arquitectura-actual",
    "contratos-herramientas",
    "canal-kapso",
    "xeon-cli",
    "evaluacion-conversacional",
)


def is_blocked(relative: str) -> bool:
    path = Path(relative)
    parts = {part.lower() for part in path.parts}
    return (
        bool(parts & BLOCKED_DIRS)
        or any(part.lower().startswith(".env") for part in path.parts)
        or path.suffix.lower() in BLOCKED_SUFFIXES
        or "__pycache__" in parts
        or ".pytest_cache" in parts
        or ".mypy_cache" in parts
        or ".ruff_cache" in parts
        or "graphify-out" in parts
        or ("generated" in parts and "graph" in parts)
    )


def corpus() -> tuple[dict[str, list[str]], list[str]]:
    found = detect(ROOT)
    files: dict[str, list[str]] = {}
    for kind, entries in found["files"].items():
        files[kind] = [
            str(Path(entry).resolve().relative_to(ROOT)).replace("\\", "/") for entry in entries
        ]
    unclassified = [
        str(Path(entry).resolve().relative_to(ROOT)).replace("\\", "/")
        for entry in found.get("unclassified", [])
    ]
    all_paths = (path for entries in files.values() for path in entries)
    forbidden = sorted(path for path in [*all_paths, *unclassified] if is_blocked(path))
    if forbidden:
        raise SystemExit(f"Graphify preflight rejected {len(forbidden)} forbidden paths")
    return files, unclassified


def call_graphify(*args: str) -> None:
    env = os.environ.copy()
    env["GRAPHIFY_BACKEND"] = "none"
    env["GRAPHIFY_NO_TIPS"] = "1"
    subprocess.run([sys.executable, "-m", "graphify", *args], cwd=ROOT, env=env, check=True)


def file_id(path: str) -> str:
    return "xeon_file_" + re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")


def resolve_link(source: str, target: str, known: set[str]) -> str | None:
    raw = unquote(urlsplit(target.split("|", 1)[0].strip()).path)
    if not raw or raw.startswith("/") or ":" in raw or raw.startswith("#"):
        return None
    if not Path(raw).suffix and source.startswith("wiki/"):
        raw += ".md"
    resolved = (ROOT / source).parent.joinpath(raw).resolve()
    try:
        relative = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return None
    return relative if relative in known else None


def add_local_files(files: dict[str, list[str]], unclassified: list[str]) -> None:
    data = json.loads((AST_OUT / "graph.json").read_text(encoding="utf-8"))
    all_paths = {path for entries in files.values() for path in entries} | set(unclassified)
    nodes = {node["id"]: node for node in data["nodes"]}
    edges = {(edge["source"], edge["target"], edge["relation"]): edge for edge in data["links"]}

    def edge(source: str, target: str, relation: str, source_file: str) -> None:
        key = (source, target, relation)
        edges[key] = {
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": source_file,
            "weight": 1.0,
        }

    for path in sorted(all_paths):
        kind = next((key for key, entries in files.items() if path in entries), "config")
        related = [
            node.get("community")
            for node in data["nodes"]
            if node.get("source_file") == path and node.get("community") is not None
        ]
        community = related[0] if related else 1000 + {"document": 1, "config": 2}.get(kind, 3)
        nodes[file_id(path)] = {
            "id": file_id(path),
            "label": path,
            "file_type": "document" if kind == "document" else kind,
            "source_file": path,
            "source_location": "L1",
            "_origin": "xeon-local-files",
            "community": community,
        }

    for node in tuple(nodes.values()):
        source = node.get("source_file", "")
        if node.get("_origin") != "xeon-local-files" and source in all_paths:
            edge(file_id(source), node["id"], "contains", source)

    for path in sorted(files.get("document", [])):
        content = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        for match in LINK.finditer(content):
            target = resolve_link(path, match.group(1) or match.group(2) or "", all_paths)
            if target:
                edge(file_id(path), file_id(target), "links_to", path)

    data["nodes"] = list(nodes.values())
    data["links"] = list(edges.values())
    data["graph"]["xeon_local_file_layer"] = True

    # AST rationale may mention protected filenames even when their contents
    # were excluded. Keep those labels out of shareable graph artifacts too.
    def sanitize(value: object) -> object:
        if isinstance(value, str):
            return value.replace("secrets/", "[protected]/").replace(".env", "[local-config]")
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    data = sanitize(data)
    OUT.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    communities: dict[str, list[str]] = {}
    for node in data["nodes"]:
        communities.setdefault(str(node["community"]), []).append(node["id"])
    OUT.joinpath(".graphify_analysis.json").write_text(
        json.dumps(
            {
                "communities": communities,
                "cohesion": {},
                "gods": [],
                "surprises": [],
                "tokens": {"input": 0, "output": 0},
            }
        ),
        encoding="utf-8",
    )


def write_report(result: dict[str, object]) -> None:
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    degrees: dict[str, int] = {}
    for edge in data["links"]:
        for endpoint in (edge["source"], edge["target"]):
            degrees[endpoint] = degrees.get(endpoint, 0) + 1
    labels = {node["id"]: node["label"] for node in data["nodes"]}
    hubs = sorted(degrees.items(), key=lambda item: (-item[1], item[0]))[:12]
    lines = [
        "# Grafo local de XEON",
        "",
        "Generado con Graphify 0.9.95: AST local y enlaces Markdown locales.",
        "Los documentos aparecen como archivos y enlaces; no contienen conceptos de un LLM.",
        "",
        f"- Nodos: {result['nodes']}",
        f"- Aristas: {result['edges']}",
        f"- Comunidades: {result['communities']}",
        f"- Archivos cubiertos: {result['files_covered']}",
        "- Llamadas LLM: 0",
        "",
        "## Nodos con más conexiones",
        "",
        *[f"- `{labels.get(node_id, node_id)}`: {degree}" for node_id, degree in hubs],
        "",
        "## Consulta",
        "",
        '`uv run --locked --group graph graphify query "AgentService"`',
        '`uv run --locked --group graph graphify explain "CommercialToolbelt"`',
        '`uv run --locked --group graph graphify path "AgentService" "Quote"`',
        "",
    ]
    OUT.joinpath("GRAPH_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def audit(files: dict[str, list[str]], unclassified: list[str]) -> dict[str, object]:
    data = json.loads(GRAPH.read_text(encoding="utf-8"))
    # Inspect output only. Never open excluded inputs or secret files to compare values.
    source_paths = [
        value
        for item in [*data["nodes"], *data["links"]]
        if isinstance(value := item.get("source_file"), str)
    ]
    leaks = [path for path in source_paths if is_blocked(path)]
    serial = GRAPH.read_text(encoding="utf-8")
    key_like = re.findall(r"(?i)(?:sk|gsk|xai|kapso)[-_][A-Za-z0-9]{20,}", serial)
    blocked_mentions = len(re.findall(r"(?i)secrets[/\\]|\.env", serial))
    if leaks or key_like or blocked_mentions:
        raise SystemExit(
            f"Graph output audit failed: {len(leaks)} forbidden paths, "
            f"{len(key_like)} key-like values, {blocked_mentions} protected-path mentions"
        )
    covered = {node.get("source_file") for node in data["nodes"] if node.get("source_file")}
    expected = {path for entries in files.values() for path in entries} | set(unclassified)
    missing = sorted(expected - covered)
    if missing:
        raise SystemExit(f"Graph output audit failed: {len(missing)} expected files missing")
    communities = {
        node.get("community") for node in data["nodes"] if node.get("community") is not None
    }
    result: dict[str, object] = {
        "graphify_version": data["graph"].get("graphify_version"),
        "nodes": len(data["nodes"]),
        "edges": len(data["links"]),
        "communities": len(communities),
        "files_covered": len(expected),
        "files_by_type": {kind: len(paths) for kind, paths in files.items()},
        "unclassified_files_included": len(unclassified),
        "excluded_path_hits": len(leaks),
        "key_like_value_hits": len(key_like),
        "blocked_path_mentions": blocked_mentions,
        "llm_calls": 0,
    }
    OUT.joinpath("xeon-audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def write_vault_bridges() -> None:
    VAULT.mkdir(parents=True, exist_ok=True)
    links = "\n".join(
        f"- [{page.replace('-', ' ').capitalize()}](../pages/{page}.md)" for page in WIKI_PAGES
    )
    VAULT.joinpath("README.md").write_text(
        "---\ntags:\n  - xeon/hub\n---\n\n# Grafo local de XEON\n\n"
        "Los nodos generados están en [generated](generated/). "
        "La [vista interactiva](../../graphify-out/graph.html) y el "
        "[grafo JSON](../../graphify-out/graph.json) se regeneran con "
        "`uv run --locked --group graph python scripts/build_graphify_map.py`.\n\n"
        "## Páginas de referencia\n\n" + links + "\n",
        encoding="utf-8",
    )
    for page in WIKI_PAGES:
        node_note = _obsidian_safe_stem(f"wiki/pages/{page}.md")
        (VAULT / f"{page}.md").write_text(
            "---\ntags:\n  - xeon/hub\n---\n\n"
            f"# {page.replace('-', ' ').capitalize()} en el grafo\n\n"
            f"[Síntesis vigente](../pages/{page}.md) · "
            f"[Nodo del archivo](generated/{node_note}.md)\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Rebuild AST from all allowed files")
    args = parser.parse_args()
    files, unclassified = corpus()
    extract_args = ["extract", ".", "--code-only", "--no-dedup", "--out", str(AST_ROOT)]
    if args.force:
        extract_args.append("--force")
    call_graphify(*extract_args)
    add_local_files(files, unclassified)
    result = audit(files, unclassified)
    write_report(result)
    call_graphify("export", "html", "--graph", str(GRAPH))
    call_graphify("export", "obsidian", "--dir", str(GENERATED))
    write_vault_bridges()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

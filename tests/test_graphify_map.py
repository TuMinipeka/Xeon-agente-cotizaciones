"""Security and link-resolution checks for the local Graphify corpus."""

from pathlib import Path

import pytest

pytest.importorskip("graphify", reason="requiere el grupo graph")

from scripts.build_graphify_map import (
    DEFAULT_PAGE_HUB,
    HUB_LAYERS,
    PAGE_HUB,
    is_blocked,
    layer_for,
    link_stats,
    resolve_link,
)


def test_protected_inputs_are_rejected_before_graph_extraction() -> None:
    for path in (
        "secrets/provider_key.txt",
        ".env",
        ".env.example",
        "video/clip.mp4",
        "reports/run.json",
        ".venv/Lib/site-packages/module.py",
        "docs/audio.mp3",
        "wiki/graph/generated/node.md",
    ):
        assert is_blocked(path), path
    assert not is_blocked("wiki/pages/arquitectura-actual.md")


def test_document_links_stay_inside_the_allowed_corpus() -> None:
    known = {"wiki/pages/arquitectura-actual.md", "docs/ARCHITECTURE.md"}
    assert (
        resolve_link("wiki/index.md", "pages/arquitectura-actual.md", known)
        == "wiki/pages/arquitectura-actual.md"
    )
    assert resolve_link("wiki/index.md", "../../outside.md", known) is None
    assert resolve_link("wiki/index.md", "https://example.com", known) is None


def test_layer_for_maps_source_files_to_architecture_layers() -> None:
    cases = {
        "src/xeon/domain/money.py": "dominio",
        "src/xeon/application/ports/llm.py": "aplicacion",
        "src/xeon/agent/service.py": "agente",
        "src/xeon/adapters/grok.py": "adaptadores",
        "src/xeon/connectors/sql.py": "adaptadores",
        "src/xeon/api/app.py": "api",
        "src/xeon/shell/repl.py": "canal",
        "src/xeon/cli.py": "canal",
        "src/xeon/config.py": "config",
        "connectors/example-ferreteria.yaml": "config",
        "compose.yaml": "config",
        "pyproject.toml": "config",
        "tests/test_cli.py": "pruebas",
        "evals/runner.py": "evaluacion",
        "scripts/build_graphify_map.py": "scripts",
        "docs/ARCHITECTURE.md": "docs",
        "README.md": "docs",
        "wiki/pages/orquestacion.md": "wiki",
        "": "externo",
    }
    for source, layer in cases.items():
        assert layer_for(source) == layer, source


def test_hub_layers_cover_every_layer_and_reference_existing_pages() -> None:
    pages = {path.stem for path in Path("wiki/pages").glob("*.md")}
    for layer, (_, linked) in HUB_LAYERS.items():
        assert set(linked) <= pages, layer
    assert set(PAGE_HUB) <= pages
    assert set(PAGE_HUB.values()) | {DEFAULT_PAGE_HUB} <= set(HUB_LAYERS)
    assert {layer_for(p) for p in ("src/xeon/domain/a.py", "", "tests/t.py")} <= set(HUB_LAYERS)


def test_link_stats_counts_orphans_with_markdown_and_wikilinks(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("[b](sub/b.md) y [[c]]", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("sin enlaces", encoding="utf-8")
    (tmp_path / "c.md").write_text("", encoding="utf-8")
    (tmp_path / "huerfana.md").write_text("[externo](https://example.com)", encoding="utf-8")
    stats = link_stats(tmp_path)
    assert stats["notes"] == 4
    assert stats["orphan_paths"] == ["huerfana.md"]

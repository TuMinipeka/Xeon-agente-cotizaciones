"""Security and link-resolution checks for the local Graphify corpus."""

from scripts.build_graphify_map import is_blocked, resolve_link


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

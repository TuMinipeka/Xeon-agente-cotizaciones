import ast
import re
from pathlib import Path

VERSIONS = Path("commercial_migrations/versions")


def _assignment(path: Path, name: str) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, str | None)
            return value
    raise AssertionError(f"No existe {name} en {path}")


def test_commercial_migration_chain_is_linear_and_separate() -> None:
    files = sorted(VERSIONS.glob("*.py"))
    revisions = [_assignment(path, "revision") for path in files]
    parents = [_assignment(path, "down_revision") for path in files]
    assert revisions == [
        "0001_commercial_core",
        "0002_normalized_catalog",
        "0003_versioned_pricing",
        "0004_normalized_stock",
        "0005_vector_search_foundation",
    ]
    assert parents == [None, *revisions[:-1]]


def test_vector_foundation_has_no_ann_index_or_fixed_dimension() -> None:
    source = (VERSIONS / "0005_vector_search_foundation.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "create extension if not exists vector" in lowered
    assert "hnsw" not in lowered
    assert "ivfflat" not in lowered
    assert re.search(r"vector\s*\(\s*\d+", lowered) is None


def test_stock_and_catalog_are_normalized_relations() -> None:
    catalog = (VERSIONS / "0002_normalized_catalog.py").read_text(encoding="utf-8")
    stock = (VERSIONS / "0004_normalized_stock.py").read_text(encoding="utf-8")
    for relation in (
        "product_brands",
        "product_colors",
        "product_lines",
        "product_categories",
        "product_sublines",
    ):
        assert relation in catalog
    assert '"stock"' in stock
    assert '"warehouse_id"' in stock
    assert '"quantity_type_code"' in stock

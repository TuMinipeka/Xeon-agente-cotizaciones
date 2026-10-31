from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.seed_commercial_db import ensure_seed_allowed, load_seed
from xeon.config import Settings


def _seed(tmp_path: Path, payload: str) -> Path:
    import hashlib

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "products.jsonl").write_text(payload, encoding="utf-8", newline="\n")
    manifest = {
        "seed_sha256": hashlib.sha256(payload.encode()).hexdigest().upper(),
        "product_count": 1,
    }
    (seed_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return seed_dir


def test_load_seed_validates_fingerprint_count_and_unique_sku(tmp_path: Path) -> None:
    seed_dir = _seed(tmp_path, '{"sku":"A-1"}\n')
    _, products = load_seed(seed_dir)
    assert products == [{"sku": "A-1"}]
    (seed_dir / "products.jsonl").write_text('{"sku":"ALTERED"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="huella"):
        load_seed(seed_dir)


def test_production_rejects_test_stock_seed() -> None:
    with pytest.raises(RuntimeError, match="producción"):
        ensure_seed_allowed(Settings(app_env="production", _env_file=None))


def test_development_allows_test_stock_seed() -> None:
    ensure_seed_allowed(Settings(app_env="development", _env_file=None))

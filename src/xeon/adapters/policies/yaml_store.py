"""Read tenant-approved operational policy text from local YAML files."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


class YamlPolicyRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, tenant_id: str, topic: str) -> str | None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", tenant_id):
            return None
        if topic not in {"pagos", "recogida", "domicilio", "horarios", "facturacion"}:
            return None
        path = self._root / f"{tenant_id}.yaml"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError, yaml.YAMLError:
            return None
        if not isinstance(data, dict):
            return None
        value = data.get(topic)
        return value.strip() if isinstance(value, str) and value.strip() else None

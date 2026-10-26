"""Read tenant-approved operational policy text from local YAML files."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from xeon.application.policy_schema import StorePolicy


class YamlPolicyRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, tenant_id: str) -> StorePolicy:
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", tenant_id):
            return StorePolicy()
        try:
            data = yaml.safe_load((self._root / f"{tenant_id}.yaml").read_text(encoding="utf-8"))
            return StorePolicy.model_validate(data if isinstance(data, dict) else {})
        except OSError, yaml.YAMLError, ValidationError:
            return StorePolicy()

    def get(self, tenant_id: str, topic: str) -> str | None:
        policy = self.load(tenant_id)
        match topic:
            case "pagos":
                return ", ".join(policy.pagos) if policy.pagos else None
            case "recogida":
                option = policy.entrega.recoger_en_sede if policy.entrega else None
                return option.nota if option and option.disponible else None
            case "domicilio":
                option = policy.entrega.domicilio if policy.entrega else None
                return option.costo if option and option.disponible else None
            case "horarios":
                hours = policy.horario
                if hours is None or hours.lunes_a_viernes is None:
                    return None
                unknown = "pendiente de confirmar con un asesor"
                return (
                    f"Lunes a viernes {hours.lunes_a_viernes}; "
                    f"sabado {hours.sabado or unknown}; domingo {hours.domingo or unknown}"
                )
            case "facturacion":
                return policy.facturacion
            case _:
                return None

"""Freeze synthetic XEON seed as independent evaluation fixtures.

Run once to create fixtures; later runs fail on drift. Use --refresh deliberately
when the synthetic seed changes and review the resulting JSON diff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from xeon.adapters.catalog.synthetic_seed import SYNTHETIC_PRODUCTS
from xeon.adapters.inventory.memory import SYNTHETIC_SNAPSHOTS

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "evals" / "fixtures"


def fixture_bytes() -> dict[str, bytes]:
    catalog = [
        {
            "sku": item.sku,
            "name": item.name,
            "aliases": list(item.aliases),
            "unit": item.unit,
            "unit_price": str(item.list_price.amount),
            "currency": item.list_price.currency,
            "source": item.source,
            "catalog_version": item.catalog_version,
        }
        for item in SYNTHETIC_PRODUCTS
    ]
    inventory = [
        {
            "sku": item.sku,
            "branch_id": item.branch_id,
            "quantity": str(item.quantity),
            "channel": item.channel.value,
            "observed_at": item.observed_at,
            "valid_until": item.valid_until,
            "source": item.source,
        }
        for item in SYNTHETIC_SNAPSHOTS
    ]
    policies = {"currency": "COP", "taxes": None, "discount_policy": None, "status": "DRAFT"}
    values = {"catalog.json": catalog, "inventory.json": inventory, "policies.json": policies}
    return {
        name: (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        for name, data in values.items()
    }


def digest(files: dict[str, bytes]) -> str:
    hasher = hashlib.sha256()
    for name, data in sorted(files.items()):
        hasher.update(name.encode() + b"\0" + data)
    return hasher.hexdigest()


def export(*, refresh: bool = False, destination: Path = DESTINATION) -> str:
    files = fixture_bytes()
    fingerprint = digest(files)
    stamp = destination / "fixtures.sha256"
    if stamp.exists() and not refresh:
        stored = stamp.read_text(encoding="ascii").strip()
        if stored != fingerprint or any(
            not (destination / name).exists() or (destination / name).read_bytes() != data
            for name, data in files.items()
        ):
            raise RuntimeError("La semilla sintetica cambio: revise el diff y use --refresh.")
        return fingerprint
    if not refresh and any((destination / name).exists() for name in files):
        raise RuntimeError("Fixtures parciales sin huella; revise y use --refresh.")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (destination / name).write_bytes(data)
    stamp.write_text(fingerprint + "\n", encoding="ascii")
    return fingerprint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        print(export(refresh=args.refresh))
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

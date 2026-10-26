"""Create the XEON API key file without ever printing the key.

    uv run python scripts/create_api_key.py

The key is written to secrets/xeon_api_key.txt (ignored by Git). The CLI and the API read the same
file, so nothing is passed as an argument or environment variable. Use --rotate to replace it.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import secrets
import sys
from pathlib import Path

DEFAULT_FILE = Path("secrets/xeon_api_key.txt")


def create_api_key(path: Path, *, rotate: bool = False) -> bool:
    """Write a new random key; return False when one exists and rotate was not requested."""
    if "secrets" not in path.resolve().parts:
        raise ValueError("La clave de API debe guardarse dentro de secrets/.")
    if path.exists() and path.read_text(encoding="utf-8").strip() and not rotate:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secrets.token_urlsafe(32) + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)  # Best effort: Windows ACLs differ.
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--rotate", action="store_true", help="Reemplaza una clave existente")
    args = parser.parse_args(argv)
    if not create_api_key(args.file, rotate=args.rotate):
        print(f"{args.file} ya existe; usa --rotate para reemplazarla.", file=sys.stderr)
        return 1
    print(f"Clave de API guardada en {args.file}. No se muestra; el CLI la lee de ese archivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

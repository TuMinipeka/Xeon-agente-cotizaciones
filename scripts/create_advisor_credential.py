"""Create or replace an advisor panel credential without exposing the password.

Run it yourself in a terminal: the password is typed at a hidden prompt, only its PBKDF2 hash
is written to the credentials file under secrets/, and nothing is printed back.

    uv run python scripts/create_advisor_credential.py asesor1
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import os
import re
import sys
from pathlib import Path

from xeon.api.panel_auth import MAX_PASSWORD_LENGTH, hash_password

DEFAULT_FILE = Path("secrets/advisor_panel_credentials.txt")
MIN_LENGTH = 12
USERNAME = re.compile(r"[a-z0-9._-]{3,32}")


def upsert_credential(path: Path, username: str, stored_hash: str) -> None:
    """Write `username:hash`, replacing an earlier line for the same user."""
    if "secrets" not in path.parts:
        raise ValueError("El archivo de credenciales debe estar dentro de secrets/.")
    user = username.strip().lower()
    if not USERNAME.fullmatch(user):
        raise ValueError("Usuario invalido: 3 a 32 caracteres a-z, 0-9, punto, guion.")
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        kept = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and line.split(":", 1)[0].strip().lower() != user
        ]
    kept.append(f"{user}:{stored_hash}")
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)  # Best effort: Windows ACLs differ.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args(argv)
    password = getpass.getpass("Contrasena del asesor: ")
    if len(password) < MIN_LENGTH:
        print(f"La contrasena debe tener al menos {MIN_LENGTH} caracteres.", file=sys.stderr)
        return 1
    if len(password) > MAX_PASSWORD_LENGTH:
        print(f"La contrasena admite hasta {MAX_PASSWORD_LENGTH} caracteres.", file=sys.stderr)
        return 1
    if getpass.getpass("Repite la contrasena: ") != password:
        print("Las contrasenas no coinciden.", file=sys.stderr)
        return 1
    upsert_credential(args.file, args.username, hash_password(password))
    print(f"Credencial guardada para {args.username.strip().lower()} en {args.file}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

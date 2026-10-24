"""Register and maintain XEON's Kapso WhatsApp webhook."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path
from typing import TextIO
from urllib.parse import quote, urlsplit

import httpx

DEFAULT_BASE_URL = "https://api.kapso.ai"
DEFAULT_SECRET_FILE = "secrets/kapso_webhook_secret.txt"
WEBHOOK_PATH = "/v1/channels/whatsapp/kapso/webhook"
CONFIG_NAMES = {"KAPSO_API_KEY", "KAPSO_API_BASE_URL", "KAPSO_WEBHOOK_SECRET_FILE"}
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+\Z")


def _dotenv_values(path: Path) -> dict[str, str]:
    """Read only the three settings used here; never expose file contents."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        name, separator, value = line.strip().partition("=")
        name = name.removeprefix("export ").strip()
        if separator and name in CONFIG_NAMES:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name] = value
    return values


def _setting(name: str, env: dict[str, str], dotenv: dict[str, str], default: str = "") -> str:
    return env.get(name) or dotenv.get(name) or default


def _https_url(raw: str, *, webhook: bool = False) -> str:
    parts = urlsplit(raw)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Se requiere una URL HTTPS valida sin credenciales, query ni fragmento.")
    if webhook and parts.path != WEBHOOK_PATH:
        raise ValueError("La URL debe apuntar al endpoint webhook de Kapso de XEON.")
    if not webhook and parts.path not in ("", "/"):
        raise ValueError("KAPSO_API_BASE_URL debe contener solo el origen HTTPS.")
    return raw.rstrip("/")


def _id(raw: str) -> str:
    if not SAFE_ID.fullmatch(raw):
        raise ValueError("El identificador solo admite letras, numeros, guiones y guion bajo.")
    return quote(raw, safe="")


def _write_secret(path: Path, secret: str, *, rotate: bool) -> None:
    if path.is_symlink():
        raise ValueError("La ruta del secreto no puede ser un enlace simbolico.")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if rotate else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(secret + "\n")


def _response_id(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    for candidate in (data, data.get("data"), data.get("whatsapp_webhook")):
        if isinstance(candidate, dict):
            nested = candidate.get("whatsapp_webhook", candidate)
            if isinstance(nested, dict):
                value = nested.get("id")
                if isinstance(value, str) and SAFE_ID.fullmatch(value):
                    return value
    return None


def _webhook_rows(data: object) -> list[dict[str, object]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("whatsapp_webhooks", "data", "webhooks"):
            rows = data.get(key)
            if isinstance(rows, list):
                return _webhook_rows(rows)
            if isinstance(rows, dict):
                return _webhook_rows(rows)
    return []


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administra el webhook de Kapso para XEON.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--phone-number-id", required=True)
    create.add_argument("--url", required=True)
    create.add_argument("--rotate-secret", action="store_true")
    update = commands.add_parser("update-url")
    update.add_argument("--webhook-id", required=True)
    update.add_argument("--url", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--phone-number-id", required=True)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    client: httpx.Client | None = None,
    environ: dict[str, str] | None = None,
    env_file: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = _parser().parse_args(argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    try:
        env = dict(os.environ) if environ is None else environ
        dotenv = _dotenv_values(Path(".env") if env_file is None else env_file)
        api_key = _setting("KAPSO_API_KEY", env, dotenv)
        if not api_key:
            raise ValueError("Falta KAPSO_API_KEY.")
        base = _https_url(_setting("KAPSO_API_BASE_URL", env, dotenv, DEFAULT_BASE_URL))
        webhook_url = _https_url(args.url, webhook=True) if args.command != "list" else ""
        path = (
            f"/platform/v1/whatsapp/webhooks/{_id(args.webhook_id)}"
            if args.command == "update-url"
            else f"/platform/v1/whatsapp/phone_numbers/{_id(args.phone_number_id)}/webhooks"
        )
        payload: dict[str, object] | None = None
        if args.command == "create":
            secret_path = Path(
                _setting("KAPSO_WEBHOOK_SECRET_FILE", env, dotenv, DEFAULT_SECRET_FILE)
            )
            if secret_path.exists() and not args.rotate_secret:
                raise ValueError("El archivo de secreto ya existe; use --rotate-secret.")
            secret = secrets.token_hex(32)
            _write_secret(secret_path, secret, rotate=args.rotate_secret)
            payload = {
                "whatsapp_webhook": {
                    "url": webhook_url,
                    "events": ["whatsapp.message.received"],
                    "kind": "kapso",
                    "payload_version": "v2",
                    "buffer_enabled": False,
                    "active": True,
                    "secret_key": secret,
                }
            }
        elif args.command == "update-url":
            payload = {"whatsapp_webhook": {"url": webhook_url}}

        owns_client = client is None
        if client is None:
            client = httpx.Client(timeout=15, follow_redirects=False)
        try:
            response = client.request(
                {"create": "POST", "update-url": "PATCH", "list": "GET"}[args.command],
                base + path,
                headers={"X-API-Key": api_key},
                json=payload,
                follow_redirects=False,
            )
        finally:
            if owns_client:
                client.close()
        print(f"HTTP {response.status_code}", file=out)
        if 300 <= response.status_code < 400:
            print("Kapso devolvio una redireccion; operacion rechazada.", file=err)
            return 1
        if response.is_error:
            return 1
        try:
            data = response.json()
        except ValueError:
            data = None
        if args.command == "create":
            webhook_id = _response_id(data)
            if webhook_id:
                print(f"webhook_id: {webhook_id}", file=out)
        elif args.command == "list":
            for row in _webhook_rows(data):
                identifier = row.get("id")
                url = row.get("url")
                active = row.get("active")
                events = row.get("events")
                if isinstance(identifier, str) and SAFE_ID.fullmatch(identifier):
                    if not isinstance(url, str) or not url.startswith("https://"):
                        url = ""
                    if not isinstance(events, list):
                        events = []
                    safe_events = [event for event in events if isinstance(event, str)]
                    fields = (identifier, url, str(active is True), ",".join(safe_events))
                    print("\t".join(fields), file=out)
        return 0
    except FileExistsError:
        print("El archivo de secreto ya existe; use --rotate-secret.", file=err)
    except OSError, httpx.HTTPError:
        print("No se pudo completar la operacion de Kapso.", file=err)
    except ValueError as exc:
        print(exc, file=err)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

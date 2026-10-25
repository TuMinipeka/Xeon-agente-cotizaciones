"""Set the permitted Grok entries in the local .env without displaying secrets."""

from __future__ import annotations

import re
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_BOM = b"\xef\xbb\xbf"
_TARGETS = {
    "LLM_PROVIDER": "grok",
    "GROK_MODEL": "grok-4.6",
    "GROK_BASE_URL": "https://api.reto.pltk.mx/v1",
    "GROK_API_KEY_FILE": "secrets/grok_api_key.txt",
}
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")
_ASSIGNMENT = re.compile(
    r"^(?P<prefix>[ \t]*(?:export[ \t]+)?)(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<equals>[ \t]*=[ \t]*)(?P<value>[^\r\n]*)(?P<ending>\r\n|\n|\r)?$"
)


def main() -> None:
    original = _ENV_PATH.read_bytes() if _ENV_PATH.exists() else b""
    had_bom = original.startswith(_BOM)
    try:
        content = original.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SystemExit("No se pudo decodificar .env como UTF-8.") from exc

    newline = "\r\n" if "\r\n" in content else "\n"
    lines = content.splitlines(keepends=True)
    seen: set[str] = set()
    changed: dict[str, str] = {}

    for index, line in enumerate(lines):
        match = _ASSIGNMENT.fullmatch(line)
        if match is None:
            continue
        name = match.group("name").upper()
        if name in _TARGETS:
            replacement = _TARGETS[name]
        elif name == "GROK_API_KEY" and match.group("value").strip():
            replacement = ""
        else:
            continue

        seen.add(name)
        if match.group("value") == replacement:
            continue
        lines[index] = (
            f"{match.group('prefix')}{match.group('name')}{match.group('equals')}"
            f"{replacement}{match.group('ending') or ''}"
        )
        changed[name] = replacement

    if "LLM_PROVIDER" not in seen:
        if lines and not lines[-1].endswith(("\r", "\n")):
            lines.append(newline)
        lines.append(f"LLM_PROVIDER=grok{newline}")
        changed["LLM_PROVIDER"] = "grok"

    if changed:
        encoded = "".join(lines).encode("utf-8")
        _ENV_PATH.write_bytes((_BOM if had_bom else b"") + encoded)

    for name, value in changed.items():
        if any(marker in name for marker in _SECRET_MARKERS):
            print(name)
        else:
            print(f"{name}={value}")


if __name__ == "__main__":
    main()

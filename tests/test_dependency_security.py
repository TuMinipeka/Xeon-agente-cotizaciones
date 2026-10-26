"""Regression guards for dependency advisories found in the 2026-10-26 security review."""

from __future__ import annotations

import re
from pathlib import Path


def _locked_version(name: str) -> tuple[int, ...]:
    text = Path("uv.lock").read_text(encoding="utf-8")
    match = re.search(rf'name = "{re.escape(name)}"\nversion = "([0-9.]+)"', text)
    assert match, name
    return tuple(int(part) for part in match.group(1).split("."))


def test_certifi_is_past_the_revoked_emsign_root_advisory() -> None:
    # PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2: fixed in 2026.10.18-19.
    assert _locked_version("certifi") >= (2026, 10, 19)

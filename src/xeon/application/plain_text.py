"""Shared plain-text presentation for every customer-facing channel."""

from __future__ import annotations

import re


def plain_text(text: str, *, max_length: int | None = None) -> str:
    plain = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"(?m)^\s*[-*+]\s+", "• ", plain)
    plain = re.sub(r"(?m)^\s*\d+[.)]\s+", "• ", plain)
    plain = re.sub(
        r"\*\*([^*]+)\*\*|__([^_]+)__",
        lambda match: match.group(1) or match.group(2) or "",
        plain,
    )
    plain = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", plain)
    plain = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", plain)
    plain = re.sub(r"(?m)^\s*>\s?", "", plain)
    plain = plain.replace("```", "").replace("`", "")
    plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
    if max_length is None or len(plain) <= max_length:
        return plain
    clipped = plain[: max_length - 1].rsplit("\n", 1)[0]
    if len(clipped) < max_length // 2:
        clipped = plain[: max_length - 1]
    return clipped.rstrip() + "…"

"""Compact plain-text formatting for outbound WhatsApp messages."""

from __future__ import annotations

import re


class WhatsAppFormatter:
    def __init__(self, *, max_length: int = 1500) -> None:
        if max_length < 80:
            raise ValueError("El limite de mensaje debe permitir una respuesta util.")
        self._max_length = max_length

    def format(self, text: str) -> str:
        plain = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        plain = re.sub(r"(?m)^\s*[-*+]\s+", "• ", plain)
        plain = re.sub(r"(?m)^\s*\d+[.)]\s+", "• ", plain)
        plain = re.sub(
            r"\*\*([^*]+)\*\*|__([^_]+)__",
            lambda match: match.group(1) or match.group(2) or "",
            plain,
        )
        plain = plain.replace("```", "").replace("`", "")
        plain = re.sub(r"\n{3,}", "\n\n", plain).strip()
        if len(plain) <= self._max_length:
            return plain
        clipped = plain[: self._max_length - 1].rsplit("\n", 1)[0]
        if len(clipped) < self._max_length // 2:
            clipped = plain[: self._max_length - 1]
        return clipped.rstrip() + "…"

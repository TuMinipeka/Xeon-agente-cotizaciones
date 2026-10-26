"""Compact plain-text formatting for outbound WhatsApp messages."""

from __future__ import annotations

from xeon.application.plain_text import plain_text


class WhatsAppFormatter:
    def __init__(self, *, max_length: int = 1500) -> None:
        if max_length < 80:
            raise ValueError("El limite de mensaje debe permitir una respuesta util.")
        self._max_length = max_length

    def format(self, text: str) -> str:
        return plain_text(text, max_length=self._max_length)

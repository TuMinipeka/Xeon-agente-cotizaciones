"""Channel-neutral guided response and WhatsApp option limits."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Option:
    id: str
    title: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.title.strip():
            raise ValueError("Option id and title are required.")


@dataclass(frozen=True, slots=True)
class Reply:
    text: str
    kind: Literal["text", "buttons", "list"] = "text"
    options: tuple[Option, ...] = ()
    step: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Reply text is required.")
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Option ids must be unique.")
        if self.kind == "buttons" and not (1 <= len(self.options) <= 3):
            raise ValueError("Buttons require 1 to 3 options.")
        if self.kind == "list" and not (1 <= len(self.options) <= 10):
            raise ValueError("Lists require 1 to 10 rows.")
        if self.kind == "text" and self.options:
            raise ValueError("Text reply cannot have options.")
        limit = 20 if self.kind == "buttons" else 24
        if any(len(option.title) > limit for option in self.options):
            raise ValueError("Option title exceeds WhatsApp limit.")

    def numbered(self) -> str:
        if not self.options:
            return self.text
        choices = "\n".join(
            f"{index}. {option.title} [{option.id}]" for index, option in enumerate(self.options, 1)
        )
        return f"{self.text}\n{choices}"

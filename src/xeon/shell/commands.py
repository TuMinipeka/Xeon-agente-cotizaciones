from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandName = Literal["run", "status", "config", "logs", "new", "help", "quit"]

ALIASES: dict[str, CommandName] = {
    "run": "run",
    "r": "run",
    "status": "status",
    "s": "status",
    "config": "config",
    "c": "config",
    "logs": "logs",
    "l": "logs",
    "new": "new",
    "n": "new",
    "help": "help",
    "h": "help",
    "?": "help",
    "quit": "quit",
    "q": "quit",
    "exit": "quit",
}


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    name: CommandName
    argument: str = ""


def parse_command(line: str) -> ParsedCommand | None:
    stripped = line.strip()
    if not stripped:
        return None
    parts = stripped.split(maxsplit=1)
    head = parts[0]
    tail = parts[1] if len(parts) == 2 else ""
    name = ALIASES.get(head.casefold())
    if name is None:
        return ParsedCommand("run", stripped)
    return ParsedCommand(name, tail.strip())

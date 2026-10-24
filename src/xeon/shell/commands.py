from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CommandName = Literal["run", "status", "config", "logs", "new", "help", "quit", "invalid", "usage"]

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


_NO_ARGUMENTS = frozenset({"status", "config", "new", "help", "quit"})


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, start=1):
        current = [index]
        for column, other in enumerate(right, start=1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (char != other))
            )
        previous = current
    return previous[-1]


def parse_command(line: str) -> ParsedCommand | None:
    stripped = line.strip()
    if not stripped:
        return None
    parts = stripped.split(maxsplit=1)
    head = parts[0]
    tail = parts[1] if len(parts) == 2 else ""
    name = ALIASES.get(head.casefold())
    if name is None:
        if head.startswith(("/", ":")) or not tail:
            candidate = head.lstrip("/:").casefold()
            nearest = min(
                ALIASES, key=lambda alias: (_edit_distance(candidate, alias), -len(alias))
            )
            if head.startswith(("/", ":")) or _edit_distance(candidate, nearest) <= 2:
                return ParsedCommand("invalid", nearest)
        return ParsedCommand("run", stripped)
    if name in _NO_ARGUMENTS and tail.strip():
        return ParsedCommand("usage", name)
    return ParsedCommand(name, tail.strip())

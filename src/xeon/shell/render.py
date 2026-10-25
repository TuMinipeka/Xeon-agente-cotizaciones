from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from xeon.shell import theme

if TYPE_CHECKING:
    from xeon.shell.session import Session

_FONT = {
    "X": ("██  ██", " ████ ", "  ██  ", " ████ ", "██  ██"),
    "E": ("██████", "██    ", "█████ ", "██    ", "██████"),
    "O": (" ████ ", "██  ██", "██  ██", "██  ██", " ████ "),
    "N": ("██  ██", "███ ██", "██████", "██ ███", "██  ██"),
    "C": (" █████", "██    ", "██    ", "██    ", " █████"),
    "L": ("██    ", "██    ", "██    ", "██    ", "██████"),
    "I": ("██████", "  ██  ", "  ██  ", "  ██  ", "██████"),
    " ": ("   ",) * 5,
}
_TITLE = "XEON CLI"
_TITLE_COLORS = (
    theme.ACCENT,
    theme.ACCENT,
    theme.ACCENT_MID,
    theme.ACCENT_LOW,
    theme.ACCENT_DIM,
)
_SUBTITLE = "T a c t i c a l   A g e n t   S h e l l"
_COMMANDS = (
    ("run", "r", "Execute agent workflow"),
    ("status", "s", "View agent status"),
    ("config", "c", "View safe configuration"),
    ("logs", "l", "View session logs"),
    ("tools", "t", "View last turn tools"),
    ("new", "n", "Start new conversation"),
    ("help", "h, ?", "Show available commands"),
    ("quit", "q, exit", "Exit shell"),
)


def _version() -> str:
    try:
        return version("xeon")
    except PackageNotFoundError:
        return "0.1.0"


def supports_art(console: Console) -> bool:
    if console.legacy_windows:
        return False
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    try:
        "█▄┌✓".encode(encoding)
    except LookupError, UnicodeEncodeError:
        return False
    return True


def _large_title() -> Text:
    title = Text()
    for row in range(5):
        line = " ".join(_FONT[letter][row] for letter in _TITLE).rstrip()
        title.append(line, style=f"bold {_TITLE_COLORS[row]}")
        if row < 4:
            title.append("\n")
    return title


def _turtle_logo() -> Text:
    cells = [[" "] * 24 for _ in range(12)]

    def span(row: int, left: int, right: int, glyph: str) -> None:
        cells[row][left : right + 1] = [glyph] * (right - left + 1)

    span(0, 10, 13, "▀")
    span(1, 9, 14, "█")
    span(2, 10, 13, "▄")
    span(3, 10, 13, "▓")
    for row, left, right in (
        (3, 7, 16),
        (4, 6, 17),
        (5, 5, 18),
        (6, 5, 18),
        (7, 5, 18),
        (8, 5, 18),
        (9, 6, 17),
    ):
        span(row, left, right, "▓")
        cells[row][left] = cells[row][right] = "█"
    for row, left in ((4, 8), (5, 9), (6, 10), (7, 10), (8, 9), (9, 8)):
        span(row, left, left + 1, "█")
        span(row, 22 - left, 23 - left, "█")
    for row, left, right in ((4, 1, 4), (5, 2, 4), (8, 2, 4), (9, 1, 4)):
        span(row, left, right, "▄" if row in (4, 8) else "█")
        span(row, 23 - right, 23 - left, "▄" if row in (4, 8) else "█")
    span(10, 9, 10, "▄")
    span(10, 13, 14, "▄")
    span(11, 10, 10, "▀")
    span(11, 13, 13, "▀")

    logo = Text()
    for row_index, logo_row in enumerate(cells):
        for glyph in logo_row:
            logo.append(glyph, style=theme.ACCENT_DIM if glyph == "▓" else theme.ACCENT)
        if row_index < len(cells) - 1:
            logo.append("\n")
    return logo


def _commands_table(*, include_tools: bool = True) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(width=8, no_wrap=True)
    table.add_column(width=10, no_wrap=True)
    table.add_column(width=38, no_wrap=True)
    for name, aliases, description in _COMMANDS:
        if name == "tools" and not include_tools:
            continue
        table.add_row(
            Text(name, style=f"bold {theme.ACCENT}"),
            Text(f"/ {aliases}", style=theme.ACCENT_DIM),
            Text(description, style=theme.FG),
        )
    return table


def render_commands(
    width: int, *, plain: bool = False, include_tools: bool = True
) -> RenderableType:
    commands = tuple(item for item in _COMMANDS if include_tools or item[0] != "tools")
    if plain:
        return Text(
            "\n".join(
                f"{name} / {aliases}  {description}" for name, aliases, description in commands
            )
        )
    if width < 60:
        return Text("  ".join(name for name, _, _ in commands), style=theme.ACCENT)
    return Panel(
        _commands_table(include_tools=include_tools),
        title="// AVAILABLE COMMANDS",
        title_align="left",
        border_style=theme.BORDER,
        padding=(0, 1),
        width=min(72, width),
        expand=True,
    )


def _hud_rule(width: int, *, top: bool) -> Text:
    if top:
        prefix, suffix = "┌─", " //// ┐"
    else:
        prefix, suffix = "└─", "┘"
    rule = Text(prefix, style=theme.ACCENT)
    rule.append("─" * (width - len(prefix) - len(suffix)), style=theme.BORDER)
    rule.append(suffix, style=theme.ACCENT)
    return rule


def render_banner(session: Session, width: int, *, plain: bool = False) -> RenderableType:
    profile = f"{session.engine.provider} / {session.engine.model}"
    if plain:
        return Text(
            f"XEON CLI | Tactical Agent Shell\n"
            f"system ready | {_version()} | {profile}\n"
            "run  status  config  logs  new  help  quit"
        )
    if width < 70:
        return Group(
            Text("XEON CLI  |  Tactical Agent Shell", style=theme.ACCENT),
            Text(f"● ready  |  {_version()}  |  {profile}", style=theme.FG_MUTED),
            render_commands(width, include_tools=False),
        )
    ready = Text("● system ready", style=theme.STATUS_OK)
    details = Table.grid(padding=(0, 1))
    details.add_column(style=theme.FG_MUTED, width=8, no_wrap=True)
    details.add_column(style=theme.BORDER, width=1)
    details.add_column(style=theme.FG)
    if width < 100:
        details.add_column(style=theme.FG_MUTED, width=5, no_wrap=True)
        details.add_column(style=theme.BORDER, width=1)
        details.add_column(style=theme.FG)
        details.add_row("version", "│", _version(), "mode", "│", "interactive")
        details.add_row("profile", "│", profile, "", "", "")
    else:
        details.add_row("version", "│", _version())
        details.add_row("mode", "│", "interactive")
        details.add_row("profile", "│", profile)
    system = Panel(
        Group(ready, details),
        border_style=theme.BORDER,
        padding=(0, 1),
        width=min(72, width - 2),
        expand=True,
    )
    title = Group(
        _large_title(),
        Text(_SUBTITLE, style=theme.ACCENT_DIM),
    )
    if width < 100:
        frame_width = min(width, 74)
        body: RenderableType = Group(
            title, system, render_commands(frame_width - 2, include_tools=False)
        )
    else:
        frame_width = min(width, 100)
        right = Group(title, system, render_commands(72, include_tools=False))
        grid = Table.grid(padding=(0, 1), expand=False)
        grid.add_column(width=24, vertical="middle")
        grid.add_column(width=72)
        grid.add_row(_turtle_logo(), right)
        body = grid
    return Group(
        Align.left(_hud_rule(frame_width, top=True), pad=True),
        Align.left(body, width=frame_width, pad=True),
        Align.left(_hud_rule(frame_width, top=False), pad=True),
    )


def render_footer(width: int, *, plain: bool = False) -> Text:
    hints: tuple[tuple[str, str], ...] = (
        ("r", "run"),
        ("s", "status"),
        ("c", "config"),
        ("l", "logs"),
        ("t", "tools"),
        ("h", "help"),
        ("q", "quit"),
    )
    if width < 60:
        hints = (("r", "run"), ("h", "help"), ("q", "quit"))
    footer = Text()
    for index, (key, verb) in enumerate(hints):
        if index:
            footer.append("  ")
        footer.append(key, style=None if plain else f"bold {theme.ACCENT}")
        footer.append(f" {verb}", style=None if plain else theme.FG_MUTED)
    return footer


def render_prompt(*, plain: bool = False) -> Text:
    return Text("xeon > ", style="" if plain else f"bold {theme.ACCENT}")


def render_status(session: Session, *, plain: bool = False) -> RenderableType:
    if plain:
        return Text(
            f"provider: {session.engine.provider}\nmodel: {session.engine.model}\n"
            f"base URL: {session.engine.base_url}\nkey: {session.key_status}\n"
            f"conversation: {session.conversation_id}\nturns: {session.turns}"
        )
    table = Table.grid(padding=(0, 2))
    table.add_column(style=theme.FG_MUTED)
    table.add_column(style=theme.FG)
    table.add_row("provider", session.engine.provider)
    table.add_row("model", session.engine.model)
    table.add_row("base URL", session.engine.base_url)
    table.add_row("key", session.key_status)
    table.add_row("conversation", str(session.conversation_id))
    table.add_row("turns", str(session.turns))
    return Panel(table, title="// STATUS", title_align="left", border_style=theme.BORDER)


def render_config(session: Session, *, plain: bool = False) -> RenderableType:
    if plain:
        return Text(
            f"provider: {session.engine.provider}\nmodel: {session.engine.model}\n"
            f"base URL: {session.engine.base_url}\nAPI key: {session.key_status}"
        )
    table = Table.grid(padding=(0, 2))
    table.add_column(style=theme.FG_MUTED)
    table.add_column(style=theme.FG)
    table.add_row("provider", session.engine.provider)
    table.add_row("model", session.engine.model)
    table.add_row("base URL", session.engine.base_url)
    table.add_row("API key", session.key_status)
    return Panel(table, title="// CONFIG", title_align="left", border_style=theme.BORDER)


def render_logs(session: Session, count: int, *, plain: bool = False) -> RenderableType:
    if plain:
        rows = [
            f"{entry.at:%H:%M:%S} {entry.command} {entry.provider} "
            f"{entry.latency_ms}ms {entry.result}"
            for entry in list(session.logs)[-count:]
        ]
        return Text("\n".join(rows) if rows else "No session logs yet.")
    table = Table(show_header=True, header_style=theme.ACCENT, box=None)
    table.add_column("UTC")
    table.add_column("Command")
    table.add_column("Provider")
    table.add_column("Latency", justify="right")
    table.add_column("Result")
    for entry in list(session.logs)[-count:]:
        glyph = {"ok": "✓", "warn": "▲", "error": "✕"}[entry.result]
        color = {
            "ok": theme.STATUS_OK,
            "warn": theme.STATUS_WARN,
            "error": theme.STATUS_ERROR,
        }[entry.result]
        table.add_row(
            entry.at.strftime("%H:%M:%S"),
            entry.command,
            entry.provider,
            f"{entry.latency_ms} ms",
            Text(f"{glyph} {entry.result}", style=color),
        )
    return table if session.logs else Text("No session logs yet.", style=theme.FG_MUTED)


def render_reply(reply: str, *, plain: bool = False) -> Text:
    return Text(reply, style="" if plain else theme.FG)


def render_error(message: str, *, plain: bool = False) -> Text:
    return Text(
        f"{'error:' if plain else '✕'} {message}",
        style="" if plain else theme.STATUS_ERROR,
    )

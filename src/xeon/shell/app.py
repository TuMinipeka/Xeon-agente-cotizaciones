from __future__ import annotations

import sys
from collections.abc import Callable
from time import perf_counter

from rich.console import Console
from rich.text import Text

from xeon.shell import theme
from xeon.shell.commands import ParsedCommand, parse_command
from xeon.shell.render import (
    render_banner,
    render_config,
    render_error,
    render_footer,
    render_logs,
    render_prompt,
    render_reply,
    render_status,
    supports_art,
)
from xeon.shell.session import Session


async def run_shell(
    session: Session,
    *,
    console: Console,
    read_line: Callable[[], str] = input,
    stdin_is_tty: bool | None = None,
) -> int:
    """Own the line-oriented terminal lifecycle, including engine cleanup."""
    interactive = sys.stdin.isatty() if stdin_is_tty is None else stdin_is_tty
    plain = not console.is_terminal or not supports_art(console)
    try:
        if interactive:
            console.print(render_banner(session, console.width, plain=plain))
            console.print(render_footer(console.width, plain=plain))
        while True:
            if interactive:
                console.print(render_prompt(plain=plain), end="")
            try:
                line = read_line()
            except EOFError:
                if interactive:
                    console.print()
                return 0
            except KeyboardInterrupt:
                if interactive:
                    console.print()
                return 130
            command = parse_command(line)
            if command is None:
                continue
            if command.name == "quit":
                return 0
            try:
                await _execute(command, session, console)
            except KeyboardInterrupt:
                if interactive:
                    console.print()
                return 130
    finally:
        await session.engine.aclose()


async def _execute(command: ParsedCommand, session: Session, console: Console) -> None:
    started = perf_counter()
    plain = not console.is_terminal or not supports_art(console)
    if command.name == "run":
        if not command.argument:
            session.record("run", "warn", started)
            console.print(render_error("Uso: run <mensaje>", plain=plain))
            return
        try:
            reply = await session.run(command.argument)
        except Exception:
            console.print(render_error("No fue posible obtener respuesta del agente.", plain=plain))
            return
        console.print(render_reply(reply, plain=plain))
        return
    if command.name == "status":
        session.record("status", "ok", started)
        console.print(render_status(session, plain=plain))
    elif command.name == "config":
        session.record("config", "ok", started)
        console.print(render_config(session, plain=plain))
    elif command.name == "new":
        session.new()
        session.record("new", "ok", started)
        marker = "OK" if plain else "✓"
        console.print(
            Text(f"{marker} Nueva conversacion lista.", style="" if plain else theme.STATUS_OK)
        )
    elif command.name == "help":
        session.record("help", "ok", started)
        from xeon.shell.render import render_commands

        if plain:
            console.print(render_banner(session, console.width, plain=True))
        else:
            console.print(render_commands(console.width))
        console.print(render_footer(console.width, plain=plain))
    elif command.name == "logs":
        if command.argument:
            try:
                count = int(command.argument)
            except ValueError:
                count = 0
            if not 1 <= count <= 100:
                session.record("logs", "warn", started)
                console.print(render_error("Uso: logs [N], con N entre 1 y 100.", plain=plain))
                return
        else:
            count = 20
        session.record("logs", "ok", started)
        console.print(render_logs(session, count, plain=plain))

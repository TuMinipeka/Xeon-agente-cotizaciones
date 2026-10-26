from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from rich.console import Console
from typer.testing import CliRunner

from xeon.cli import app
from xeon.config import Settings
from xeon.shell.app import run_shell
from xeon.shell.commands import parse_command
from xeon.shell.render import (
    _large_title,
    _turtle_logo,
    render_banner,
    render_config,
    render_footer,
    render_prompt,
)
from xeon.shell.session import HTTPEngine, InProcessEngine, Session, key_status


def _console(width: int = 80) -> tuple[Console, StringIO]:
    output = StringIO()
    return (
        Console(
            file=output,
            record=True,
            width=width,
            force_terminal=False,
            force_interactive=False,
            color_system=None,
            no_color=True,
            legacy_windows=False,
        ),
        output,
    )


def _mock_session() -> Session:
    return Session(InProcessEngine(Settings(llm_provider="mock", _env_file=None)), "not required")


def test_aliases_and_free_text_are_pure() -> None:
    expected = {
        "r hola": ("run", "hola"),
        "status": ("status", ""),
        "s": ("status", ""),
        "c": ("config", ""),
        "l 3": ("logs", "3"),
        "tools": ("tools", ""),
        "t": ("tools", ""),
        "n": ("new", ""),
        "?": ("help", ""),
        "h": ("help", ""),
        "q": ("quit", ""),
        "exit": ("quit", ""),
        "Necesito cemento": ("run", "Necesito cemento"),
    }
    for line, result in expected.items():
        command = parse_command(line)
        assert command is not None
        assert (command.name, command.argument) == result
    assert parse_command("  ") is None


@pytest.mark.parametrize("width", [120, 80, 50])
def test_banner_renders_by_width(width: int) -> None:
    console, output = _console(width)
    console.print(render_banner(_mock_session(), width))
    console.print(render_footer(width))
    text = output.getvalue()
    if width < 70:
        assert "XEON CLI" in text
        assert "Tactical Agent Shell" in text
    else:
        assert "█" in text
        assert "T a c t i c a l   A g e n t   S h e l l" in text
    assert "mock" in text
    assert "run" in text
    assert "\x1b[" not in text
    for line in text.splitlines():
        assert len(line) <= width
    if width == 120:
        assert "▓" in text
        assert "AVAILABLE COMMANDS" in text
    elif width == 80:
        assert "AVAILABLE COMMANDS" in text
    else:
        assert "AVAILABLE COMMANDS" not in text


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (120, 25),
        (80, 24),
    ],
)
def test_banner_text_snapshot(width: int, height: int) -> None:
    console, output = _console(width)
    console.print(render_banner(_mock_session(), width))
    console.print(render_footer(width))
    console.print(render_prompt(), end="")
    text = output.getvalue()
    lines = text.splitlines()
    assert len(lines) == height
    assert all(len(line) == width for line in lines[: height - 2])
    assert len(lines[-2]) == 58
    assert lines[-1] == "xeon > "
    snapshot = Path(__file__).parent / "snapshots" / f"banner_{width}x{height}.txt"
    assert text == snapshot.read_text(encoding="utf-8")


def test_cp1252_legacy_console_uses_plain_ascii() -> None:
    class Cp1252Output(StringIO):
        @property
        def encoding(self) -> str:
            return "cp1252"

        def write(self, value: str) -> int:
            value.encode("cp1252")
            return super().write(value)

    output = Cp1252Output()
    console = Console(file=output, width=80, force_terminal=True, legacy_windows=True)
    code = run_shell(_mock_session(), console=console, read_line=lambda: "quit", stdin_is_tty=True)
    assert code == 0
    assert "XEON CLI | Tactical Agent Shell" in output.getvalue()
    assert "xeon > " in output.getvalue()
    assert output.getvalue().isascii()
    assert "\x1b[" not in output.getvalue()


def test_turtle_logo_is_symmetric_single_cell_art() -> None:
    rows = _turtle_logo().plain.splitlines()
    assert len(rows) == 12
    assert all(len(row) == 24 and row == row[::-1] for row in rows)
    assert any("▓" in row for row in rows)
    assert rows[6][10:14] == "████"
    assert rows[4][8:10] == rows[4][14:16] == "██"


@pytest.mark.parametrize("width", [120, 80])
def test_command_descriptions_begin_in_one_column(width: int) -> None:
    console, output = _console(width)
    console.print(render_banner(_mock_session(), width))
    descriptions = (
        "Execute agent workflow",
        "View agent status",
        "View safe configuration",
        "View session logs",
        "Start new conversation",
        "Show available commands",
        "Exit shell",
    )
    lines = output.getvalue().splitlines()
    starts = [
        next(line.index(description) for line in lines if description in line)
        for description in descriptions
    ]
    assert len(set(starts)) == 1


def test_title_gradient_and_prompt_use_accent_styles() -> None:
    title = _large_title()
    assert len(title.plain.splitlines()) == 5
    assert "▀" not in title.plain and "▄" not in title.plain
    styles = [str(span.style) for span in title.spans]
    assert len(styles) == 5
    assert "#00f5b0" in styles[0]
    assert "#008d73" in styles[-1]
    assert "bold" in str(render_prompt().style)
    assert render_prompt(plain=True).style is None or str(render_prompt(plain=True).style) == ""


def test_shell_run_new_logs_and_config_hide_secrets() -> None:
    session = _mock_session()
    old_id = session.conversation_id
    console, output = _console()
    commands = iter(
        [
            "r start:products",
            "r cemento",
            "r product:CEM-50",
            "r quantity:other",
            "r 2",
            "status",
            "config",
            "logs 4",
            "new",
            "s",
            "quit",
        ]
    )
    code = run_shell(session, console=console, read_line=lambda: next(commands), stdin_is_tty=False)
    text = output.getvalue()
    assert code == 0
    assert "Cemento gris" in text
    assert "mock-xeon-v1" in text
    assert "not required" in text
    assert "run" in text and "logs" in text
    assert session.conversation_id != old_id
    assert session.turns == 0
    assert "API key" in text
    assert "secret" not in text.casefold()


def test_tools_command_shows_last_turn_and_new_clears_it() -> None:
    session = _mock_session()
    console, output = _console()
    lines = iter(
        [
            "r start:products",
            "r cemento",
            "r product:CEM-50",
            "r quantity:other",
            "r 2",
            "tools",
            "r more:view",
            "r delivery:pickup",
            "r branch:sede-norte",
            "tools",
            "new",
            "t",
            "quit",
        ]
    )

    assert (
        run_shell(session, console=console, read_line=lambda: next(lines), stdin_is_tty=False) == 0
    )

    shown = output.getvalue()
    assert "TOOL search_products status=exact_match sku=CEM-50" in shown
    assert "TOOL get_stock_by_branches sku=CEM-50" in shown
    assert "TOOL create_quote_draft quote_id=" in shown
    assert "Sin herramientas en el ultimo turno." in shown
    assert session.last_tools == ()


def test_shell_uses_same_conversation_for_multiple_mock_turns() -> None:
    session = _mock_session()
    conversation_id: UUID = session.conversation_id
    console, output = _console()
    commands = iter(
        [
            "start:products",
            "tubo pvc de 1/2 pulgada",
            "product:TUB-PVC-20",
            "quantity:other",
            "5",
            "q",
        ]
    )
    code = run_shell(session, console=console, read_line=lambda: next(commands), stdin_is_tty=False)
    assert code == 0
    assert session.conversation_id == conversation_id
    assert session.turns == 5
    assert "Tubo PVC" in output.getvalue()
    assert "$21.000" in output.getvalue()


def test_shell_eof_and_ctrl_c_exit_codes() -> None:
    def eof() -> str:
        raise EOFError

    def interrupt() -> str:
        raise KeyboardInterrupt

    for reader, expected in ((eof, 0), (interrupt, 130), (lambda: "\x03", 130)):
        console, _ = _console()
        code = run_shell(_mock_session(), console=console, read_line=reader, stdin_is_tty=False)
        assert code == expected


@pytest.mark.parametrize("line", ["statu", "quitt", "helpp", "confg", "/status", ":status"])
def test_mistyped_command_never_calls_engine(line: str) -> None:
    session = _mock_session()
    console, output = _console()
    lines = iter([line, "quit"])
    assert (
        run_shell(session, console=console, read_line=lambda: next(lines), stdin_is_tty=False) == 0
    )
    assert session.turns == 0
    assert "Comando no valido" in output.getvalue()
    assert "Quisiste decir" in output.getvalue()


@pytest.mark.parametrize("line", ["1", "2", "3", "opcion 2", "opción 3", "la 2"])
def test_numeric_choices_are_sent_to_engine(line: str) -> None:
    parsed = parse_command(line)
    assert parsed is not None
    assert (parsed.name, parsed.argument) == ("run", line)

    session = _mock_session()
    console, output = _console()
    lines = iter([line, "quit"])
    assert (
        run_shell(session, console=console, read_line=lambda: next(lines), stdin_is_tty=False) == 0
    )
    assert session.turns == 1
    assert "Comando no valido" not in output.getvalue()


@pytest.mark.parametrize(
    "line", ["status foo", "config bar", "tools extra", "new 123", "help extra", "quit ahora"]
)
def test_no_argument_commands_show_usage_without_running(line: str) -> None:
    session = _mock_session()
    console, output = _console()
    lines = iter([line, "quit"])
    assert (
        run_shell(session, console=console, read_line=lambda: next(lines), stdin_is_tty=False) == 0
    )
    assert session.turns == 0
    assert "Uso:" in output.getvalue()


def test_distant_free_text_still_runs() -> None:
    session = _mock_session()
    console, _ = _console()
    lines = iter(["cemento", "necesito cemento", "quit"])
    assert (
        run_shell(session, console=console, read_line=lambda: next(lines), stdin_is_tty=False) == 0
    )
    assert session.turns == 2


def test_plain_help_lists_commands_without_banner() -> None:
    console, output = _console()
    lines = iter(["help", "quit"])
    assert (
        run_shell(
            _mock_session(), console=console, read_line=lambda: next(lines), stdin_is_tty=False
        )
        == 0
    )
    assert "run / r" in output.getvalue()
    assert "tools / t" in output.getvalue()
    assert "q quit" in output.getvalue()
    assert "XEON CLI" not in output.getvalue()
    assert "system ready" not in output.getvalue()


def test_cli_no_color_and_piped_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    result = CliRunner().invoke(app, [], input="status\nquit\n")
    assert result.exit_code == 0
    assert "provider" in result.stdout
    assert "mock" in result.stdout
    assert "XEON CLI" not in result.stdout
    assert "xeon >" not in result.stdout
    assert "\x1b[" not in result.stdout


def test_http_engine_uses_health_profile_and_conversation_id_without_network() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"provider": "grok", "model": "grok-test"})
        assert request.url.path == "/v1/chat"
        return httpx.Response(
            200,
            json={"provider": "grok", "model": "grok-test", "reply": "Respuesta remota"},
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            engine = HTTPEngine(
                "http://test", Settings(llm_provider="mock", _env_file=None), client=client
            )
            await engine.refresh()
            assert (engine.provider, engine.model) == ("grok", "grok-test")
            reply = await engine.run("hola", UUID("00000000-0000-0000-0000-000000000001"))
            assert reply == "Respuesta remota"

    asyncio.run(run())
    assert [request.url.path for request in requests] == ["/health", "/v1/chat"]
    assert b"00000000-0000-0000-0000-000000000001" in requests[1].content


def test_config_masks_key_and_detects_missing_file(tmp_path: Path) -> None:
    settings = Settings(
        llm_provider="grok",
        grok_api_key=SecretStr("dummy-private-value"),
        grok_api_key_file=None,
        _env_file=None,
    )
    assert key_status(settings) == "configured"
    engine = HTTPEngine("http://test", settings)
    session = Session(engine, key_status(settings))
    console, output = _console()
    console.print(render_config(session, plain=True))
    assert "configured" in output.getvalue()
    assert "dummy-private-value" not in output.getvalue()
    asyncio.run(engine.aclose())

    missing = Settings(
        llm_provider="grok",
        grok_api_key=None,
        grok_api_key_file=tmp_path / "absent.txt",
        _env_file=None,
    )
    assert key_status(missing) == "missing"

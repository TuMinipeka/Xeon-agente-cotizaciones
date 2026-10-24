from __future__ import annotations

import json
import os
import sys
from typing import Annotated

import httpx
import typer
from rich.console import Console

from xeon.config import Settings, SettingsError
from xeon.shell.app import run_shell
from xeon.shell.session import HTTPEngine, InProcessEngine, Session, key_status

app = typer.Typer(help="XEON Tactical Agent Shell.", invoke_without_command=True)
quotes_app = typer.Typer(help="Revisar borradores sinteticos. No aprueba ni emite.")
stock_app = typer.Typer(help="Consultar disponibilidad sintetica por sede. No reserva stock.")
app.add_typer(quotes_app, name="quotes")
app.add_typer(stock_app, name="stock")


@app.callback()
def main(
    ctx: typer.Context,
    api: Annotated[str | None, typer.Option("--api", help="Usar una API XEON remota.")] = None,
) -> None:
    """Abre el shell si no se invoca un subcomando."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        settings = Settings()
        engine = HTTPEngine(api, settings) if api is not None else InProcessEngine(settings)
    except SettingsError as exc:
        typer.echo(f"xeon: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo("xeon: no se pudo iniciar el motor.", err=True)
        raise typer.Exit(code=1) from exc
    session = Session(engine=engine, key_status=key_status(settings))
    encoding = sys.stdout.encoding or "utf-8"
    try:
        "┌✓".encode(encoding)
        unicode_ok = True
    except LookupError, UnicodeEncodeError:
        unicode_ok = False
    if not unicode_ok and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    plain = (
        "NO_COLOR" in os.environ
        or os.environ.get("TERM") == "dumb"
        or not sys.stdout.isatty()
        or not unicode_ok
    )
    console = Console(
        force_terminal=not plain,
        no_color=plain,
        color_system=None if plain else "truecolor",
    )
    try:
        code = run_shell(session, console=console)
    except KeyboardInterrupt as exc:
        raise typer.Exit(code=130) from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        typer.echo("xeon: no se pudo conectar con la API XEON.", err=True)
        raise typer.Exit(code=1) from exc
    raise typer.Exit(code=code)


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def health(base_url: str = "http://127.0.0.1:8000") -> None:
    """Comprueba que la API esta disponible."""
    response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=5)
    response.raise_for_status()
    _echo_json(response.json())


@app.command()
def chat(message: str, base_url: str = "http://127.0.0.1:8000") -> None:
    """Envia un turno al agente de producto. No calcula precios."""
    response = httpx.post(
        f"{base_url.rstrip('/')}/v1/chat",
        json={"message": message},
        timeout=130,
    )
    response.raise_for_status()
    typer.echo(response.json()["reply"])


@quotes_app.command("create")
def quotes_create(
    tenant_id: Annotated[str, typer.Option("--tenant-id", help="Empresa de prueba.")],
    request_id: Annotated[str, typer.Option("--request-id", help="Clave idempotente del intento.")],
    line: Annotated[
        list[str],
        typer.Option("--line", help="Consulta o SKU y cantidad, separados por ':'."),
    ],
    discount_requested: Annotated[bool, typer.Option("--discount-requested")] = False,
    base_url: str = "http://127.0.0.1:8000",
) -> None:
    """Crea o reutiliza un borrador DRAFT. El backend calcula; el LLM no interviene."""
    payload_lines: list[dict[str, str]] = []
    for item in line:
        if ":" not in item:
            raise typer.BadParameter("Cada --line debe ser query:cantidad")
        query, quantity = item.rsplit(":", 1)
        payload_lines.append({"query": query, "quantity": quantity})
    response = httpx.post(
        f"{base_url.rstrip('/')}/v1/quotes",
        json={
            "tenant_id": tenant_id,
            "request_id": request_id,
            "lines": payload_lines,
            "discount_requested": discount_requested,
        },
        timeout=10,
    )
    if response.status_code >= 500:
        response.raise_for_status()
    _echo_json(response.json())
    if response.status_code >= 400:
        raise typer.Exit(code=1)


@stock_app.command("show")
def stock_show(
    sku: Annotated[str, typer.Option("--sku", help="SKU a consultar.")],
    requested_branch_id: Annotated[
        str,
        typer.Option("--requested-branch-id", help="Sede desde la que se pregunta."),
    ],
    evaluated_at: Annotated[
        str,
        typer.Option(
            "--evaluated-at",
            help="Instante UTC inyectado para clasificar vigencia. No usa el reloj real.",
        ),
    ],
    requested_quantity: Annotated[
        str | None,
        typer.Option(
            "--requested-quantity",
            help="Cantidad solicitada. Explica faltante local; no reserva stock.",
        ),
    ] = None,
    base_url: str = "http://127.0.0.1:8000",
) -> None:
    """Muestra origen, tipo, vigencia y faltante local. No inventa existencias."""
    params: dict[str, str] = {
        "sku": sku,
        "requested_branch_id": requested_branch_id,
        "evaluated_at": evaluated_at,
    }
    if requested_quantity is not None:
        params["requested_quantity"] = requested_quantity
    response = httpx.get(
        f"{base_url.rstrip('/')}/v1/stock",
        params=params,
        timeout=10,
    )
    if response.status_code >= 400:
        _echo_json(response.json())
        raise typer.Exit(code=1)
    _echo_json(response.json())


@quotes_app.command("show")
def quotes_show(
    quote_id: str,
    tenant_id: Annotated[str, typer.Option("--tenant-id")],
    base_url: str = "http://127.0.0.1:8000",
) -> None:
    """Muestra un borrador existente. No lo aprueba."""
    response = httpx.get(
        f"{base_url.rstrip('/')}/v1/quotes/{quote_id}",
        params={"tenant_id": tenant_id},
        timeout=10,
    )
    if response.status_code >= 400:
        _echo_json(response.json())
        raise typer.Exit(code=1)
    _echo_json(response.json())


if __name__ == "__main__":
    app()

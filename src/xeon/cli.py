from __future__ import annotations

import json
from typing import Annotated

import httpx
import typer

app = typer.Typer(help="Cliente minimo para operar la base de XEON.")
quotes_app = typer.Typer(help="Revisar borradores sinteticos. No aprueba ni emite.")
stock_app = typer.Typer(help="Consultar disponibilidad sintetica por sede. No reserva stock.")
app.add_typer(quotes_app, name="quotes")
app.add_typer(stock_app, name="stock")


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
    """Envia un turno al agente. El backend calcula; el modelo no pone precios."""
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

from __future__ import annotations

import httpx
import typer

app = typer.Typer(help="Cliente minimo para operar la base de XEON.")


@app.command()
def health(base_url: str = "http://127.0.0.1:8000") -> None:
    """Comprueba que la API esta disponible."""
    response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=5)
    response.raise_for_status()
    typer.echo(response.json())


@app.command()
def chat(message: str, base_url: str = "http://127.0.0.1:8000") -> None:
    """Envia un turno al agente de producto."""
    response = httpx.post(
        f"{base_url.rstrip('/')}/v1/chat",
        json={"message": message},
        timeout=130,
    )
    response.raise_for_status()
    typer.echo(response.json()["reply"])


if __name__ == "__main__":
    app()

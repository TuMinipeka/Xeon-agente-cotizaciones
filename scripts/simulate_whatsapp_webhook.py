from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx

from xeon.api.app import create_app
from xeon.config import Settings


def build_sample_evolution_payload(
    *,
    message_text: str,
    remote_jid: str = "573001234567@s.whatsapp.net",
    push_name: str = "Cliente Ferreteria",
    instance: str = "xeon-ferreteria",
    message_id: str = "SIM-MSG-001",
) -> dict[str, Any]:
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": False,
                "id": message_id,
            },
            "pushName": push_name,
            "message": {
                "conversation": message_text,
            },
        },
    }


async def run_simulation(
    *,
    message_text: str,
    provider: str,
    live_url: str | None,
) -> dict[str, Any]:
    payload = build_sample_evolution_payload(message_text=message_text)

    if live_url:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{live_url.rstrip('/')}/v1/channels/whatsapp/webhook",
                json=payload,
            )
            response.raise_for_status()
            return dict(response.json())

    settings = Settings(
        llm_provider=provider,  # type: ignore[arg-type]
        whatsapp_send_enabled=False,
    )
    app = create_app(settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/v1/channels/whatsapp/webhook", json=payload)
        response.raise_for_status()
        return dict(response.json())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simula un webhook MESSAGES_UPSERT de Evolution API (WhatsApp) hacia XEON."
    )
    parser.add_argument(
        "--message",
        default="Necesito cotizar 5 tubos PVC presion 1/2 en la sede norte y saber disponibilidad",
        help="Mensaje de WhatsApp del cliente a simular",
    )
    parser.add_argument(
        "--provider",
        choices=("mock", "hermes", "groq"),
        default="mock",
        help="Proveedor LLM a usar en modo in-process (default: mock)",
    )
    parser.add_argument(
        "--live-url",
        default=None,
        help=(
            "Si se especifica (ej. http://127.0.0.1:8000), "
            "envia el webhook por HTTP al servidor en vivo"
        ),
    )
    args = parser.parse_args()

    result = asyncio.run(
        run_simulation(
            message_text=args.message,
            provider=args.provider,
            live_url=args.live_url,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

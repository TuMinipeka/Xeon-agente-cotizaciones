from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Any

import httpx


def _resolve_api_key() -> str:
    env_key = os.getenv("EVOLUTION_API_KEY", "").strip()
    if env_key:
        return env_key
    key_file = os.getenv("EVOLUTION_API_KEY_FILE", "").strip()
    if key_file:
        return Path(key_file).read_text(encoding="utf-8").strip()
    return "xeon-evolution-local-key"


def setup_instance(
    *,
    evolution_url: str,
    instance_name: str,
    webhook_url: str,
    api_key: str,
    qr_output: Path,
) -> dict[str, Any]:
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    base = evolution_url.rstrip("/")

    with httpx.Client(timeout=20.0, headers=headers) as client:
        health_resp = client.get(f"{base}/")
        health_resp.raise_for_status()

        instances_resp = client.get(f"{base}/instance/fetchInstances")
        instances_resp.raise_for_status()
        instances = instances_resp.json()
        exists = any(
            isinstance(item, dict)
            and (item.get("name") == instance_name or item.get("instanceName") == instance_name)
            for item in (instances if isinstance(instances, list) else [])
        )

        if not exists:
            create_payload = {
                "instanceName": instance_name,
                "integration": "WHATSAPP-BAILEYS",
                "qrcode": True,
                "rejectCall": True,
                "groupsIgnore": True,
                "alwaysOnline": False,
                "readMessages": True,
                "readStatus": False,
                "syncFullHistory": False,
                "webhook": {
                    "url": webhook_url,
                    "byEvents": False,
                    "base64": False,
                    "events": ["MESSAGES_UPSERT"],
                },
            }
            create_resp = client.post(f"{base}/instance/create", json=create_payload)
            create_resp.raise_for_status()
        else:
            webhook_payload = {
                "webhook": {
                    "enabled": True,
                    "url": webhook_url,
                    "byEvents": False,
                    "base64": False,
                    "events": ["MESSAGES_UPSERT"],
                }
            }
            client.post(f"{base}/webhook/set/{instance_name}", json=webhook_payload)

        connect_resp = client.get(f"{base}/instance/connect/{instance_name}")
        connect_resp.raise_for_status()
        connect_data: dict[str, Any] = connect_resp.json()

        qr_base64 = connect_data.get("base64")
        if not qr_base64 and isinstance(connect_data.get("qrcode"), dict):
            qr_base64 = connect_data["qrcode"].get("base64")

        if isinstance(qr_base64, str) and qr_base64.strip():
            raw_b64 = qr_base64.split(",", 1)[-1]
            qr_output.write_bytes(base64.b64decode(raw_b64))
            connect_data["qr_saved_to"] = str(qr_output.resolve())

        return connect_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aprovisiona instancia gratuita de WhatsApp (Baileys QR $0) en Evolution API para XEON."
        )
    )
    parser.add_argument(
        "--evolution-url",
        default=os.getenv("EVOLUTION_API_URL", "http://127.0.0.1:8080"),
        help="URL base de Evolution API (default: http://127.0.0.1:8080)",
    )
    parser.add_argument(
        "--instance",
        default=os.getenv("EVOLUTION_INSTANCE", "xeon-ferreteria"),
        help="Nombre de la instancia en Evolution API (default: xeon-ferreteria)",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.getenv(
            "XEON_WEBHOOK_URL",
            "http://api:8000/v1/channels/whatsapp/webhook",
        ),
        help="URL del webhook de XEON que recibira MESSAGES_UPSERT",
    )
    parser.add_argument(
        "--qr-output",
        default="qr_whatsapp.png",
        help="Archivo donde guardar la imagen PNG del codigo QR",
    )
    args = parser.parse_args()

    try:
        result = setup_instance(
            evolution_url=args.evolution_url,
            instance_name=args.instance,
            webhook_url=args.webhook_url,
            api_key=_resolve_api_key(),
            qr_output=Path(args.qr_output),
        )
    except httpx.HTTPError as exc:
        print(
            f"[ERROR] No se pudo conectar a Evolution API en {args.evolution_url}: {exc}\n"
            "Asegurate de levantar Docker primero:\n"
            "  docker compose -f compose.yaml -f compose.evolution.yaml --profile core up -d",
            file=sys.stderr,
        )
        return 1

    print(f"[OK] Instancia '{args.instance}' configurada en modo WHATSAPP-BAILEYS ($0 costo).")
    print(f"[OK] Webhook apuntando a: {args.webhook_url}")
    if "qr_saved_to" in result:
        print(f"[QR] Imagen del codigo QR guardada en: {result['qr_saved_to']}")
        print("     Abre esa imagen y escaneala desde WhatsApp -> Dispositivos vinculados.")
    else:
        state = result.get("instance", {}).get("state") or result.get("state") or "desconocido"
        print(f"[INFO] Estado de conexion: {state}")
        print(f"       Panel visual disponible en: {args.evolution_url}/manager")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

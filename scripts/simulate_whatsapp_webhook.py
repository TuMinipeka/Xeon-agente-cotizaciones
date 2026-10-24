from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import httpx

DEFAULT_URL = "http://127.0.0.1:8000/v1/channels/whatsapp/kapso/webhook"


def build_sample_kapso_payload(
    *, message_text: str, phone_number_id: str, sender_number: str, message_id: str
) -> dict[str, Any]:
    return {
        "phone_number_id": phone_number_id,
        "conversation": {"phone_number": sender_number},
        "message": {"id": message_id, "type": "text", "text": {"body": message_text}},
    }


def sign_payload(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Simula un webhook firmado de Kapso para XEON.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--message", default="Necesito 5 tubos PVC de 1/2 pulgada")
    parser.add_argument("--message-id", default="SIM-MSG-001")
    parser.add_argument("--phone-number-id", default=os.getenv("KAPSO_PHONE_NUMBER_ID", ""))
    parser.add_argument("--sender-number", default="+573001234567")
    parser.add_argument(
        "--webhook-secret-file",
        type=Path,
        default=Path(os.getenv("KAPSO_WEBHOOK_SECRET_FILE", "secrets/kapso_webhook_secret.txt")),
    )
    args = parser.parse_args()
    if not args.phone_number_id.strip():
        parser.error("KAPSO_PHONE_NUMBER_ID o --phone-number-id es obligatorio.")
    try:
        secret = args.webhook_secret_file.read_text(encoding="utf-8").strip()
    except OSError:
        parser.error("No se pudo leer KAPSO_WEBHOOK_SECRET_FILE.")
    if not secret:
        parser.error("KAPSO_WEBHOOK_SECRET_FILE esta vacio.")
    payload = build_sample_kapso_payload(
        message_text=args.message,
        phone_number_id=args.phone_number_id,
        sender_number=args.sender_number,
        message_id=args.message_id,
    )
    raw_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        response = httpx.post(
            args.url,
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Event": "whatsapp.message.received",
                "X-Webhook-Signature": sign_payload(raw_body, secret),
            },
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        parser.exit(1, f"No se pudo enviar el webhook: {type(exc).__name__}.\n")
    print(json.dumps(response.json(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

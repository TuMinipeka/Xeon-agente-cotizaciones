from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import httpx

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kapso_webhook.py"
SPEC = importlib.util.spec_from_file_location("kapso_webhook_script", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
main = module.main

WEBHOOK_URL = "https://xeon.example/v1/channels/whatsapp/kapso/webhook"
API_KEY = "private-api-key-for-test"


def invoke(
    args: list[str],
    tmp_path: Path,
    transport: httpx.MockTransport,
    *,
    environ: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with httpx.Client(transport=transport) as client:
        code = main(
            args,
            client=client,
            environ=environ
            or {
                "KAPSO_API_KEY": API_KEY,
                "KAPSO_WEBHOOK_SECRET_FILE": str(tmp_path / "webhook-secret.txt"),
            },
            env_file=tmp_path / ".env",
            stdout=out,
            stderr=err,
        )
    return code, out.getvalue(), err.getvalue()


def test_create_writes_and_sends_secret_without_printing_it(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"whatsapp_webhook": {"id": "webhook-123"}})

    code, out, err = invoke(
        ["create", "--phone-number-id", "phone-1", "--url", WEBHOOK_URL],
        tmp_path,
        httpx.MockTransport(respond),
    )
    secret = (tmp_path / "webhook-secret.txt").read_text(encoding="utf-8").strip()
    assert len(secret) == 64
    assert code == 0
    assert out == "HTTP 201\nwebhook_id: webhook-123\n"
    assert err == ""
    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/platform/v1/whatsapp/phone_numbers/phone-1/webhooks"
    assert seen[0].headers["X-API-Key"] == API_KEY
    assert json.loads(seen[0].content) == {
        "whatsapp_webhook": {
            "url": WEBHOOK_URL,
            "events": ["whatsapp.message.received"],
            "kind": "kapso",
            "payload_version": "v2",
            "buffer_enabled": False,
            "active": True,
            "secret_key": secret,
        }
    }
    assert secret not in out + err
    assert API_KEY not in out + err


def test_create_requires_explicit_rotation(tmp_path: Path) -> None:
    secret_file = tmp_path / "webhook-secret.txt"
    secret_file.write_text("old-secret\n", encoding="utf-8")
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"id": "new-webhook"})

    args = ["create", "--phone-number-id", "phone-1", "--url", WEBHOOK_URL]
    code, out, err = invoke(args, tmp_path, httpx.MockTransport(respond))
    assert code == 1
    assert "--rotate-secret" in err
    assert out == ""
    assert not requests
    assert secret_file.read_text(encoding="utf-8") == "old-secret\n"
    code, out, err = invoke([*args, "--rotate-secret"], tmp_path, httpx.MockTransport(respond))
    assert code == 0
    assert secret_file.read_text(encoding="utf-8").strip() != "old-secret"
    assert len(requests) == 1
    assert API_KEY not in out + err


def test_update_url_uses_project_route_and_patch(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "webhook-123"})

    code, out, err = invoke(
        ["update-url", "--webhook-id", "webhook-123", "--url", WEBHOOK_URL],
        tmp_path,
        httpx.MockTransport(respond),
    )
    assert code == 0
    assert out == "HTTP 200\n"
    assert err == ""
    assert requests[0].method == "PATCH"
    assert requests[0].url.path == "/platform/v1/whatsapp/webhooks/webhook-123"
    assert requests[0].content == b'{"whatsapp_webhook":{"url":"' + WEBHOOK_URL.encode() + b'"}}'


def test_list_uses_env_file_and_prints_only_requested_fields(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        f"KAPSO_API_KEY={API_KEY}\nKAPSO_API_BASE_URL=https://api.example\n",
        encoding="utf-8",
    )

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.example"
        assert request.url.path == "/platform/v1/whatsapp/phone_numbers/phone-1/webhooks"
        assert request.headers["X-API-Key"] == API_KEY
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "webhook-123",
                        "url": WEBHOOK_URL,
                        "active": True,
                        "events": ["whatsapp.message.received"],
                        "secret_key": "server-secret",
                    }
                ]
            },
        )

    code, out, err = invoke(
        ["list", "--phone-number-id", "phone-1"],
        tmp_path,
        httpx.MockTransport(respond),
        environ={},
    )
    assert code == 0
    assert "webhook-123\t" in out
    assert WEBHOOK_URL in out
    assert "whatsapp.message.received" in out
    assert "server-secret" not in out + err
    assert API_KEY not in out + err


def test_rejects_insecure_urls_and_redirects(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example"})

    transport = httpx.MockTransport(respond)
    code, out, err = invoke(
        ["update-url", "--webhook-id", "webhook-123", "--url", "http://xeon.example"],
        tmp_path,
        transport,
    )
    assert code == 1
    assert not requests
    assert API_KEY not in out + err
    code, out, err = invoke(
        ["update-url", "--webhook-id", "webhook-123", "--url", WEBHOOK_URL],
        tmp_path,
        transport,
    )
    assert code == 1
    assert out == "HTTP 302\n"
    assert "redireccion" in err
    assert len(requests) == 1
    assert API_KEY not in out + err

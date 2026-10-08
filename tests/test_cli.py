from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from xeon.cli import app

runner = CliRunner()


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


def test_cli_creates_and_shows_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []  # method, url
    quote = {
        "id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "demo",
        "request_id": "req-1",
        "version": 1,
        "status": "DRAFT",
        "total": "57800.00",
        "replayed": False,
    }

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        calls.append(("POST", url))
        assert json["tenant_id"] == "demo"
        assert json["request_id"] == "req-1"
        assert json["lines"] == [{"query": "CEM-50", "quantity": "2"}]
        return _FakeResponse(201, {"outcome": "draft_ready", "quote": quote})

    def fake_get(url: str, params: dict[str, str], timeout: float) -> _FakeResponse:
        calls.append(("GET", url))
        assert params["tenant_id"] == "demo"
        return _FakeResponse(200, quote)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    created = runner.invoke(
        app,
        [
            "quotes",
            "create",
            "--tenant-id",
            "demo",
            "--request-id",
            "req-1",
            "--line",
            "CEM-50:2",
        ],
    )
    shown = runner.invoke(
        app,
        ["quotes", "show", quote["id"], "--tenant-id", "demo"],
    )

    assert created.exit_code == 0
    assert shown.exit_code == 0
    assert json.loads(created.stdout)["outcome"] == "draft_ready"
    assert json.loads(shown.stdout)["status"] == "DRAFT"
    assert calls[0][0] == "POST"
    assert calls[1][0] == "GET"

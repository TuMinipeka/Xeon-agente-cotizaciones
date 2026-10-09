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


def test_cli_shows_stock_by_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "sku": "TUB-PVC-20",
        "requested_branch_id": "sede-centro",
        "evaluated_at": "2026-10-08T15:00:00+00:00",
        "items": [
            {
                "sku": "TUB-PVC-20",
                "branch_id": "sede-norte",
                "origin_id": "sede-norte",
                "origin_name": "Ferreteria Demo XEON Norte",
                "quantity": "12",
                "kind": "transfer",
                "channel": "on_hand",
                "source": "synthetic-ferreteria-demo-xeon",
                "observed_at": "2026-10-08T12:00:00+00:00",
                "valid_until": "2026-10-08T18:00:00+00:00",
                "freshness": "fresh",
                "is_firm": True,
                "age": "PT3H",
            }
        ],
    }

    def fake_get(url: str, params: dict[str, str], timeout: float) -> _FakeResponse:
        assert url.endswith("/v1/stock")
        assert params == {
            "sku": "TUB-PVC-20",
            "requested_branch_id": "sede-centro",
            "evaluated_at": "2026-10-08T15:00:00+00:00",
        }
        return _FakeResponse(200, payload)

    monkeypatch.setattr(httpx, "get", fake_get)

    shown = runner.invoke(
        app,
        [
            "stock",
            "show",
            "--sku",
            "TUB-PVC-20",
            "--requested-branch-id",
            "sede-centro",
            "--evaluated-at",
            "2026-10-08T15:00:00+00:00",
        ],
    )

    assert shown.exit_code == 0
    body = json.loads(shown.stdout)
    assert body["items"][0]["kind"] == "transfer"
    assert body["items"][0]["origin_id"] == "sede-norte"
    assert body["items"][0]["kind"] != "local"
    assert body["items"][0]["freshness"] == "fresh"
    assert body["items"][0]["is_firm"] is True
    assert body["evaluated_at"] == "2026-10-08T15:00:00+00:00"


def test_cli_shows_partial_stock_for_requested_quantity(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "sku": "CEM-50",
        "requested_branch_id": "sede-norte",
        "evaluated_at": "2026-10-08T15:00:00+00:00",
        "requested_quantity": "50",
        "fulfillment_status": "partial",
        "local_available": "20",
        "shortfall": "30",
        "items": [
            {
                "sku": "CEM-50",
                "branch_id": "sede-norte",
                "origin_id": "sede-norte",
                "origin_name": "Ferreteria Demo XEON Norte",
                "quantity": "20",
                "kind": "local",
                "channel": "on_hand",
                "source": "synthetic-ferreteria-demo-xeon",
                "observed_at": "2026-10-08T12:00:00+00:00",
                "valid_until": "2026-10-08T18:00:00+00:00",
                "freshness": "fresh",
                "is_firm": True,
                "age": "PT3H",
            }
        ],
        "alternatives": [
            {
                "sku": "CEM-50",
                "branch_id": "sede-centro",
                "origin_id": "sede-centro",
                "origin_name": "Ferreteria Demo XEON Centro",
                "quantity": "80",
                "kind": "transfer",
                "channel": "on_hand",
                "source": "synthetic-ferreteria-demo-xeon",
                "observed_at": "2026-10-08T12:00:00+00:00",
                "valid_until": "2026-10-08T18:00:00+00:00",
                "freshness": "fresh",
                "is_firm": True,
                "age": "PT3H",
            }
        ],
    }

    def fake_get(url: str, params: dict[str, str], timeout: float) -> _FakeResponse:
        assert url.endswith("/v1/stock")
        assert params == {
            "sku": "CEM-50",
            "requested_branch_id": "sede-norte",
            "requested_quantity": "50",
            "evaluated_at": "2026-10-08T15:00:00+00:00",
        }
        return _FakeResponse(200, payload)

    monkeypatch.setattr(httpx, "get", fake_get)

    shown = runner.invoke(
        app,
        [
            "stock",
            "show",
            "--sku",
            "CEM-50",
            "--requested-branch-id",
            "sede-norte",
            "--requested-quantity",
            "50",
            "--evaluated-at",
            "2026-10-08T15:00:00+00:00",
        ],
    )

    assert shown.exit_code == 0
    body = json.loads(shown.stdout)
    assert body["requested_quantity"] == "50"
    assert body["fulfillment_status"] == "partial"
    assert body["local_available"] == "20"
    assert body["shortfall"] == "30"
    assert body["alternatives"][0]["kind"] == "transfer"
    assert body["alternatives"][0]["origin_id"] == "sede-centro"
    assert body["items"][0]["freshness"] == "fresh"
    assert body["items"][0]["is_firm"] is True


def test_cli_shows_stale_stock_without_promising_firm_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "sku": "CEM-50",
        "requested_branch_id": "sede-norte",
        "evaluated_at": "2026-10-09T12:00:00+00:00",
        "requested_quantity": "50",
        "fulfillment_status": "unknown",
        "local_available": None,
        "shortfall": None,
        "items": [
            {
                "sku": "CEM-50",
                "branch_id": "sede-norte",
                "origin_id": "sede-norte",
                "origin_name": "Ferreteria Demo XEON Norte",
                "quantity": "20",
                "kind": "local",
                "channel": "on_hand",
                "source": "synthetic-ferreteria-demo-xeon",
                "observed_at": "2026-10-08T12:00:00+00:00",
                "valid_until": "2026-10-08T18:00:00+00:00",
                "freshness": "stale",
                "is_firm": False,
                "age": "PT24H",
            }
        ],
        "alternatives": [],
    }

    def fake_get(url: str, params: dict[str, str], timeout: float) -> _FakeResponse:
        assert url.endswith("/v1/stock")
        assert params == {
            "sku": "CEM-50",
            "requested_branch_id": "sede-norte",
            "requested_quantity": "50",
            "evaluated_at": "2026-10-09T12:00:00+00:00",
        }
        return _FakeResponse(200, payload)

    monkeypatch.setattr(httpx, "get", fake_get)

    shown = runner.invoke(
        app,
        [
            "stock",
            "show",
            "--sku",
            "CEM-50",
            "--requested-branch-id",
            "sede-norte",
            "--requested-quantity",
            "50",
            "--evaluated-at",
            "2026-10-09T12:00:00+00:00",
        ],
    )

    assert shown.exit_code == 0
    body = json.loads(shown.stdout)
    assert body["fulfillment_status"] == "unknown"
    assert body["items"][0]["freshness"] == "stale"
    assert body["items"][0]["is_firm"] is False
    assert body["items"][0]["valid_until"] == "2026-10-08T18:00:00+00:00"
    assert body["items"][0]["age"] == "PT24H"
    assert body["local_available"] is None

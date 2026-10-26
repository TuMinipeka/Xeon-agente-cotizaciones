"""Persistence formats and configuration without a database or network."""

from dataclasses import replace
from pathlib import Path

import pytest

from xeon.adapters.catalog.synthetic_seed import CORE_SYNTHETIC_PRODUCTS
from xeon.adapters.persistence.postgres.codec import (
    cart_in,
    cart_out,
    funnel_in,
    funnel_out,
    quote_in,
    quote_out,
)
from xeon.application.ports.funnel import FunnelState
from xeon.application.reply import Option, Reply
from xeon.config import Settings, SettingsError
from xeon.domain.cart import QuoteCart
from xeon.domain.quote import build_draft_quote


def test_operational_payloads_round_trip_exact_money_and_reply() -> None:
    product = CORE_SYNTHETIC_PRODUCTS[0]
    cart = QuoteCart("conversation").add_item(product, 10)
    cart = replace(cart, last_request_id="message-1")
    assert cart_in(cart_out(cart)) == cart
    state = FunnelState(
        step="cantidad",
        selected_sku=product.sku,
        candidates=(product.sku,),
        last_request_id="message-1",
        last_reply=Reply("¿Cuántas?", kind="buttons", options=(Option("quantity:10", "10"),)),
    )
    assert funnel_in(funnel_out(state)) == state
    quote = build_draft_quote(
        cart.confirmed_lines(),
        tenant_id="test",
        request_id="quote-1",
        version=cart.quote_version,
    )
    assert quote_in(quote_out(quote)) == quote
    with pytest.raises(ValueError, match="Version"):
        cart_in({"schema_version": 99, "data": {}})


def test_state_url_requires_secret_file_and_postgres_scheme(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("sqlite:///wrong", encoding="utf-8")
    with pytest.raises(SettingsError, match="secrets"):
        Settings(xeon_state_url_file=outside, _env_file=None).require_state_url()
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir()
    bad = secret_dir / "url.txt"
    bad.write_text("sqlite:///wrong", encoding="utf-8")
    with pytest.raises(SettingsError, match="PostgreSQL"):
        Settings(xeon_state_url_file=bad, _env_file=None).require_state_url()

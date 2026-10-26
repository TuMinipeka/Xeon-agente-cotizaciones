from xeon.adapters.channels.whatsapp_formatter import WhatsAppFormatter


def test_formatter_removes_markdown_and_limits_outbound_text() -> None:
    formatter = WhatsAppFormatter(max_length=100)
    plain = formatter.format(
        "### **Cotización**\n- [Cemento](https://example.invalid): `10` x $28.900 = $289.000"
    )
    assert plain == "Cotización\n• Cemento: 10 x $28.900 = $289.000"
    assert len(formatter.format("texto largo " * 40)) <= 100

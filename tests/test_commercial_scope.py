from xeon.application.commercial_scope import CommercialScopePolicy


def test_scope_blocks_general_knowledge_before_llm() -> None:
    decision = CommercialScopePolicy().classify(
        "Busca tarjetas gráficas para jugar y pásame enlaces"
    )

    assert decision.kind == "out_of_scope"
    assert decision.blocks_llm is True
    assert decision.commercial_query is None
    assert decision.customer_message is not None
    assert "ferretería" in decision.customer_message


def test_scope_allows_courtesy_and_operational_help_without_general_knowledge() -> None:
    policy = CommercialScopePolicy()

    greeting = policy.classify("Buenas tardes")
    help_request = policy.classify("¿Cómo funciona este chat?")

    assert greeting.kind == "courtesy"
    assert greeting.blocks_llm is True
    assert help_request.kind == "operational_help"
    assert help_request.blocks_llm is True
    assert "producto" in (help_request.customer_message or "")
    assert "cantidad" in (help_request.customer_message or "")


def test_scope_accepts_agreed_hardware_store_categories() -> None:
    policy = CommercialScopePolicy()

    for message in (
        "Necesito cemento para construcción",
        "Busco una herramienta para el taller",
        "Necesito tubería para plomería",
        "Busco cable para electricidad",
        "Necesito alambre para el potrero",
    ):
        decision = policy.classify(message)
        assert decision.kind == "commercial"
        assert decision.commercial_query == message


def test_scope_separates_mixed_request_and_keeps_only_commercial_part() -> None:
    decision = CommercialScopePolicy().classify(
        "Necesito cemento y busca tarjetas gráficas con enlaces"
    )

    assert decision.kind == "mixed"
    assert decision.blocks_llm is False
    assert decision.commercial_query == "Necesito cemento"
    assert decision.customer_message is not None
    assert "no manejo información" in decision.customer_message

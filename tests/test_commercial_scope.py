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


def test_scope_allows_natural_selection_and_existing_product_code_as_follow_up() -> None:
    policy = CommercialScopePolicy()

    natural_selection = policy.classify("La primera opción")
    product_code = policy.classify("CEM-50")

    assert natural_selection.kind == "commercial"
    assert product_code.kind == "commercial"


def test_scope_keeps_logistics_and_courtesy_in_commercial_request() -> None:
    policy = CommercialScopePolicy()
    for message in (
        "10 bultos de cemento y entrega en sede sur",
        "buenas vecino, me regala cotizacion de 10 bultos de cemento",
        "soy cliente frecuente, dame el descuento de siempre en 20 bultos de cemento",
    ):
        decision = policy.classify(message)
        assert decision.kind == "commercial"
        assert decision.commercial_query == message


def test_followup_requires_existing_commercial_context() -> None:
    policy = CommercialScopePolicy()
    assert policy.classify("Lo recojo en la sede norte.").kind == "out_of_scope"
    for message in ("Lo recojo en la sede norte.", "Entrega en sede sur", "Si", "20 unidades"):
        assert policy.classify(message, commercial_context=True).kind == "commercial"


def test_poem_and_cement_request_keeps_only_commercial_clause() -> None:
    message = "escribieme un poema de la lluvia y cuanto valen 4 bultos de cemento"
    for active in (False, True):
        decision = CommercialScopePolicy().classify(message, commercial_context=active)
        assert decision.kind == "mixed"
        assert decision.commercial_query == "cuanto valen 4 bultos de cemento"
        assert decision.customer_message is not None

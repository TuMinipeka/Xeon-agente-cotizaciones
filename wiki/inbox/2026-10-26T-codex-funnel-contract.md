---
tags:
  - xeon/estado
---

# Ajuste del embudo al contrato D14

Fecha: 2026-10-26. Autor del aporte: Codex. Estado: implementado y verificado localmente. Fuentes: encargo del orquestador, [contrato D14](../pages/embudo-cotizacion.md), [guía QA](../../docs/QA_EMBUDO.md) y pruebas del repositorio. Pendiente: integrar esta nota en las páginas compartidas de la wiki.

Commit funcional: `dcfc794` (`Fix: :bug: AlignGuidedFunnelWithD14Contract`).

- `inicio`, `cantidad`, `mas`, `entrega` y `resumen` ofrecen tres botones. `resumen` ofrece exactamente Confirmar, Modificar y Cancelar. Las órdenes de texto «cancelar» y «asesor» siguen disponibles en cualquier paso sin ocupar los botones. El tercer botón de `entrega` es Hablar con asesor para cumplir el requisito de tres; la tabla original de D14 mostraba dos alternativas de entrega.
- `cantidad` nombra el producto completo y usa la unidad del catálogo: bulto 10/20/Otra, metro 10/50/Otra y unidad u otras unidades 1/2/Otra. Las selecciones se procesan por ID sin cálculo del modelo.
- Preguntas sobre horario, domicilio, recogida, pago, IVA, descuentos y vigencia se contestan con el YAML del tenant y luego se repiten las opciones del paso. Un campo nulo se indica como pendiente de confirmar con un asesor. El carrito y la etapa no cambian.
- Pruebas: `tests/test_guided_funnel.py` verifica los cinco payloads Kapso de tipo `button` con tres opciones, las unidades y políticas en varios pasos, incluido YAML con valores nulos. `tests/guided_steps.py` y `tests/evals/test_regressions.py` aceptan 10 unidades mediante Otra sin cambiar la cantidad o la prueba de borrador único. `evals/scenarios/journeys.yaml` usa botones 1 y 2 para la pala en S21 y S17; conserva montos, cantidades y criterios. `tests/test_multiturn_context.py` conserva la verificación de política de descuento y no repetición de borrador.
- La guía manual `docs/QA_EMBUDO.md` conserva descripciones del flujo previo (cuatro opciones iniciales, cantidad 10/20 para pala, etc.). Requiere actualización por quien la mantiene. No se ha probado WhatsApp real ni se han hecho llamadas pagadas.

Gate local: `uv run --locked --group evals ruff check .`, `ruff format --check .`, `mypy src evals` y `pytest -q` terminaron con código 0; `uv run --locked --group evals python -m evals.runner --mode offline`: 66 PASS, 0 FAIL, 0 ERROR. El grafo se regeneró con `uv run --locked --group graph python scripts/build_graphify_map.py`: Graphify 0.9.95, 2389 nodos, 7095 aristas, 154 comunidades, 273 archivos, 0 llamadas LLM, 0 coincidencias de rutas excluidas o valores tipo clave. La extracción SQL emitió un aviso de dependencia opcional `tree_sitter_sql` ausente; no afecta el embudo.

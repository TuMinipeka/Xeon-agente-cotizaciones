---
tags:
  - xeon/operacion
---

# Corrección local de los defectos S16–S20 de la corrida en vivo

Fecha: 2026-10-26. Autor de la evidencia: agy, [nota de corrida en vivo](2026-10-26T-agy-live-qa-conde.md). Implementación: Codex en `fix/live-qa-defects`, commit `1422e05` (`Fix: :bug: PreserveLiveConversationState`). Estado: **implementado y probado localmente** con LLM simulado; queda pendiente repetir la corrida pagada en vivo por decisión del orquestador. Relacionado: [QA de Conde](../pages/qa-conde-2026-10-24.md), [arquitectura](../pages/arquitectura-actual.md) y [evaluación](../pages/evaluacion-conversacional.md).

| Defecto | Causa verificada | Commit | Regresión determinista | Estado |
|---|---|---|---|---|
| D1 / S16 | El intérprete aceptaba `agregar` del modelo para «mejor dejala en 15 bultos de cemento», y `QuoteCart.add_item` sumaba al SKU existente. La corrección «no es 35 son 15 nomas» leía 35. | `1422e05` | `tests/test_live_qa_defects.py::test_s16_absolute_correction_overrides_model_addition`, seis frases de reemplazo absoluto y prueba de verbo aditivo explícito. | Corregido localmente: 15 × $28.900 = $433.500. |
| D2 / S17 | La memoria retenía una sola lista de opciones; `_choose` seleccionaba la primera línea pendiente, aunque las opciones fueran de pala. Nuevas solicitudes de pala sumaban cantidades anteriores. | `1422e05` | `test_s17_pending_variant_keeps_its_own_quantity_and_cement` reproduce «quiero 20 bultos cemento gris y 3 palas» → «elige 1 y pala 2 pon 15 bultos y 2 palas» → «pala 2 deja solo 1 pala 15 cemento» → «la redonda con mango de fibra». | Corregido localmente: cemento 15 y pala redonda 1; total $477.200; sin líneas pendientes fantasma. |
| D3 / S19 | El formato Markdown solo se aplicaba en Kapso y la cobertura del proyecto no se guardaba. El ejecutor repetía la misma pregunta al ver el área. | `1422e05` | `test_s19_plain_text_and_whole_surface_confirmation` y `test_s19_chat_api_uses_same_plain_text_boundary`; LLM simulado devuelve `###`, `**` y una repregunta. | Corregido localmente: salida plana en `AgentService` para API, CLI y Kapso; `whole_surface=True` conserva la respuesta «toda la superficie». |
| D4 / S20 | La comprobación de compatibilidad dependía de palabras del turno actual y no retenía el contexto de PC/placa base. | `1422e05` | `test_s20_pc_compatibility_persists_across_rephrasing` reproduce «hola tienen tornillos para motherboard de pc» → «tienen m3 o 6-32 para placa base» → «tienen o no tornillos m3 para pc», más seguimiento «tienen tornillos 6-32». | Corregido localmente: exige compatibilidad verificada y no ofrece tornillos galvanizados de obra. |
| D5 / S18 | Una consulta de stock con sede y cantidad, pero sin producto, descartaba la sede y obligaba a repetir la solicitud. | `1422e05` | `test_s18_stock_product_branch_same_turn_or_one_clarification` reproduce «estan disponibles esos 10 bultos en sede norte» → «cemento 10 bultos» → pago/recogida → resumen; también producto, cantidad y sede en un turno. | Corregido localmente: una aclaración con opciones, stock de sede Norte y borrador de $289.000. |

La memoria de opciones pendientes ahora conserva la asociación con cada línea. La cantidad pendiente se actualiza al fijar o quitar unidades, y elegir una variante modifica solo su línea. El intérprete usa salvaguardas deterministas sobre JSON válido del modelo en ajustes absolutos y consultas de stock. El formato plano se implementa una vez en `application/plain_text.py`; `AgentService` lo aplica antes de responder y Kapso reutiliza esa función con su límite de longitud.

## Verificación y límites

- `uv run --locked --group evals ruff check .`: verde. `ruff format --check .`: verde tras el formato del archivo que agy edita en `tests/evals/`. `mypy src evals`: verde. Las 13 pruebas de `tests/test_live_qa_defects.py` pasan.
- `uv run --locked --group evals python -m evals.runner --mode offline`: **60 PASS, 0 FAIL, 0 ERROR**, S01–S20 con tres repeticiones. Coste de modelos de esta tarea: **0**. No hubo llamadas a Grok.
- El último `pytest` completo observó tres fallos en `tests/test_e12_e13_live_regressions.py` causados por la captura nueva de eventos de herramienta de agy: `RecordingLLM.tool_contexts()[-1]` termina en un evento de borrador que conserva `quote_id` pero omite `total`, aunque los borradores contienen los importes correctos. Agy trabaja en `evals/recording.py`, `evals/sut.py` y `tests/evals/`; Codex no editó ni versionó esos archivos. Repetir `pytest` tras su ajuste.
- Se regeneró Graphify con extracción AST local, sin extracción semántica ni llamadas a modelos. Los cambios autogenerados de `wiki/graph/` se excluyen de este commit para evitar mezclar el mapa con la reparación conversacional.
- El documento funcional `docs/XeonContexto.md` todavía describe el prototipo sintético, mientras `docs/ARCHITECTURE.md` documenta el conector SQL opcional. La operación predeterminada sigue sintética; no se infiere una conexión activa a una ferretería real. La armonización documental corresponde al orquestador.

La evidencia en vivo previa era 1 PASS, 5 FAIL. Esta nota registra correcciones deterministas locales; no afirma que una nueva corrida en vivo ya haya pasado.

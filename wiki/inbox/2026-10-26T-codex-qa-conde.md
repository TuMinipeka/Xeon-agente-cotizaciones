# QA conversacional Conde — Fase 1

- Fecha: 2026-10-26.
- Procedencia: `docs/qa/reporte_conde_qa.md`, plan aprobado `C:/Users/danie/.claude/plans/atomic-percolating-stream.md`, código y pruebas locales.
- Estado: implementación en `fix/qa-conde-cart`; pendiente de integración del orquestador en páginas compartidas de la wiki.
- Commits: `d29c45a` (C2, carrito), `08a14b9` (C1/C3, intérprete), `30e1410` (C2/C4, ejecutor y políticas), `af41edd` (C4, canal y seguimiento).
- Evidencia principal: `tests/test_qa_conde_conversation.py`, `tests/test_quote_cart.py`, `tests/test_intent_interpreter.py`, `tests/test_whatsapp_formatter.py`.

| QA | Causa | Commit | Prueba de regresión / evidencia | Estado |
|---|---|---|---|---|
| QA-001 | C1/C2/C3 | `08a14b9`, `30e1410` | `test_stock_and_policy_followups_preserve_quote`; `test_hypothetical_and_project_data_do_not_change_cart` | Corregido para contexto comercial reconocido; memoria local. |
| QA-002 | C1/C4 | `30e1410` | `test_weight_and_delivery_questions_are_both_addressed`; `test_tool_trace_records_three_real_invocations_without_customer_data` | Parcial: precio solo desde catálogo sintético; compatibilidad técnica real sin fuente autorizada. |
| QA-003 | C1/C3 | `08a14b9`, `30e1410` | `test_hypothetical_and_project_data_do_not_change_cart` | Parcial: corral y área reconocidos; cobertura general de todos los proyectos aún no validada. |
| QA-004 | C1/C4 | `af41edd` | `test_weight_and_delivery_questions_are_both_addressed` | Corregido para la frase reportada: peso y domicilio quedan explícitamente pendientes, sin inventar. |
| QA-005 | C4 | `30e1410` | `test_stock_and_policy_followups_preserve_quote`; `tests/test_toolbelt_agent.py` | Corregido: disponible, agotado o pendiente según inventario y vigencia. |
| QA-006 | C2 | `d29c45a`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total` | Parcial: cotización progresiva DRAFT; aprobación y cierre comercial siguen fuera de alcance. |
| QA-007 | C1/C4 | `af41edd` | `test_formatter_removes_markdown_and_limits_outbound_text`; `test_stock_and_policy_followups_preserve_quote` | Corregido en el canal Kapso y en las frases verificadas. |
| QA-008 | C2/C3 | `d29c45a`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total` | Corregido: 15 bultos y dos palas pendientes de variante. |
| QA-009 | C2/C3 | `08a14b9`, `30e1410` | `test_hypothetical_and_project_data_do_not_change_cart` | Corregido: pregunta hipotética no muta el carrito. |
| QA-010 | C2/C4 | `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total` | Corregido: 15 × 28.900 + 1 × 43.700 = 477.200, cálculo Decimal del backend. |
| QA-011 | C3 | `08a14b9`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total`; `tests/test_intent_interpreter.py` | Corregido: elección por atributos de la pala pendiente. |
| QA-012 | C2/C3 | `d29c45a`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total` | Corregido: reduce pala pendiente de dos a una antes de fijar SKU. |
| QA-013 | C1/C4 | `08a14b9`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total`; `test_weight_and_delivery_questions_are_both_addressed` | Parcial: operaciones probadas sin rechazo; falta ampliar léxico de todas las comparaciones posibles. |
| QA-014 | C3 | `08a14b9`, `30e1410` | `test_hypothetical_and_project_data_do_not_change_cart` | Corregido para 20 × 30 m = 600 m²; pregunta por la superficie efectiva. |
| QA-015 | C3/C4 | `30e1410` | `test_hypothetical_and_project_data_do_not_change_cart` | Parcial: conserva medidas y pide dato faltante; no hay máquina de etapas ni cuantificación técnica validada. |
| QA-016 | C4 | `30e1410`, `af41edd` | `test_hypothetical_and_project_data_do_not_change_cart` | Parcial: marca la lista como preliminar; recomendaciones concretas requieren validación técnica externa. |
| QA-017 | C4 | `af41edd` | `test_formatter_removes_markdown_and_limits_outbound_text`; `tests/test_kapso_channel.py` | Corregido: limpia Markdown y limita cuerpo saliente de WhatsApp. |
| QA-018 | C2 | `d29c45a`, `30e1410` | `test_cart_revision_and_attribute_choice_preserve_verified_total` | Corregido: cemento y pala quedan en un único borrador vigente. |
| QA-019 | C1 | `08a14b9`, `30e1410` | `test_stock_and_policy_followups_preserve_quote` | Corregido en el flujo nuevo: rechazo solo cuando todas las intenciones son ajenas. |
| QA-020 | C1/C4 | `30e1410` | `test_stock_and_policy_followups_preserve_quote` | Corregido: consulta sede Norte y responde pendiente cuando el dato está vencido. |
| QA-021 | C4 | `30e1410` | `test_stock_and_policy_followups_preserve_quote` | Corregido según ausencia de política autorizada: pagos y recogida pendientes con asesor. |
| QA-022 | C2 | `30e1410` | `test_stock_and_policy_followups_preserve_quote` | Corregido: recupera 10 × 28.900 = 289.000. |
| QA-023 | C4 | `30e1410` | `test_stock_and_policy_followups_preserve_quote`; `test_weight_and_delivery_questions_are_both_addressed` | Corregido para inventario, pagos, recogida y presentación desconocida con contingencia específica. |

## Verificación

- `uv run --locked ruff check .`: OK.
- `uv run --locked ruff format --check .`: OK.
- `uv run --locked mypy src evals`: OK (73 archivos).
- `uv run --locked pytest -q --tb=no`: OK (suite completa; una advertencia de dependencia `rx`).
- `uv run --locked --group evals python -m evals.runner --mode offline`: 42 PASS, 0 FAIL, 0 ERROR, 90 llamadas al MockLLM del evaluador; costo real de modelo: 0. Reporte local `reports/evals/4b146f7331fb4519/`.
- `uv run --locked --group graph python scripts/build_graphify_map.py`: 1775 nodos, 5446 aristas, 98 comunidades, 216 archivos cubiertos, 0 rutas excluidas y 0 llamadas LLM.
- `uv run --locked python scripts/check_doc_links.py`: 41 enlaces relativos comprobados, 0 rotos.

## Límites y siguiente paso

- Los datos comerciales son sintéticos. `config/policies/whatsapp.yaml` deja pagos, recogida, domicilio y horarios en `null`; un asesor debe proporcionar y aprobar los valores antes de informarlos como hechos.
- El carrito y la memoria son locales al proceso y con desalojo acotado; no sobreviven reinicios ni se comparten entre réplicas.
- Las respuestas de asesoría del proveedor real no se probaron con una llamada pagada. Un turno transaccional usa una sola llamada de interpretación; la asesoría libre puede usar una segunda llamada y siempre exige validación técnica.
- Tras la auditoría B1, `build_container` siempre usa el mismo `AgentService -> IntentInterpreter -> CommercialExecutor`, incluso con `llm` inyectado. Las pruebas de integración y el SUT de evaluación observan este flujo; se retiraron el servicio previo, `CommercialScopePolicy` y `prepare_verified_context`.
- En la fase inicial no se editaron `evals/` ni `tests/evals/`. B1 cambió `evals/sut.py` y `evals/recording.py` para observar el flujo nuevo; no se tocaron `evals/scenarios/`, `evals/checks/`, `wiki/pages/`, `wiki/index.md` ni `wiki/log.md`. El orquestador puede integrar las filas parciales y decidir las políticas oficiales.

## Auditoría B1 — flujo único

- Hallazgo del orquestador: antes de `9d025e4`, el SUT inyectaba `RecordingLLM` y `build_container` elegía el camino previo. El resultado offline de **42 PASS, 0 FAIL** evaluaba ese camino, no el ejecutor nuevo.
- Corrección: `9d025e4` elimina `use_commercial_executor` y todo el camino alternativo; migra las aserciones que exigían el prefijo de rechazo o la estructura antigua del prompt. `evals/sut.py` observa la respuesta del ejecutor, y `evals/recording.py` recupera sus marcadores de diagnóstico MockLLM para los checks existentes. `8503a15` exige compatibilidad verificable para tornillos de motherboard. No se tocaron los checks ni escenarios de agy.
- Medición inicial al activar el camino único: S01–S14, tres repeticiones, **18 PASS, 24 FAIL, 0 ERROR**. Había fallos reales de XEON en consulta de stock con producto explícito, modificaciones compuestas, selección pendiente y exposición prematura de precios de candidatos; se corrigieron en `src` sin relajar los checks.
- Medición después de corregirlos: `uv run --locked --group evals python -m evals.runner --mode offline --scenarios S01,S02,S03,S04,S05,S06,S07,S08,S09,S10,S11,S12,S13,S14`: **42 PASS, 0 FAIL, 0 ERROR**, reporte `reports/evals/683a0c37fe345f6f/`; costo real de LLM: **0**.
- Prueba adicional del mismo flujo: S16 detectó que «Mejor déjamelo en 15 bultos» sumaba 15 a los 20 vigentes. El parser ahora ejecuta `set_quantity`; la corrida aislada de S16 pasó con subtotal 433.500.
- Los nuevos S15–S20 estaban en edición paralela al primer intento: 2 PASS, 1 FAIL (S16) y 3 ERROR del check `no_markdown`. Tras el ajuste de ese check por agy y las correcciones de XEON para S16 y S20, la corrida `--scenarios S15,S16,S17,S18,S19,S20 --reps 3` dio **18 PASS, 0 FAIL, 0 ERROR** (`reports/evals/c5ac092306465caf/`). Los archivos `evals/checks/`, `evals/scenarios/` y `tests/evals/test_oracle_checks.py` siguen fuera de este corte.
- Corrida offline completa posterior a B1, ya con S01–S20: `uv run --locked --group evals python -m evals.runner --mode offline`: **60 PASS, 0 FAIL, 0 ERROR**, 150 llamadas al MockLLM, costo real 0, reporte `reports/evals/72e9e69d33eaca83/`.
- Se actualizó `docs/ARCHITECTURE.md` y la distinción de versiones en `docs/XeonContexto.md`: la API directa crea DRAFT v1, mientras la conversación conserva revisiones locales del carrito. La wiki compartida sigue a cargo del orquestador.
- Verificación del grafo tras B1: `graphify explain AgentService` muestra `IntentInterpreter` y `CommercialExecutor`; `rg` ya no encuentra referencias en `src`, `tests` ni `evals` a `CommercialScopePolicy`, `prepare_verified_context`, `use_commercial_executor` o `SYSTEM_PROMPT`. Regeneración local final: 1874 nodos, 5549 aristas, 102 comunidades, 222 archivos cubiertos, cero rutas excluidas y cero llamadas LLM.

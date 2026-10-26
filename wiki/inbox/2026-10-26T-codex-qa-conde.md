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
- Para preservar pruebas de integraciones que inyectan un LLM y su contexto de herramientas, `build_container` mantiene el flujo previo si se suministra `llm` sin `use_commercial_executor=True`. El despliegue normal usa el flujo nuevo. El reemplazo definitivo de ese camino de compatibilidad requiere migrar los contratos de esas integraciones.
- No se editaron `evals/`, `tests/evals/`, `wiki/pages/`, `wiki/index.md` ni `wiki/log.md`; el orquestador puede integrar las filas parciales y decidir las políticas oficiales.

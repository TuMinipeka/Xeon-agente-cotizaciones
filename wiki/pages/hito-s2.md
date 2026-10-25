---
tags:
  - xeon/estado
---

# Hito S2: estado

Equivale al `status_s2` del protocolo original. Muestra el estado de la hoja de ruta semanal y del hito actual. Relacionado: [orquestación](orquestacion.md), [contratos de herramientas](contratos-herramientas.md), [estado del corte](estado-del-corte.md).

Revisado: 2026-10-24.

## Hoja de ruta

| Hito | Objetivo                                                     | Estado                                                                                         | Evidencia                                                                 |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| S1   | Agente funcionando de punta a punta                          | `implementado` (entregado)                                                                     | commit `90ecbfe DeliverDocHito1`; [estado del corte](estado-del-corte.md) |
| S2   | 3 herramientas funcionales y flujo de demo de 2 min          | Herramientas `implementado`; demo verificada en vivo por WhatsApp (Kapso) y en el shell `xeon` | `src/xeon/agent/hermes.py:60,153,170`; `tests/test_multiturn_context.py`  |
| S3   | Datos reales, autoevaluación y telemetría de costo por tarea | `planificado`                                                                                  | [fuente](../raw/orquestacion-original-2026-10-24.md)                      |
| S4   | Carga de 1.000 unidades en 12 h                              | `planificado`                                                                                  | [fuente](../raw/orquestacion-original-2026-10-24.md)                      |

## Trabajo delegado (2026-10-24)

| Tarea | Agente | Estado |
|---|---|---|
| Proveedor Grok (xAI) detrás de `LLMPort`, reutilizando `OpenAICompatibleLLM` | Codex | `implementado` con pruebas sin red; la prueba real con xAI queda pendiente (D3) |
| QA multi-turno con `mock`, casos límite y guion de la demo de 2 min | agy | `implementado`: `tests/test_multiturn_context.py` |
| Auditoría DRY, verificaciones e integración en la wiki | Claude Opus | `implementado`: diff revisado, sin duplicación y sin cambios en `domain` |

**Verificación del orquestador (2026-10-24):**

- `ruff check` y `ruff format --check` pasan (91 archivos).
- `mypy src` pasa (39 archivos).
- `pytest`: **93 aprobadas y 3 `xfail` estrictas** (defectos documentados abajo).
- **Tras corregir QA1–QA3 (2026-10-24):** 104 aprobadas y 0 `xfail`; `mypy` sobre 42 archivos.

## Defectos de QA

**QA1, QA2 y QA3 están corregidos** (`implementado`, 2026-10-24) según el [contrato](contratos-herramientas.md). Sus pruebas ya no llevan `xfail`: son obligatorias.

agy los validó en un **ensayo real con Grok** (`grok-4.20-0309-non-reasoning`, 3 llamadas a `/v1/chat` en la misma conversación):

- **QA2:** "Cotízame 5 unidades de ese mismo" recuperó `TUB-PVC-20` de la memoria y creó un `DRAFT v1` de 21000.00 COP.
- **QA3:** "el descuento de siempre" devolvió `discount_policy_unavailable` sin crear borrador, y Grok explicó que no hay política aprobada.
- Ningún turno inventó precios.

La tabla conserva la descripción original de cada defecto:

| ID | Defecto | Ubicación | Prueba |
|---|---|---|---|
| QA1 (**corregido**) | Un webhook repetido entre workers o tras un reinicio crea 2 borradores, porque el `request_id` es aleatorio. En un mismo proceso lo frena la caché volátil `seen_webhook_messages` (`api/app.py:131,185-195`). | `agent/hermes.py:240` | `test_duplicate_webhook_across_workers_or_restarts_is_idempotent_in_repository` |
| QA2 (**corregido**) | No hay memoria conversacional. `AgentService.respond` solo recibe el turno actual, así que una frase como "de ese mismo" pierde el SKU anterior. | `agent/service.py:17`, `api/app.py:161,198` | `test_multiturn_chat_retains_product_context_across_turns` |
| QA3 (**corregido**) | T08 por chat: "dame el descuento de siempre" crea un borrador a precio de lista sin informar `DiscountPolicyUnavailable`. | `agent/hermes.py:238` | `test_t08_chat_natural_language_discount_request_reports_policy_unavailable` |

| QA4 (**corregido**, 2026-10-24) | `/health` reportaba `provider=grok` pero `model=llama-3.3-70b-versatile` porque leía `settings.llm_model`. Ahora `LLMPort` expone `provider_name` y `model`, y `/health` los toma del LLM activo. | `api/app.py:150-156`, `application/ports/llm.py` | `tests/test_api_e2e.py`, `tests/test_config.py` |

**Casos que pasan:** T02, T03, T08 por `/v1/quotes`, T10 (`fromMe`, eco del bot y grupos), T19 (cero llamadas externas), payloads malformados (200 `ignored` o 422) e inyección de prompt (el precio de lista y el estado `DRAFT` se mantienen y el catálogo queda intacto).

## Guion de demo, menos de 2 min (modo `mock`)

Fuente: reporte QA de agy. Los comandos y opciones de la CLI se verificaron con `--help`; el recorrido completo todavía no se ha ejecutado de punta a punta.

1. **API (terminal 1).** Hay dos modos:
   - **Demo oficial con Grok** (el predeterminado; los pasos 3 y 6 consumen inferencia real): `Remove-Item Env:LLM_PROVIDER -ErrorAction SilentlyContinue; $env:WHATSAPP_SEND_ENABLED='false'; uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`
   - **Ensayo sin costo:** anteponer `$env:LLM_PROVIDER='mock';`. Al terminar, limpiar con `Remove-Item Env:LLM_PROVIDER, Env:WHATSAPP_SEND_ENABLED -ErrorAction SilentlyContinue`.
   - Si tu `.env` local define `LLM_PROVIDER`, esa línea manda sobre el valor por defecto.
2. **Salud:** `uv run xeon health`. Debe mostrar `provider: grok, model: grok-4.20-0309-non-reasoning`, o `mock` con `mock-xeon-v1` en el ensayo. El modelo sale del LLM activo desde la corrección de QA4.
3. **`search_products`:**
   - `uv run xeon chat 'Necesito el coso que va en el aire acondicionado'` (T02).
   - `uv run xeon chat 'La pieza mide 20 x 30 x 10'` (T03).
   - `uv run xeon chat 'Busco tuberia para agua fria de 200 psi'` (debe devolver `TUB-PVC-20`).
4. **`get_stock_by_branches`:**
   - `uv run xeon stock show --sku CEM-50 --requested-branch-id sede-norte --evaluated-at 2026-10-08T15:00:00+00:00 --requested-quantity 50` (resultado parcial: 20 locales y un faltante de 30).
   - El mismo comando con `--evaluated-at 2026-10-08T20:00:00+00:00` (`stale`, T07).
5. **`create_quote_draft`:**
   - `uv run xeon quotes create --tenant-id ferreteria-demo --request-id demo-desc-01 --line CEM-50:10 --discount-requested` (422, T08).
   - `uv run xeon quotes create --tenant-id ferreteria-demo --request-id demo-cot-01 --line CEM-50:10 --line TUB-PVC-20:5` (310000.00 COP).
   - El mismo comando otra vez (`replayed: true`).
6. **Webhook de Kapso:** `uv run python scripts/simulate_whatsapp_webhook.py --phone-number-id <ID_SANDBOX> --message "Necesito 10 bultos de cemento en sede norte"` firma un payload v2 y lo envía a `/v1/channels/whatsapp/kapso/webhook` (responde `processed`; la traza `[XEON_TOOL:...]` de las tres herramientas aparece en la respuesta enviada). El ensayo real se hace escribiendo al número del sandbox.

## Hallazgos que afectan la demo

Vienen de una inspección estática de `format_verified_context` en `src/xeon/agent/hermes.py:187-260`; ver D6 en [decisiones pendientes](decisiones-pendientes.md). Desde la limpieza D9 ese código vive en `src/xeon/agent/toolbelt.py` (`CommercialToolbelt.prepare_verified_context`) y los marcadores se llaman `XEON_TOOL`; las rutas y líneas citadas abajo son históricas.

- **No hay tool-calling del LLM.** Las tres herramientas se ejecutan antes de llamar al modelo y su resultado se inyecta como contexto verificado. El LLM no elige herramientas. Estado: `implementado`, distinto de lo que describe el prompt original.
- **Fecha fija.** `evaluated_at` está escrita a mano como `2026-10-08T15:00:00+00:00` (línea 212), así que la vigencia `fresh`/`stale` no depende de la hora real.
- **Errores silenciados.** `except Exception: pass` (líneas 233 y 252) oculta fallos de stock y de borrador. Puede contradecir el principio "fuente caída no significa agotado" si no se informa al comprador.
- **Borradores duplicados.** El borrador automático usa un `request_id` aleatorio por mensaje (línea 240), de modo que un webhook repetido crea otro borrador. Contradice el principio 8 de [XeonContexto](../../docs/XeonContexto.md).

# Hito S2: estado

Equivale al `status_s2` del protocolo original. Muestra el estado de la hoja de ruta semanal y del hito actual. Relacionado: [orquestación](orquestacion.md), [contratos de herramientas](contratos-herramientas.md), [estado del corte](estado-del-corte.md).

Revisado: 2026-10-24.

## Hoja de ruta

| Hito | Objetivo | Estado | Evidencia |
|---|---|---|---|
| S1 | Agente funcionando de punta a punta | `implementado` (entregado) | commit `90ecbfe DeliverDocHito1`; [estado del corte](estado-del-corte.md) |
| S2 | 3 herramientas funcionales y flujo de demo de 2 min | Herramientas `implementado`; guion de demo listo, pendiente de ensayo en vivo | `src/xeon/agent/hermes.py:60,153,170`; `tests/test_multiturn_context.py` |
| S3 | Datos reales, autoevaluación y telemetría de costo por tarea | `planificado` | [fuente](../raw/orquestacion-original-2026-10-24.md) |
| S4 | Carga de 1.000 unidades en 12 h | `planificado` | [fuente](../raw/orquestacion-original-2026-10-24.md) |

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

## Defectos confirmados por QA

Cada uno está fijado con una prueba `xfail(strict=True)` en `tests/test_multiturn_context.py`. Cuando el defecto se corrija, la prueba empezará a pasar y la suite fallará hasta que se quite la marca.

| ID | Defecto | Ubicación | Prueba |
|---|---|---|---|
| QA1 | Un webhook repetido entre workers o tras un reinicio crea 2 borradores, porque el `request_id` es aleatorio. En un mismo proceso lo frena la caché volátil `seen_webhook_messages` (`api/app.py:131,185-195`). | `agent/hermes.py:240` | `test_duplicate_webhook_across_workers_or_restarts_is_idempotent_in_repository` |
| QA2 | No hay memoria conversacional. `AgentService.respond` solo recibe el turno actual, así que una frase como "de ese mismo" pierde el SKU anterior. | `agent/service.py:17`, `api/app.py:161,198` | `test_multiturn_chat_retains_product_context_across_turns` |
| QA3 | T08 por chat: "dame el descuento de siempre" crea un borrador a precio de lista sin informar `DiscountPolicyUnavailable`. | `agent/hermes.py:238` | `test_t08_chat_natural_language_discount_request_reports_policy_unavailable` |

**Casos que pasan:** T02, T03, T08 por `/v1/quotes`, T10 (`fromMe`, eco del bot y grupos), T19 (cero llamadas externas), payloads malformados (200 `ignored` o 422) e inyección de prompt (el precio de lista y el estado `DRAFT` se mantienen y el catálogo queda intacto).

## Guion de demo, menos de 2 min (modo `mock`)

Fuente: reporte QA de agy. Los comandos y opciones de la CLI se verificaron con `--help`; el recorrido completo todavía no se ha ejecutado de punta a punta.

1. **API (terminal 1):** `$env:LLM_PROVIDER='mock'; $env:WHATSAPP_SEND_ENABLED='false'; uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`
2. **Salud:** `uv run xeon health`. Debe mostrar `provider: mock`. *Por verificar:* el reporte esperaba el modelo `llama-3.3-70b-versatile`, pero en modo mock el modelo es `mock-xeon-v1`.
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
6. **Webhook:** un `POST /v1/channels/whatsapp/webhook` con `messages.upsert`, `fromMe=false` y el texto "Necesito 10 bultos de cemento en sede norte". La respuesta muestra la traza de las tres herramientas.

## Hallazgos que afectan la demo

Vienen de una inspección estática de `format_verified_context` en `src/xeon/agent/hermes.py:187-260`; ver D6 en [decisiones pendientes](decisiones-pendientes.md).

- **No hay tool-calling del LLM.** Las tres herramientas se ejecutan antes de llamar al modelo y su resultado se inyecta como contexto verificado. El LLM no elige herramientas. Estado: `implementado`, distinto de lo que describe el prompt original.
- **Fecha fija.** `evaluated_at` está escrita a mano como `2026-10-08T15:00:00+00:00` (línea 212), así que la vigencia `fresh`/`stale` no depende de la hora real.
- **Errores silenciados.** `except Exception: pass` (líneas 233 y 252) oculta fallos de stock y de borrador. Puede contradecir el principio "fuente caída no significa agotado" si no se informa al comprador.
- **Borradores duplicados.** El borrador automático usa un `request_id` aleatorio por mensaje (línea 240), de modo que un webhook repetido crea otro borrador. Contradice el principio 8 de [XeonContexto](../../XeonContexto.md).

# Contratos de las herramientas comerciales

Equivale al `tools_spec` del protocolo original. Define las entradas, salidas y reglas de las tres herramientas comerciales de `CommercialToolbelt` (llamado `HermesToolbelt` hasta la limpieza D9). Relacionado: [hito S2](hito-s2.md), [arquitectura actual](arquitectura-actual.md), [orquestación](orquestacion.md).

Revisado: 2026-10-24. Fuentes:

- Código: `src/xeon/agent/toolbelt.py` (antes `hermes.py`; los números de línea citados abajo corresponden a la versión anterior). Los marcadores de contexto pasaron de `HERMES_TOOL` a `XEON_TOOL`.
- Documento funcional: [XeonContexto §7](../../XeonContexto.md), líneas 133-139.

Estado de las tres herramientas: `implementado` (inspección estática).

## `search_products(query, *, limit=3)` → `SearchProductsOutcome`

Líneas 60-151.

- **Entrada:** texto libre, alias o SKU.
- **Salida:** `status`, `query`, `candidates[]`, `clarification_reason` y `message`. Cada candidato trae `sku`, `name`, `unit`, `unit_price` (texto de un `Decimal`), `currency`, `specs`, `source` y `catalog_version`.
- **Valores de `status`:**

| `status` | Cuándo ocurre |
|---|---|
| `clarification_required` | La consulta está vacía (`empty_query`), tiene medidas sin unidades (`missing_units`) o la referencia es ambigua sin candidatos (`ambiguous_reference`). |
| `exact_match` | El SKU o alias coincide exactamente. |
| `semantic_candidates` | Hay candidatos por puntuación de nombre, specs o descripción. Es léxica en memoria: el `pgvector` real sigue `planificado`. |
| `catalog_unavailable` | El catálogo falló. No equivale a agotado. |
| `not_found` | No hay candidatos. Desconocido no significa existencia cero. |

- **Regla:** el precio sale del catálogo, nunca del LLM.

## `get_stock_by_branches(*, sku, requested_branch_id, evaluated_at, requested_quantity=None)` → `StockByBranches`

Líneas 153-168.

- **Salida:** `local_available`, `shortfall`, `fulfillment_status` (`sufficient`, `partial` o `unknown`) e `items[]`. Cada ítem trae sede, cantidad, `kind` (`local`, `transfer` o `delivery`) y `freshness` (`fresh`, `stale` o `unknown`).
- **Regla:** solo consulta. No reserva stock ni promete stock vencido.

## `create_quote_draft(*, tenant_id, request_id, lines, discount_requested=False)` → `CreateQuoteResult`

Líneas 170-185.

- **Salida:** `QuoteDraftReady`, que contiene la cotización en estado `DRAFT` versión 1 calculada con `Decimal`, o un resultado de aclaración o error.
- **Reglas:**
  - Es idempotente por `(tenant_id, request_id)`.
  - Nunca aprueba la cotización.
  - Si se pide un descuento y no hay política, no inventa un porcentaje (`DiscountPolicyUnavailable`).

## Invariantes para cualquier cambio

- Ningún modelo aprueba cotizaciones, ejecuta SQL ni modifica inventario.
- Un cambio de contrato se registra aquí antes de implementarlo. Codex lo implementa y Opus lo audita.
- Ver los hallazgos de idempotencia y fecha fija en [hito S2](hito-s2.md).

## Contrato de corrección QA1–QA3 (definido por el orquestador, 2026-10-24)

El usuario decidió corregir los tres defectos antes de la demo, con historial corto enviado a Grok para QA2. Estado: **`implementado`** (2026-10-24): Codex lo implementó, el orquestador lo auditó y agy lo validó con mock y con Grok real. Ubicación: puerto `application/ports/conversation_memory.py`, adaptador `adapters/conversation/memory.py` y `CommercialToolbelt.prepare_verified_context`.

- **QA1, idempotencia:**
  - `AgentService.respond(message, *, conversation_key=None, request_id=None)`.
  - El webhook pasa `request_id=f"wa-{instance}-{external_message_id}"` y `conversation_key=f"wa-{instance}-{sender_number}"`.
  - `format_verified_context` usa ese `request_id` en `create_quote_draft`. Si es `None` (chat sin id), conserva el aleatorio.
  - La idempotencia `(tenant_id, request_id)` del repositorio evita el duplicado incluso entre workers.
- **QA2, memoria:**
  - Puerto `ConversationMemory` en `application/ports/`, con métodos `history(key) -> tuple[ChatMessage, ...]`, `last_sku(key) -> str | None` y `record(key, user, assistant, sku)`.
  - Adaptador en memoria acotado: `conversation_max_turns` (6 por defecto) y un máximo de conversaciones con expulsión LRU.
  - `/v1/chat` usa `conversation_id` como clave.
  - El historial se envía a Grok entre el `system` y el turno actual.
  - Si el turno actual no identifica ningún producto (`not_found` o `ambiguous_reference`) pero hay un `last_sku`, las herramientas usan ese SKU de forma determinista.
- **QA3, descuentos:**
  - Se detecta la intención de descuento (descuento, rebaja, precio especial o un porcentaje) y se pasa `discount_requested=True`.
  - Si el resultado es `DiscountPolicyUnavailable`, el contexto informa «no hay política de descuentos aprobada; no se aplica ni se inventa un porcentaje» y no se crea el borrador.
- **Invariantes:**
  - El modelo nunca calcula precios.
  - Las pruebas siguen en `mock`.
  - Las marcas `xfail` de QA1–QA3 se retiran porque las pruebas pasan a ser obligatorias.

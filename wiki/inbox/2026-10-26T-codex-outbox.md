---
tags:
  - xeon/estado
---

# Outbox Kapso y recepción durable

Fecha: 2026-10-26. Aporte: Codex en `feat/kapso-outbox`, worktree `xo`. Estado: implementado y verificado localmente; pendiente de integración en páginas compartidas de la wiki. Fuente: encargo del orquestador, código, pruebas y [guía operativa](../../docs/PERSISTENCIA.md). Páginas relacionadas: [arquitectura actual](../pages/arquitectura-actual.md), [canal Kapso](../pages/canal-kapso.md), [estado del corte](../pages/estado-del-corte.md).

## Corte y garantía

- `STATE_STORE=postgres` añade la migración Alembic `0003_kapso_outbox`: `inbound_deliveries` guarda el evento v2 crudo después de validar HMAC, tipo y campos del mensaje y **antes** de responder 200. Restricción única `(tenant_id, instance, message_id)` evita encolar dos veces la misma entrada. El despacho posterior procesa cada mensaje dentro de la transacción por conversación existente: `processed_events`, embudo, carrito, borrador, estado de entrada `done` y salida `pending` se confirman juntos. Una caída antes del commit deja la entrada pendiente para reintento.
- `outbound_deliveries` registra las respuestas del embudo y los avisos posteriores a la revisión humana con clave única de envío. La aprobación/rechazo del asesor y su aviso saliente se guardan en la misma transacción. El trabajador reclama mensajes con `FOR UPDATE SKIP LOCKED` y lease, despacha a Kapso y marca `pending`/`sent`/`failed`. Reintenta errores de red, 5xx, 408, 409, 425 y 429 con backoff exponencial y máximo cinco intentos; otros 4xx son definitivos. Eventos y envíos del mismo cliente esperan al anterior para conservar el orden durante reintentos. No se registran teléfonos ni textos en logs.
- En `STATE_STORE=memory` continúa el envío inmediato y la tarea local anterior, **sin durabilidad**. Con PostgreSQL, el trabajador corre como tarea de fondo de la API y cierra antes de liberar el contenedor. Para ejecutarlo aparte: configura `DELIVERY_WORKER_ENABLED=false` en la API y `STATE_STORE=postgres`, `WHATSAPP_SEND_ENABLED=true` en el proceso trabajador; ejecuta `uv run --locked --group db python scripts/run_delivery_worker.py`. La API persiste entradas aunque el trabajador esté detenido. `DELIVERY_POLL_SECONDS` configura el intervalo.
- Garantía **al menos una vez** hacia Kapso. La clave de envío evita duplicados locales después de un envío marcado `sent`, pero una caída después de la aceptación remota y antes de persistir ese resultado puede reenviar. La API oficial de [texto](https://docs.kapso.ai/docs/whatsapp/send-messages/text) y [botones](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons) no documenta una clave de idempotencia para `POST /messages`; no se envía una cabecera inventada. `X-Idempotency-Key` está documentada para [webhooks entrantes](https://docs.kapso.ai/docs/platform/webhooks/overview), no como deduplicación de salidas. Kapso [reintenta webhooks sin HTTP 200](https://docs.kapso.ai/docs/platform/webhooks/advanced). `sent` significa aceptación del proveedor, no entrega al teléfono.

## Evidencia

Commit funcional: `5b4c988` (`Feat: :sparkles: AddDurableKapsoOutbox`).

Archivos nuevos: `migrations/versions/0003_kapso_outbox.py`, `src/xeon/application/ports/delivery.py`, `src/xeon/application/delivery_worker.py`, `src/xeon/adapters/persistence/postgres/delivery.py`, `scripts/run_delivery_worker.py`, `tests/test_delivery_worker.py`. Cambios en el adaptador Kapso (código HTTP de error), `AppContainer`, webhook API, panel, `AdvisorReview`, Settings, esquema SQL, `tests/integration/test_state_postgres.py`, `docs/PERSISTENCIA.md`, `docs/ARCHITECTURE.md` y `docs/XeonContexto.md`.

Pruebas con dobles HTTP: 503 → reintento y un envío aceptado; 400 → `failed` definitivo; 409 → reintento; clave repetida no reenvía. Integración PostgreSQL: webhook firmado persistido antes del acuse sin ejecutar agente; procesamiento y outbox sobreviven dos reinicios; decisión del asesor y aviso se confirman juntos; separación y orden de mensajes; backoff verificable. Migración probada de `0002_advisor_inbox` a `0003_kapso_outbox`. No hubo envíos reales ni llamadas LLM pagadas: costo 0.

Perfil CI: `uv run --locked --group db ruff check .`, `ruff format --check .`, `mypy src`, `pytest -q`: verdes. Perfil completo `db`, `db-test`, `evals`, `graph`: Ruff/formato verdes; `mypy src evals` (116 archivos), pytest normal, 21/21 integraciones y offline 66 PASS, 0 FAIL, 0 ERROR. Servicios iniciados con `docker compose -f compose.state.yaml up -d --wait` y `docker compose -f compose.db-test.yaml up -d --wait`; ambos se apagaron con `down` sin borrar volúmenes.

Verificación adicional: `scripts/check_doc_links.py` revisó 60 enlaces relativos, 0 rotos. Graphify local regenerado sin LLM: 2997 nodos, 9704 aristas, 170 comunidades y 325 archivos; 0 rutas excluidas y 0 valores con aspecto de clave. Se restauraron los hubs versionados de `wiki/graph/` tras generar el grafo para evitar nombres dependientes del worktree. Dos archivos `.sql` no produjeron nodos AST porque el grupo `graph` no incluye `tree_sitter_sql`; el grafo completo ignorado permanece en `graphify-out/`.

## Límites

El resultado remoto entre aceptación y registro local sigue siendo ambiguo; para exactamente una vez se necesita una garantía de idempotencia documentada por Kapso/Meta o conciliación fiable por clave de negocio. Cinco fallos de entrada o salida dejan registro `failed` para atención manual; no hay panel de redrive ni alerta automática. El aviso libre del asesor puede fallar fuera de la ventana de servicio de WhatsApp; requiere plantilla aprobada en un corte posterior. Los payloads entrantes y las respuestas salientes incluyen datos personales: se restringe el acceso a la base y la retención continúa **POR DEFINIR** por el usuario. El orden por conversación difiere de un orden total entre tenants o destinatarios. Falta prueba de carga y validación en sandbox real.

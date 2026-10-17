# Cambios de Juan Pablo Conde

## 2026-10-17 — Confirmación conversacional de SKU

### Objetivo

Impedir que una coincidencia descriptiva se trate como producto confirmado. XEON debe mostrar los
SKU candidatos y esperar a que el comprador responda explícitamente con uno de ellos antes de
consultar inventario o crear un borrador de cotización.

### Reglas implementadas

- Una coincidencia exacta por SKU o alias mantiene el flujo comercial existente.
- Una búsqueda descriptiva con candidatos devuelve `confirmation_required` y no ejecuta
  `get_stock_by_branches` ni `create_quote_draft`.
- Los candidatos pendientes se conservan por `conversation_id` en la API y por
  `instancia + sender_jid` en WhatsApp.
- Solo se acepta un SKU incluido en la lista pendiente. Un SKU diferente mantiene bloqueadas las
  operaciones comerciales.
- Al confirmar, se recuperan la cantidad y la sede de la solicitud original; una cantidad o sede
  explícita en la confirmación tiene prioridad.
- La memoria está limitada a 1024 conversaciones y vive en el proceso. Se pierde al reiniciar;
  todavía no sustituye la persistencia pendiente en PostgreSQL.

### Flujo verificable

1. El comprador escribe: `necesito 50 bultos para fundir una placa y pegar ladrillo`.
2. XEON presenta `CEM-50` como candidato y solicita que se confirme el SKU.
3. No se consulta stock ni se crea un `DRAFT` durante ese primer turno.
4. El comprador responde: `Confirmo el SKU CEM-50` en la misma conversación.
5. XEON registra la selección, consulta el stock sintético y crea el borrador con la cantidad
   conservada del primer turno.

### Cobertura

- Flujo directo de `HermesToolbelt`.
- Continuidad mediante `POST /v1/chat` usando el mismo `conversation_id`.
- Continuidad mediante dos webhooks de WhatsApp del mismo remitente.
- Rechazo de un SKU que no pertenece a los candidatos pendientes.
- Perfil `mock`; no se realizan llamadas pagadas ni conexiones externas.

### Commits

- `Feat: :sparkles: RequireConversationalSkuConfirmation`
- `Test: :test_tube: CoverSkuConfirmationGuards`
- `Fix: :bug: NarrowPendingConversationKey`
- `Docs: :memo: DocumentCondeSkuConfirmation`

### Verificación

- `uv sync --locked`: 36 paquetes resueltos y comprobados.
- `uv run ruff check .`: sin errores.
- `uv run ruff format --check .`: 61 archivos formateados.
- `uv run mypy src`: 39 archivos sin errores.
- `uv run pytest`: 83 pruebas aprobadas.

# Arquitectura base de XEON

## Estado implementado

El sistema conecta tres planos a traves de `AppContainer` (composition root) bajo arquitectura
hexagonal:

```text
POST /v1/chat   POST /v1/channels/whatsapp/webhook (Evolution API)
      |                                 |
      +----------------+----------------+
                       |
                       v
        AgentService + HermesToolbelt ---- system prompt acotado
         /                             \
        v                               v
     LLMPort                    Herramientas comerciales autorizadas:
      /   \                     - search_products (Exacto + RAG semantico + JSONB specs)
   Grok   Mock/Groq/Hermes      - get_stock_by_branches (SQL / Snapshots deterministas)
                                - create_quote_draft (Calculo Decimal ACID)

POST /v1/quotes  GET /v1/quotes/{id}
      |
      v
 AppContainer (composition root)
      |
      +--> CreateQuoteDraft / GetQuoteDraft
      +--> ProductCatalog (memoria hibrida: SKU/alias, specs JSONB y contexto RAG)
      +--> QuoteDraftRepository (memoria, clave idempotente tenant_id+request_id)
      |
      v
 domain: Product(specs, description_context), Money(Decimal), QuoteLine,
         Quote(status=DRAFT, version=1)

GET /v1/stock  CLI stock show
      |
      v
 AppContainer
      |
      +--> GetStockByBranches
      +--> BranchInventory (memoria, snapshots sinteticos)
      |
      v
 domain: StockSnapshot(valid_until), AvailabilityKind(local|transfer|delivery),
         Freshness(fresh|stale|unknown),
         FulfillmentStatus(sufficient|partial|unknown)
```

### 1. Orquestacion con Hermes, Groq y Grok API
- `grok` es el perfil predeterminado. Reutiliza `OpenAICompatibleLLM` mediante `LLMPort` con
  el modelo `grok-4.20-0309-non-reasoning` y la pasarela del reto `https://api.reto.pltk.mx/v1`.
  La clave se toma por defecto del archivo local `secrets/grok_api_key.txt`; en Compose se monta
  como `/run/secrets/grok_api_key`. Falta el smoke test real autorizado por el orquestador.
- `MockLLM` se selecciona explicitamente en las pruebas y no realiza llamadas externas.
- El perfil `groq` exige una credencial explicita (`GROQ_API_KEY` o `GROQ_API_KEY_FILE`) y consume
  el endpoint OpenAI-compatible de Groq (`https://api.groq.com/openai/v1`) como alternativa.
- El perfil `hermes` sigue disponible como alternativa local. La fabrica rechaza un modelo Grok
  vacio aun cuando existe un modelo predeterminado.
- `HermesToolbelt` conecta el turno conversacional con las herramientas deterministas del backend:
  identifica referencias candidatas mediante busqueda hibrida (`search_products`), consulta stock
  por sede (`get_stock_by_branches`) y crea borradores (`create_quote_draft`).
- `CommercialScopePolicy` clasifica el alcance de la consulta antes del modelo. Las solicitudes
  ajenas al comercio se bloquean sin llamar al LLM; las mixtas conservan solo la parte comercial
  para la busqueda y explican el limite al cliente.
- `CustomerResponsePolicy` revisa las respuestas de proveedores reales y sustituye salidas que
  exponen codigos internos, marcadores tecnicos o enlaces no autorizados. El perfil `mock` conserva
  sus marcadores de diagnostico para las pruebas locales.
- `ConversationMemory` conserva un historial corto por conversacion, acotado por turnos y LRU;
  el historial se entrega como mensajes `user`/`assistant` al modelo. No hay carrito persistente
  ni seleccion confirmada de SKU por conversacion en este corte.

### 1.1. Catalogo sintetico ampliado

`SyntheticProductSeed` genera 2000 productos ficticios con procedencia explicita. El catalogo
en memoria los indexa por SKU, alias y atributos; el inventario en memoria crea snapshots
sinteticos correspondientes. Son datos de demostracion, no precios ni existencias empresariales.

### 1.2. Memoria de conversacion e idempotencia
- `ConversationMemory` (puerto en `application/ports/conversation_memory.py`) guarda por
  conversacion los ultimos `conversation_max_turns` turnos y el ultimo SKU identificado;
  `adapters/conversation/memory.py` la implementa en proceso con expulsion LRU.
- `AgentService.respond(message, *, conversation_key, request_id)` envia ese historial al LLM y,
  ante referencias como «ese mismo», usa el ultimo SKU de forma determinista.
- El webhook deriva `request_id=wa-{instance}-{external_message_id}`: un mensaje repetido reutiliza
  el mismo borrador gracias a la idempotencia `(tenant_id, request_id)`.
- Un pedido de descuento detectado en el chat se propaga como `discount_requested=True`; sin
  politica no se crea borrador.

### 1.3. XEON CLI (Tactical Agent Shell)
- `xeon` sin subcomando abre el shell (`src/xeon/shell/`): `theme` (tokens), `commands` (alias
  puros), `session` (estado y motor en proceso o HTTP con `--api`), `render` (vistas Rich por
  ancho) y `app` (bucle y ciclo de vida de la terminal).
- Es una interfaz de entrada como FastAPI y Typer: delega en `build_container`/`AgentService` y no
  contiene reglas comerciales. Degrada a texto plano con `NO_COLOR`, sin TTY o sin UTF-8.

### 2. Canal WhatsApp con Kapso y Evolution API
- `WHATSAPP_CHANNEL=kapso` selecciona por defecto el adaptador de envio de Kapso cuando
  `WHATSAPP_SEND_ENABLED=true`; requiere ID del numero y clave explicita. Evolution API sigue
  disponible con `WHATSAPP_CHANNEL=evolution`.
- `POST /v1/channels/whatsapp/kapso/webhook` comprueba HMAC-SHA256 del cuerpo crudo antes de
  interpretar JSON. Solo acepta eventos `whatsapp.message.received` de texto, incluidos lotes;
  deduplica IDs en memoria y programa el turno comercial y el envio en segundo plano.
  El acuse `processed` significa que se programo el trabajo, no que WhatsApp entrego el mensaje.
- `KapsoChannelAdapter` envia texto a la API Meta proxy con `X-API-Key`. El webhook requiere
  secreto configurado; no se admiten mensajes proactivos ni plantillas fuera de la ventana de 24 h.
- La deduplicacion y el trabajo de fondo son locales al proceso. Persistencia, cola durable,
  observabilidad de entregas y ensayo real en el sandbox quedan pendientes.
- `POST /v1/channels/whatsapp/webhook` recibe eventos `messages.upsert` desde una instancia local de
  **Evolution API**, ignorando mensajes propios (`fromMe=True`), estados y grupos.
- Cuando `WHATSAPP_SEND_ENABLED=true`, `EvolutionAPIChannelAdapter` despacha la respuesta verificada
  a `POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}` usando la cabecera `apikey`
  sanitizada.

### 3. Modelo de Datos Hibrido Empresarial (SQL + NoSQL `JSONB` + RAG `pgvector`)
Para responder con agilidad al catalogo polimorfico de una ferreteria/agroferreteria sin perder
exactitud financiera, la arquitectura separa tres responsabilidades dentro de PostgreSQL 17 (y su
equivalente en memoria para pruebas):
- **Capa SQL Relacional Estricta:** Precios (`Decimal` / `NUMERIC`), unidades comerciales, stock por
  sede (`fresh` / `stale` / `unknown`), borradores de cotizacion (`DRAFT`), versiones y llaves de
  idempotencia (`tenant_id + request_id`).
- **Capa NoSQL Documental (`JSONB` / `Product.specs`):** Atributos tecnicos variables por categoria
  (`calibre`, `presion_psi`, `diametro`, `peso_kg`, `norma`), matrices de descuento y payloads
  crudos de webhooks de Evolution API sin requerir migraciones rigidas por cada nuevo atributo.
- **Capa Vectorial / RAG Semantico (`pgvector` / `Product.description_context`):** Resuelve lenguaje
  coloquial o ambiguo del comprador para proponer `SKU`s candidatos. El RAG nunca almacena ni
  decide precios ni existencias.

## Trazabilidad del corte

| Caso | Resultado esperado | Donde se cubre |
|---|---|---|
| T01 | SKU y cantidad validos crean un DRAFT exacto, version 1 | `CreateQuoteDraft`, `POST/GET /v1/quotes`, CLI `quotes create/show` |
| T02 | «El coso del aire» exige aclaracion; no inventa SKU | `ClarificationRequired.ambiguous_reference`, `HermesToolbelt.search_products` |
| T03 | Medidas sin unidades exigen aclaracion | `ClarificationRequired.missing_units`, `HermesToolbelt.search_products` |
| T04 | Producto en otra sede: origen y tipo local/traslado/entrega | `GetStockByBranches`, `GET /v1/stock`, CLI `stock show` |
| T05 | Pedido parcialmente cubierto: faltante local y alternativas observadas | `explain_local_fulfillment`, `GetStockByBranches`, `GET /v1/stock`, CLI `stock show --requested-quantity` |
| T06 | Catalogo caido no se reporta como agotado | `CatalogUnavailable`, `HermesToolbelt.search_products` |
| T07 | Snapshot vencido: senala antiguedad y no promete disponibilidad firme | `classify_freshness`, `GetStockByBranches`, `GET /v1/stock`, CLI `stock show --evaluated-at` |
| T08 | Descuento pedido sin politica: no se inventa porcentaje | `DiscountPolicyUnavailable` |
| T11 | Consulta fuera del alcance comercial o salida insegura | `CommercialScopePolicy`, `CustomerResponsePolicy` y pruebas del arnes |
| T19 | Perfil mock: cero llamadas a proveedores LLM | `/health`, `/v1/chat`, `/v1/channels/whatsapp/webhook` y suite con `LLM_PROVIDER=mock` |

## Fronteras que no deben romperse

- Hermes interpreta y busca candidatos (RAG + `specs`); el dominio y la aplicacion deciden precios,
  descuentos, impuestos, inventario y estados desde la base de datos.
- La API transforma HTTP y delega. No contiene reglas comerciales.
- Los adaptadores (Groq, Evolution API) conocen protocolos externos; el puerto no conoce HTTPX.
- La identidad de una conversacion en WhatsApp no implica identidad comercial ni permiso de vendedor.
- Desconocido o fuente caida no significan agotado.

## Pendiente (no implementado)

- Persistencia en PostgreSQL 17 (`SQL + JSONB + pgvector`) con Alembic.
- Generacion de PDF con WeasyPrint, aprobacion humana y politica de descuentos versionada.
- Flujo copiloto para el trabajador (post-MVP): notificacion por Gmail (`WorkerNotificationPort` / SMTP) con tabla de pre-facturacion, hoja de alistamiento multi-sede, semaforo de descuentos del harness y confirmacion humana antes de facturar (`PENDING_APPROVAL` -> `APPROVED_FOR_BILLING`) con aviso de regreso al WhatsApp del cliente.
- Registro y notificacion real al trabajador cuando un producto solicitado no figura en el catalogo.

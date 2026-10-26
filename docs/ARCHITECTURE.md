# Arquitectura base de XEON

## Conector SQL por ferretería (fase 2)

`DATA_SOURCE` selecciona el adaptador en `AppContainer`. El valor predeterminado `synthetic`
usa los datos de demostración; `sql` carga `connectors/<tenant>.yaml` y una URL local de `secrets/`.
Los puertos `ProductCatalog`, `BranchInventory` y `BranchDirectory` aíslan el dominio del motor.
`GuidedFunnel` resuelve las sedes ofrecidas contra `BranchDirectory`; `CommercialExecutor`
consulta stock con el id verificado. Precio y subtotal siguen bajo `Money(Decimal)` y
`CreateQuoteDraft`. SQLAlchemy se importa solo al seleccionar SQL. Ver
[guía de conexión](CONECTOR_FERRETERIA.md) para mapeos, permisos y límites.

## Estado implementado

### Persistencia operativa D15 A

`STATE_STORE=memory` mantiene los adaptadores de desarrollo y pruebas. Con
`STATE_STORE=postgres`, una base PostgreSQL 17 **propia de XEON** persiste
`FunnelState`, `QuoteCart`, `ConversationMemory`, `QuoteDraftRepository` y los IDs de
webhook procesados. SQLAlchemy Core y Alembic se cargan solo en ese perfil, desde
`XEON_STATE_URL_FILE` bajo `secrets/`. Una transacción con bloqueo por conversación
serializa los turnos entre workers; el carrito verifica la versión y el evento
entrante tiene clave única. La base del conector D13 sigue separada y de solo
lectura. Ver [guía de persistencia](PERSISTENCIA.md).

### Panel del asesor y estado persistido

El panel `/panel` usa `AdvisorInbox` y `AdvisorReview`; solo el asesor autenticado
puede pasar un borrador confirmado a `APPROVED_FOR_BILLING` o `RECHAZADO_POR_ASESOR`.
Con `STATE_STORE=postgres`, la migración `0002_advisor_inbox` conserva los eventos
por tenant. La revisión bloquea evento y borrador en una transacción, de modo que
una decisión concurrente recibe conflicto. Las sesiones del panel expiran en memoria:
solo se retiene la huella HMAC del token. Ver [panel](PANEL_ASESOR.md).

### Embudo guiado D14

`GuidedFunnel` es el único flujo para `/v1/chat`, CLI y Kapso. El estado
`FunnelState` vive por conversación en el repositorio elegido; `Reply` presenta opciones independientes del canal.
El paso de producto consulta `search_products` y las operaciones del carrito pasan por el mismo
`CommercialExecutor` y `QuoteCart`. Las respuestas de botones usan el id exacto;
el texto de pasos cerrados se valida como una opción permitida o `no_encaja`. La configuración
predeterminada usa el embudo y el evaluador recorre sus opciones por id o número.

Las políticas de `config/policies/<tenant>.yaml` se validan con Pydantic. La plantilla `whatsapp`
es demo para Colombia; un campo nulo queda pendiente de confirmar con un asesor. Confirmar cambia
el borrador a `CONFIRMADO_POR_CLIENTE` y emite un evento sin datos del cliente a `AdvisorNotifier`;
no aprueba, reserva ni factura. El adaptador inicial del notificador solo registra metadatos.

El sistema conecta tres planos a traves de `AppContainer` (composition root) bajo arquitectura
hexagonal:

```text
POST /v1/chat   POST /v1/channels/whatsapp/kapso/webhook (Kapso, HMAC)
      |                                 |
      +----------------+----------------+
                       |
                       v
        AgentService -> GuidedFunnel -> CommercialExecutor
                                            |          |
                                       QuoteCart  CommercialToolbelt
         /                             \
        v                               v
     LLMPort                    Herramientas comerciales autorizadas:
      /   \                     - search_products (SKU/alias + puntuacion lexical de specs)
   Grok   Mock/Groq            - get_stock_by_branches (Snapshots sinteticos)
                                - create_quote_draft (Calculo Decimal en memoria)

POST /v1/quotes  GET /v1/quotes/{id}
      |
      v
 AppContainer (composition root)
      |
      +--> CreateQuoteDraft / GetQuoteDraft
      +--> ProductCatalog (sintético por defecto; SQL configurable)
      +--> QuoteDraftRepository (memoria o PostgreSQL propio, clave idempotente tenant_id+request_id)
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
      +--> BranchInventory (sintético por defecto; SQL configurable)
      +--> BranchDirectory (ids, nombres visibles y alias)
      |
      v
 domain: StockSnapshot(valid_until), AvailabilityKind(local|transfer|delivery),
         Freshness(fresh|stale|unknown),
         FulfillmentStatus(sufficient|partial|unknown)
```

### 1. Agente comercial con Grok, Groq y mock
- `grok` es el perfil predeterminado. Reutiliza `OpenAICompatibleLLM` mediante `LLMPort` con
  el modelo `grok-4.6` y la pasarela del reto `https://api.reto.pltk.mx/v1`.
  La clave se toma por defecto del archivo local `secrets/grok_api_key.txt`; en Compose se monta
  como `/run/secrets/grok_api_key`. El orquestador verificó `grok-4.6` mediante una llamada real con el adaptador de XEON.
- `MockLLM` se selecciona explicitamente en las pruebas y no realiza llamadas externas.
- El perfil `groq` exige una credencial explicita (`GROQ_API_KEY` o `GROQ_API_KEY_FILE`) y consume
  el endpoint OpenAI-compatible de Groq (`https://api.groq.com/openai/v1`) como alternativa.
- La fabrica rechaza un modelo Grok vacio aun cuando existe uno predeterminado.
- `CommercialToolbelt` conecta el turno conversacional con las herramientas deterministas del backend:
  identifica referencias candidatas mediante busqueda lexical en memoria (`search_products`), consulta stock
  por sede (`get_stock_by_branches`) y crea borradores (`create_quote_draft`).
- El contexto verificado usa marcadores internos `[XEON_TOOL:...]`; no autorizan al modelo a
  calcular precios ni a ejecutar herramientas. El embudo emite respuestas desde plantillas.
- `GuidedFunnel` clasifica texto libre de los pasos cerrados a una opción permitida; los ids de
  botón se procesan sin LLM. Las operaciones evidentes del carrito usan `CommercialExecutor`.
- El texto del proveedor se limita a clasificar opciones cerradas; no se publica directamente.
- `ConversationMemory` conserva historial corto, opciones pendientes y datos de proyecto.
  `CartRepository` guarda por conversacion un `QuoteCart` versionado en memoria o en
  PostgreSQL propio; las lineas confirmadas producen borradores `DRAFT` calculados con
  `Decimal`. El perfil PostgreSQL sobrevive a reinicios; no hay aprobacion automatica.

### 1.1. Catalogo sintetico ampliado

`SyntheticProductSeed` genera 2000 productos ficticios con procedencia explicita. El catalogo
en memoria los indexa por SKU, alias y atributos; el inventario en memoria crea snapshots
sinteticos correspondientes. Son datos de demostracion, no precios ni existencias empresariales.

### 1.2. Memoria de conversacion e idempotencia
- `ConversationMemory` (puerto en `application/ports/conversation_memory.py`) guarda por
  conversacion los ultimos `conversation_max_turns` turnos y el ultimo SKU identificado;
  `adapters/conversation/memory.py` la implementa en proceso con expulsion LRU.
- `AgentService.respond_reply(message, *, conversation_key, request_id, option_id)` delega al
  embudo; `respond` adapta la misma respuesta al CLI. El historial y los datos de proyecto
  permanecen en memoria por conversacion.
- El webhook deriva `request_id=kapso-{message.id}`: un mensaje repetido reutiliza
  el mismo borrador gracias a la idempotencia `(tenant_id, request_id)`.
- Un pedido de descuento detectado en el chat se propaga como `discount_requested=True`; sin
  politica no se crea borrador.

### 1.3. XEON CLI (Tactical Agent Shell)
- `xeon` sin subcomando abre el shell (`src/xeon/shell/`): `theme` (tokens), `commands` (alias
  puros), `session` (estado y motor en proceso o HTTP con `--api`), `render` (vistas Rich por
  ancho) y `app` (bucle y ciclo de vida de la terminal).
- Es una interfaz de entrada como FastAPI y Typer: delega en `build_container`/`AgentService` y no
  contiene reglas comerciales. Degrada a texto plano con `NO_COLOR`, sin TTY o sin UTF-8.

### 2. Canal WhatsApp unico con Kapso
- Cuando `WHATSAPP_SEND_ENABLED=true`, el contenedor crea `KapsoChannelAdapter`; requiere
  `KAPSO_PHONE_NUMBER_ID` y clave explicita por valor o archivo.
- `POST /v1/channels/whatsapp/kapso/webhook` comprueba HMAC-SHA256 del cuerpo crudo antes de
  interpretar JSON. Solo acepta eventos `whatsapp.message.received` de texto o respuesta interactiva,
  incluidos lotes;
  deduplica IDs en memoria o PostgreSQL propio. En PostgreSQL, la migracion `0003_kapso_outbox`
  guarda el evento validado antes del acuse y un trabajador procesa el turno y entrega la respuesta.
  El acuse `processed` significa persistencia local, no entrega al telefono.
- `KapsoChannelAdapter` envia texto o `interactive` (botones/listas) a la API oficial de WhatsApp via Kapso Meta proxy con
  `X-API-Key`. El webhook requiere secreto configurado; no se admiten mensajes proactivos ni
  plantillas fuera de la ventana de 24 h.
- La deduplicacion usa memoria local o una clave unica en PostgreSQL propio. La cola durable de
  entrada y salida existe en el perfil PostgreSQL; un trabajador puede correr dentro de la API o
  aparte. La entrega es al menos una vez, porque Kapso no documenta idempotencia de envio.
  Observabilidad operativa de entregas y prueba de carga quedan pendientes. El usuario confirmo un ensayo
  real en el sandbox con respuesta comercial por WhatsApp; eso no prueba entrega general.
- El procesamiento usa `conversation_key=kapso-{phone_number_id}-{phone}` y
  `request_id=kapso-{message.id}`; el repositorio de borradores conserva la idempotencia por
  `(tenant_id, request_id)`.

### 3. Modelo de Datos Hibrido Empresarial (SQL + NoSQL `JSONB` + RAG `pgvector`)
La base híbrida comercial con `pgvector` sigue planeada (D12: la recuperación vectorial será una herramienta más de un agente con herramientas; precios, stock y totales siguen saliendo de consultas directas). El catálogo e inventario son sintéticos o del conector SQL; el estado operativo puede persistir en PostgreSQL propio mediante D15 A. La arquitectura futura separa tres responsabilidades:
- **Capa SQL Relacional Estricta:** Precios (`Decimal` / `NUMERIC`), unidades comerciales, stock por
  sede (`fresh` / `stale` / `unknown`), borradores de cotizacion (`DRAFT`), versiones y llaves de
  idempotencia (`tenant_id + request_id`).
- **Capa NoSQL Documental (`JSONB` / `Product.specs`):** Atributos tecnicos variables por categoria
  (`calibre`, `presion_psi`, `diametro`, `peso_kg`, `norma`), matrices de descuento y payloads
  crudos de webhooks de Kapso sin requerir migraciones rigidas por cada nuevo atributo.
- **Capa Vectorial / RAG Semantico (`pgvector` / `Product.description_context`):** Resuelve lenguaje
  coloquial o ambiguo del comprador para proponer `SKU`s candidatos. El RAG nunca almacena ni
  decide precios ni existencias.

## Trazabilidad del corte

| Caso | Resultado esperado | Donde se cubre |
|---|---|---|
| T01 | SKU y cantidad validos crean un DRAFT exacto, version 1 | `CreateQuoteDraft`, `POST/GET /v1/quotes`, CLI `quotes create/show` |
| T02 | «El coso del aire» exige aclaracion; no inventa SKU | `ClarificationRequired.ambiguous_reference`, `CommercialToolbelt.search_products` |
| T03 | Medidas sin unidades exigen aclaracion | `ClarificationRequired.missing_units`, `CommercialToolbelt.search_products` |
| T04 | Producto en otra sede: origen y tipo local/traslado/entrega | `GetStockByBranches`, `GET /v1/stock`, CLI `stock show` |
| T05 | Pedido parcialmente cubierto: faltante local y alternativas observadas | `explain_local_fulfillment`, `GetStockByBranches`, `GET /v1/stock`, CLI `stock show --requested-quantity` |
| T06 | Catalogo caido no se reporta como agotado | `CatalogUnavailable`, `CommercialToolbelt.search_products` |
| T07 | Snapshot vencido: senala antiguedad y no promete disponibilidad firme | `classify_freshness`, `GetStockByBranches`, `GET /v1/stock`, CLI `stock show --evaluated-at` |
| T08 | Descuento pedido sin politica: no se inventa porcentaje | `DiscountPolicyUnavailable` |
| T10 | Webhook Kapso firmado: valida HMAC, ignora eventos ajenos y no-texto, deduplica mensajes | `POST /v1/channels/whatsapp/kapso/webhook`, `tests/test_kapso_channel.py`, `tests/test_multiturn_context.py` |
| T11 | Consulta fuera del alcance comercial o salida insegura | `GuidedFunnel`, clasificación cerrada y pruebas del arnes |
| T19 | Perfil mock: cero llamadas a proveedores LLM | `/health`, `/v1/chat`, webhook Kapso y suite con `LLM_PROVIDER=mock` |

## Fronteras que no deben romperse

- `CommercialToolbelt` identifica candidatos en el catalogo (sintetico o SQL); el dominio y la aplicacion
  deciden precios, descuentos, inventario y estados desde datos verificados del backend. La base
  empresarial y el calculo de impuestos estan pendientes.
- La API transforma HTTP y delega. No contiene reglas comerciales.
- Los adaptadores (Grok, Groq, Kapso) conocen protocolos externos; el puerto no conoce HTTPX.
- La identidad de una conversacion en WhatsApp no implica identidad comercial ni permiso de vendedor.
- Desconocido o fuente caida no significan agotado.

## Pendiente (no implementado)

- Índice híbrido comercial en PostgreSQL 17 (`SQL + JSONB + pgvector`); la persistencia operativa con Alembic ya es opcional mediante D15 A.
- Generacion de PDF con WeasyPrint y politica de descuentos versionada.
- Flujo copiloto para el trabajador (post-MVP): notificacion por Gmail (`WorkerNotificationPort` / SMTP) con tabla de pre-facturacion, hoja de alistamiento multi-sede, semaforo de descuentos del harness y confirmacion humana antes de facturar (`PENDING_APPROVAL` -> `APPROVED_FOR_BILLING`) con aviso de regreso al WhatsApp del cliente.
- Conectores `rest` y `csv` de `DATA_SOURCE` (hoy solo `synthetic` y `sql`).
- Registro y notificacion real al trabajador cuando un producto solicitado no figura en el catalogo.

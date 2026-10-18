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
   Mock   Groq API              - get_stock_by_branches (SQL / Snapshots deterministas)
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

### 1. Orquestacion con Hermes y Groq API
- `MockLLM` es el perfil predeterminado y garantiza cero llamadas externas.
- El perfil `groq` exige una credencial explicita (`GROQ_API_KEY` o `GROQ_API_KEY_FILE`) y consume
  el endpoint OpenAI-compatible de Groq (`https://api.groq.com/openai/v1`).
- `HermesToolbelt` conecta el turno conversacional con las herramientas deterministas del backend:
  identifica referencias candidatas mediante busqueda hibrida (`search_products`) y guarda una
  seleccion pendiente por conversacion. El cliente elige por nombre o numero de opcion; el SKU se
  conserva solo en el contexto interno. Solo despues de esa seleccion consulta stock por sede
  (`get_stock_by_branches`) y crea borradores (`create_quote_draft`).
- `CommercialScopePolicy` clasifica el mensaje antes del LLM. Cortesia y ayuda operativa se
  resuelven localmente; temas ajenos al comercio ferretero se rechazan; una solicitud mixta conserva
  solo su parte comercial.
- `CustomerResponsePolicy` aplica una defensa de salida: si el modelo filtra codigos, etiquetas
  internas o enlaces no registrados, se reemplaza su texto por una respuesta segura construida con
  datos verificados.

### 2. Canal WhatsApp sin costo con Evolution API
- `POST /v1/channels/whatsapp/webhook` recibe eventos `messages.upsert` desde una instancia local de
  **Evolution API**, ignorando mensajes propios (`fromMe=True`), estados y grupos.
- Cuando `WHATSAPP_SEND_ENABLED=true`, `EvolutionAPIChannelAdapter` despacha la respuesta verificada
  a `POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}` usando la cabecera `apikey`
  sanitizada.

### 2.1. Sesión comercial y carrito en memoria

- `HermesToolbelt` conserva hasta 1024 `ConversationState` mediante una clave de conversación. El
  estado contiene ubicación, pregunta pendiente, candidatos, cantidad pendiente, carrito y marca
  de borrador finalizado.
- El primer mensaje comercial se aplaza hasta recibir ciudad o zona. Solo `norte`, `sur` y `centro`
  se asocian a las sedes sintéticas configuradas; para otras ubicaciones no se inventa cercanía.
- Una intención comercial nueva sustituye candidatos pendientes. Las respuestas ordinales o
  pronominales se aplican exclusivamente a las últimas opciones mostradas.
- Agregar un producto modifica el carrito, no el repositorio de cotizaciones. `create_quote_draft`
  se ejecuta una vez al finalizar con todas las líneas acumuladas.
- La continuidad es automática hasta 24 horas, requiere elección entre 24 horas y 3 días, y abre un
  carrito nuevo después de 3 días. Un borrador finalizado siempre requiere elegir entre reutilizar
  o comenzar de nuevo.
- La implementación actual es volátil. Reiniciar el proceso elimina las sesiones y los carritos;
  PostgreSQL sigue siendo el destino de persistencia definido para un corte posterior.

### 2.2. Datos sintéticos ampliados

- `synthetic_seed.py` genera determinísticamente 2000 productos ficticios en categorías comunes de
  ferretería y agroferretería. Incluye unidad comercial, precio, alias, atributos y contexto, todos
  marcados con procedencia sintética.
- La búsqueda filtra por unidad comercial explícita, normaliza plurales y acentos, limita la salida
  a tres candidatos y prioriza las referencias curadas sobre variaciones generadas.
- Los snapshots sintéticos permiten ejercitar disponibilidad por las sedes de demostración. No son
  datos de una empresa real y no deben migrarse como catálogo productivo.

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
| T09 | Candidato descriptivo exige elegir por nombre u opcion antes de consultar stock o crear un DRAFT | `HermesToolbelt.prepare_customer_turn`, `/v1/chat`, webhook WhatsApp |
| T11 | Tema general se bloquea antes del LLM y no entrega enlaces externos | `CommercialScopePolicy`, `CustomerResponsePolicy` |
| T19 | Perfil mock: cero llamadas a Groq | `/health`, `/v1/chat`, `/v1/channels/whatsapp/webhook` y suite con `LLM_PROVIDER=mock` |

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
- Registro auditable de productos ferreteros ausentes y notificacion a un trabajador. Hasta que se
  implemente el puerto correspondiente, el chat no promete que aviso a un encargado.
- Persistencia durable de `ConversationState`, historial de carritos y continuidad tras reinicios.
- Directorio geográfico de sedes para seleccionar realmente la más cercana a una ciudad o zona.
- Relaciones verificadas entre productos para recomendaciones pertinentes sin inventar
  compatibilidad.
- Entrada por fotografías y reglas especializadas para calcular cantidades de obra.
- Flujo copiloto para el trabajador (post-MVP): notificacion por Gmail (`WorkerNotificationPort` / SMTP) con tabla de pre-facturacion, hoja de alistamiento multi-sede, semaforo de descuentos del harness y confirmacion humana antes de facturar (`PENDING_APPROVAL` -> `APPROVED_FOR_BILLING`) con aviso de regreso al WhatsApp del cliente.

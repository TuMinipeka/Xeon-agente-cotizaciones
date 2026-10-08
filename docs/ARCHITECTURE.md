# Arquitectura base de XEON

## Estado implementado

Hay dos cortes conectados por un composition root, no por el LLM.

```text
POST /v1/chat
      |
      v
 AgentService ---- system prompt acotado
      |
      v
   LLMPort
    /   \
 Mock   OpenAI-compatible -> Grok 4.6

POST /v1/quotes  GET /v1/quotes/{id}
      |
      v
 AppContainer (composition root)
      |
      +--> CreateQuoteDraft / GetQuoteDraft
      +--> ProductCatalog (memoria, SKU/alias exacto)
      +--> QuoteDraftRepository (memoria, clave tenant_id+request_id)
      |
      v
 domain: Product, Money, QuoteLine, Quote(status=DRAFT, version=1)
```

`MockLLM` es el perfil predeterminado y garantiza cero llamadas externas. El perfil `grok`
exige una credencial explicita. Los errores del proveedor se normalizan sin copiar el cuerpo
remoto ni la clave a la respuesta. Compose publica la API solo en `127.0.0.1:8000`.

El cotizador calcula con `Decimal` y catálogo sintético de Ferretería Demo XEON. Un reintento
con la misma clave `tenant_id` + `request_id` devuelve el mismo borrador. `/v1/chat` no crea
cotizaciones ni calcula precios.

## Trazabilidad del corte

| Caso | Resultado esperado | Donde se cubre |
|---|---|---|
| T01 | SKU y cantidad validos crean un DRAFT exacto, version 1 | `CreateQuoteDraft`, `POST/GET /v1/quotes`, CLI `quotes create/show` |
| T02 | «El coso del aire» exige aclaracion; no inventa SKU | `ClarificationRequired.ambiguous_reference` |
| T03 | Medidas sin unidades exigen aclaracion | `ClarificationRequired.missing_units` |
| T06 | Catalogo caido no se reporta como agotado | `CatalogUnavailable` |
| T08 | Descuento pedido sin politica: no se inventa porcentaje | `DiscountPolicyUnavailable` |
| T19 | Perfil mock: cero llamadas a Grok | `/health`, `/v1/chat` y suite con `LLM_PROVIDER=mock` |

## Fronteras que no deben romperse

- El agente interpreta; el dominio y la aplicacion deciden precios, descuentos, impuestos,
  inventario y estados.
- La API transforma HTTP y delega. No contiene reglas comerciales.
- Los adaptadores conocen protocolos externos; el puerto no conoce HTTPX.
- La identidad de una conversacion no implica identidad comercial ni permiso de vendedor.
- Desconocido o fuente caida no significan agotado.
- El agente de codigo de Kilo y el agente comercial XEON son procesos distintos.

## Pendiente (no implementado)

- PostgreSQL/Alembic, LangGraph, Telegram, Celery/RabbitMQ, PDF, aprobacion humana.
- Politica de descuentos versionada; T08 solo declara `DiscountPolicyUnavailable`.
- Herramientas tipadas del agente sobre busqueda y borrador.
- Reorganizacion feature-first: se pospone; exige un ADR que compare capas globales vs
  hexagono interno por modulo.

# Arquitectura base de XEON

## Estado implementado

El corte actual prueba la frontera minima `HTTP -> AgentService -> LLMPort -> proveedor`. Incluye
un proveedor determinista y un adaptador OpenAI-compatible para el endpoint Reto/Grok. La API no
calcula ni persiste cotizaciones y lo declara en sus respuestas y documentacion.

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
```

`MockLLM` es el perfil predeterminado y garantiza cero llamadas externas. El perfil `grok` exige
una credencial explicita. Los errores del proveedor se normalizan sin copiar el cuerpo remoto ni
la clave a la respuesta.

## Fronteras que no deben romperse

- El agente interpreta; el dominio y la aplicacion decidiran precios, descuentos, impuestos,
  inventario y estados.
- La API transforma HTTP y delega. No contiene reglas comerciales.
- Los adaptadores conocen protocolos externos; el puerto no conoce HTTPX.
- La identidad de una conversacion no implica identidad comercial ni permiso de vendedor.
- El agente de codigo de Kilo y el agente comercial XEON son procesos y responsabilidades
  diferentes.

## Siguiente corte tecnico

Implementar un cotizador determinista con `Decimal`, catálogo sintético y estados de borrador.
Solo despues conectar esas operaciones como herramientas del agente. PostgreSQL/Alembic,
LangGraph, Telegram, Celery/RabbitMQ y PDF se incorporan cuando exista el caso de uso que los
necesite y una prueba que demuestre su comportamiento.


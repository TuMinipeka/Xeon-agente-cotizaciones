---
tags:
  - xeon/producto
---

# Propuestas para escalar XEON

Lluvia de ideas generada por Claude en la conversación del 2026-10-24, a pedido del usuario, a partir de `XeonContexto.md`, `docs/ARCHITECTURE.md` y `CONTRIBUTING.md`. **Todas las ideas tienen estado `propuesta`.** Ninguna está aprobada ni implementada. Relacionado: [estado del corte](estado-del-corte.md), [hito S2](hito-s2.md), [decisiones pendientes](decisiones-pendientes.md).

Revisado: 2026-10-24.

## Base implementada (referencia)

- Chat por WhatsApp con Kapso (API oficial).
- Búsqueda léxica en memoria.
- Borrador `DRAFT` con `Decimal` e idempotencia en memoria.
- CLI Typer.
- Perfil `mock`.

El detalle está en [estado del corte](estado-del-corte.md).

## Propuestas

| Eje | Idea | Valor | Dependencia | Riesgo |
|---|---|---|---|---|
| Datos | PostgreSQL 17 con Alembic (SQL, JSONB y pgvector) | Crítico: pasar de memoria a producción | Docker, migraciones, pruebas transaccionales | Migrar los datos sintéticos; versionado del esquema |
| Datos | Índices GIN en `products.specs` | Búsqueda por atributos | PostgreSQL | Sobreindexar hace más lentas las escrituras |
| Datos | Políticas de descuento versionadas y ligadas a la cotización | Auditoría | Persistencia | Una regla que vence después de cotizar |
| Datos | Deduplicación por `external_message_id` | Idempotencia del webhook | Persistencia | Borradores duplicados (ver [hito S2](hito-s2.md)) |
| Datos | Backups y recuperación a un punto en el tiempo | Resiliencia | Almacenamiento externo | Costo |
| Producto | Aprobación humana, PDF con WeasyPrint y entrega por WhatsApp | Cierra el flujo del MVP | Persistencia y versionado | Una aprobación ligada a la versión incorrecta |
| Producto | Copiloto con Gmail y prefacturación | Menos trabajo para el vendedor | Aprobación, SMTP y puerto de notificación | Desincronización entre versión y aprobación |
| Producto | Audio y visión en WhatsApp | Mejor experiencia | Proveedor de transcripción o visión | Costo y falsos positivos |
| Producto | Reserva real en el ERP y conversión a pedido | Cierre de la venta | Integración con el ERP | Sobreventa; una cotización no es una reserva |
| Producto | Historial por cliente y complementarios | Retención y venta adicional | Identidad comercial | Privacidad; recomendaciones no aprobadas |
| Arquitectura | Eventos de auditoría de la cotización | Trazabilidad | Persistencia | Complejidad |
| Arquitectura | Colas (Redis con RQ o Celery) | Concurrencia para S4 | Redis | Estado distribuido; exige idempotencia |
| Arquitectura | Caché del catálogo | Latencia | Redis e invalidación | Precio desactualizado si la invalidación falla |
| Arquitectura | Multi-tenant estricto | SaaS | `tenant_id` en todos los repositorios | Fuga de datos entre inquilinos |
| Seguridad | RBAC con OAuth2 o JWT para vendedor y supervisor | Varios usuarios | Persistencia | Bloqueo por token vencido |
| Seguridad | Defensas contra inyección de prompt | Proteger descuentos y estados | Pruebas de agy | El modelo sigue texto malicioso |
| Seguridad | Límite de peticiones por tenant | Anti-spam y costo | Redis | Bloquear picos legítimos |
| Seguridad | Registro de auditoría | Cumplimiento | Persistencia | Volumen de datos |
| Operación | Logs estructurados y métricas (Prometheus) | Observabilidad | Exportador | Sobrecarga |
| Operación | Telemetría de costo por tarea (tokens) | Requisito de S3 | Adaptador LLM | Variación de los tokens |
| Operación | Plan de recuperación ante desastres | Resiliencia | Backups | Costo |
| Canales | Integración con ERP (Odoo, SAP) | Venta real | API del ERP | Un adaptador por cada ERP |
| Canales | Telegram, SMS o panel B2B | Alcance | Nuevo adaptador por puerto | Estado fragmentado; costo del SMS |
| Métricas | Conversión de cotización a venta, P95 de `/v1/chat`, tasa de aclaraciones, recall@K, costo por cotización y entregas fallidas en Kapso (`observe-whatsapp`) | Gestión del negocio y SLA | Persistencia y telemetría | Métricas mal interpretadas; recall@K necesita un conjunto etiquetado |

## Orden sugerido (propuesta)

1. PostgreSQL y deduplicación.
2. Aprobación, PDF y descuentos versionados.
3. RBAC y auditoría.
4. Telemetría de costo (S3).
5. Colas y carga (S4).
6. Canales adicionales.

## Correcciones respecto a la respuesta original

- Se retiró la afirmación de que GitHub Actions existía "parcialmente": no se verificó.
- Se retiraron las ideas de Slack y MCP: no tenían respaldo en las fuentes.

Grafo: [capa docs](../graph/hub-docs.md) · [mapa del proyecto](../graph/mapa-proyecto.md)

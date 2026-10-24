# Estado del corte

Revisado: 2026-10-24. La fuente funcional mezcla MVP deseado y componentes existentes. Esta página contrasta la visión con el [README](../../README.md), la [arquitectura](../../docs/ARCHITECTURE.md) y el código.

| Capacidad | Estado observado | Evidencia |
|---|---|---|
| API FastAPI y CLI Typer | Implementado para pruebas locales | [API](../../src/xeon/api/app.py), [CLI](../../src/xeon/cli.py) |
| Catálogo y stock sintéticos | Implementado en memoria | [Contenedor](../../src/xeon/application/container.py), [catálogo](../../src/xeon/adapters/catalog/memory.py), [inventario](../../src/xeon/adapters/inventory/memory.py) |
| Búsqueda de candidatos | SKU/alias exactos y puntuación léxica de nombre, especificaciones y descripción | [Catálogo](../../src/xeon/adapters/catalog/memory.py), líneas 143-178 |
| Cotizaciones | Borrador `DRAFT` con cálculo `Decimal` e idempotencia en memoria | [Dominio](../../src/xeon/domain/quote.py), [repositorio](../../src/xeon/adapters/persistence/memory.py) |
| IA | Perfil `mock` predeterminado y adaptadores compatibles con Groq/Hermes; una llamada real requiere configuración | [Configuración](../../src/xeon/config.py), [contenedor](../../src/xeon/application/container.py) |
| Proveedor Grok (xAI) | Adaptador implementado (2026-10-24) con pruebas sin red; ninguna llamada real todavía | [config](../../src/xeon/config.py), [factory](../../src/xeon/adapters/llm/factory.py); ver D3 en [decisiones](decisiones-pendientes.md) |
| Pruebas multi-turno y casos límite | 93 aprobadas y 3 `xfail` que documentan defectos QA1 a QA3 | [pruebas](../../tests/test_multiturn_context.py); [hito S2](hito-s2.md) |
| WhatsApp | Webhook y envío opcional por Evolution API; la aceptación del proveedor no demuestra entrega al teléfono | [API](../../src/xeon/api/app.py), líneas 163-229; [adaptador](../../src/xeon/adapters/channels/evolution.py), línea 167 |
| PostgreSQL comercial, JSONB y pgvector | Planificado; no es la persistencia del prototipo | [Arquitectura, pendientes](../../docs/ARCHITECTURE.md), líneas 101-105; [README](../../README.md), líneas 42-46 |
| Aprobación humana, PDF y descuentos versionados | Planificado | [Arquitectura, pendientes](../../docs/ARCHITECTURE.md), líneas 101-105 |
| Copiloto por Gmail y prefacturación | Posterior al MVP | [Documento funcional](../../XeonContexto.md), líneas 62-69 |

**Límite de verificación:** inspección estática de archivos; esta entrada no demuestra ejecución con Groq, Hermes, WhatsApp real o una base comercial. La arquitectura proyectada se discute en [decisiones pendientes](decisiones-pendientes.md).

# Nota de entrega — XEON

**Fecha de corte:** 17 de octubre de 2026  
**Equipo:** Daniel Mayorga y Juan Pablo Conde Zapata  
**Rama revisada:** `developer/daniel` (`8f295a2`)  
**Estado:** prototipo funcional con datos sintéticos y conversación por WhatsApp en entorno de prueba.

## Qué se logró

XEON recibe una consulta comercial por API o por un webhook de Evolution API, prepara contexto de productos y disponibilidad, y responde por el mismo canal cuando el envío está habilitado. El equipo ya ha enviado mensajes por WhatsApp; en este corte, la evidencia automatizada verifica la recepción, el procesamiento, la solicitud de envío a Evolution API y la deduplicación. La entrega al teléfono depende de la sesión vinculada y se constató por la prueba del equipo, no por Pytest.

| Entregable | Resultado verificable |
|---|---|
| Núcleo comercial | Catálogo sintético por SKU y alias, búsqueda léxica en nombre, atributos y descripción; stock sintético por sede con origen, vigencia y faltante. |
| Cotización | Creación y consulta de borradores `DRAFT` versión 1; importes con `Decimal`, rechazo de descuentos sin política e idempotencia por `tenant_id` y `request_id` durante la vida del proceso. |
| Conversación e IA | `AgentService` prepara contexto comercial con `HermesToolbelt` propio; perfiles `mock`, puente HTTP hacia Hermes local y adaptador OpenAI compatible para Groq. |
| WhatsApp | Webhook `messages.upsert`, filtro de grupos y estados, prefijo opcional `/xeon` o `#xeon`, soporte de identificadores `@lid`, deduplicación local y envío de texto por Evolution API. |
| Operación y demostración | API FastAPI, CLI Typer, Docker Compose para el canal y sus servicios, pruebas automatizadas, README de instalación y video de demostración. |

## Qué falló o sigue limitado

- El canal requirió ajustes de imagen, QR, versión de teléfono, caché de mensajes y direccionamiento `@lid`; el historial de commits registra esas correcciones. En esta revisión Docker Desktop no estaba disponible, por lo que no se repitió una prueba en vivo.
- El catálogo, inventario, borradores y deduplicación de XEON están en memoria. Reiniciar el proceso pierde esos datos. PostgreSQL y Redis del Compose sirven a la sesión de Evolution API; todavía no persisten los datos comerciales de XEON.
- La búsqueda descriptiva es léxica; no existen embeddings, consulta `JSONB` ni `pgvector` operativos. El chat puede tomar el primer candidato descriptivo antes de que el comprador confirme el SKU.
- No hay autenticación del webhook ni del comprador, aprobación humana, PDF, integración ERP, inventario real, facturación ni confirmación automática de entrega al teléfono. `ACCEPTED_BY_PROVIDER` solo confirma que Evolution API aceptó la solicitud.
- El puente a Hermes y Groq existe, pero la suite no acredita una conversación real con esos servicios. No hay telemetría de tokens, tiempos ni facturación por tarea.

## Costo por tarea

Los importes siguientes corresponden solo a **consumo externo comprobable en la validación de este corte**. No hay registro de horas de trabajo, facturas de infraestructura ni uso facturado de Groq, Hermes o herramientas de producción; por ello no se calcula un costo total del proyecto.

| Tarea | Consumo externo verificable | Costo que falta medir |
|---|---|---|
| Desarrollo del dominio, catálogo, stock y cotizador | Pruebas locales con datos sintéticos y `mock`: **$0 en llamadas a modelos externos**. | Horas de desarrollo y equipo. |
| API, CLI y pruebas | Ejecución local: **$0 en llamadas a modelos externos**. | Horas de desarrollo y equipo. |
| Conversación con Groq o Hermes | No se hizo una llamada real durante esta revisión. | Tokens, cuota o tarifa del proveedor y costo de alojar Hermes. |
| Mensajería por Evolution API | La suite usa un transporte HTTP simulado; no genera un cargo de proveedor medido. | Equipo, energía, alojamiento, red y cualquier cargo del canal o proveedor aplicable al despliegue real. |
| Video de demostración | Artefacto presente en el repositorio; no se ejecutó su generación en esta revisión. | Costo de voz, producción y horas de edición; no hay contabilidad por tarea. |

**Resultado económico del corte:** se puede afirmar **$0 de consumo externo de IA en la suite `mock`**. El costo real por mensaje, consulta o cotización y el costo total del proyecto quedan **sin medir**. Para calcularlos se necesita registrar uso por solicitud y conciliarlo con facturas y horas, sin guardar credenciales ni mensajes sensibles.

## Evidencia de aceptación

- `uv run ruff check .`: sin hallazgos.
- `uv run ruff format --check .`: 66 archivos conformes.
- `uv run mypy src`: sin errores en 39 archivos fuente.
- `uv run pytest -ra`: **80 pruebas aprobadas**.
- `docker compose -f compose.yaml -f compose.evolution.yaml --profile core ps`: no ejecutable en esta revisión porque Docker Desktop no estaba disponible.

## Decisión documental y siguiente paso

`XeonContexto.md` y partes de `docs/ARCHITECTURE.md` describen como actuales PostgreSQL comercial, RAG vectorial, aprobación y PDF. El código y el README los sitúan como pendientes. Para este entregable se adopta **el código probado como estado implementado** y el documento funcional como visión del producto. El equipo debe decidir y actualizar ambos documentos para marcar de forma uniforme qué está implementado y qué pertenece a la siguiente fase.

El siguiente corte debería persistir los datos comerciales y la deduplicación, exigir confirmación de SKU ambiguos, asegurar el webhook y ejecutar una prueba de extremo a extremo con un teléfono de prueba. Después corresponde incorporar aprobación humana y PDF con sus pruebas y medición de costos.

---
tags:
  - xeon/decision
---

# Propuesta de la fase 3 (para decisión del usuario)

Fecha: 2026-10-26. Autor: Sonnet (investigación y diseño; no se escribió código ni se añadieron dependencias). Estado: **`propuesta`**, sin aprobar. Origen: pedido del orquestador y el borrador de la fase 3 del plan (índice híbrido, base de conocimiento, adaptadores REST, persistencia del carrito y la memoria). Relacionado: [D12 y D13](decisiones-pendientes.md), [conector de la ferretería](conector-ferreteria.md), [embudo de cotización](embudo-cotizacion.md), [estado del corte](estado-del-corte.md), [propuestas de escalado](propuestas-escalado.md).

Las versiones salen de PyPI y de los README consultados el 2026-10-26; los precios de embeddings son de agregadores, no de hojas oficiales. Lo que no pude verificar en la documentación oficial está marcado **por verificar**.

## Límites actuales que motivan la fase

- Estado del embudo, carrito, memoria, borradores y deduplicación de webhooks viven en el proceso: un reinicio los pierde y la idempotencia entre workers no está garantizada.
- Búsqueda lexical sobre el catálogo (sintético o SQL); sin RAG.
- Políticas demo (`demo: true`); el asesor solo recibe una línea de log (`LoggingAdvisorNotifier`).
- Kapso `interactive` sin verificar en sandbox. Sin adaptadores REST ni CSV.
- El adaptador del LLM no lee el campo de uso de tokens de la respuesta (no hay coincidencias de `usage` en `src/xeon/adapters/llm/`).

## Opciones priorizadas

### A. Persistencia del estado operativo en un PostgreSQL propio de XEON

- **Problema:** perder embudo, carrito y borradores en cada reinicio; doble respuesta si dos workers reciben el mismo `message.id`.
- **Diseño hexagonal:**
  - Puertos que ya existen: `CartRepository`, `QuoteDraftRepository`, `ConversationMemory`. Se añaden `FunnelStateStore` (estado por conversación), `ProcessedEventStore` (deduplicación por `message.id` con `INSERT … ON CONFLICT DO NOTHING`) y `AdvisorOutbox` (ver B).
  - Adaptadores nuevos en `adapters/persistence/postgres/` con SQLAlchemy Core + psycopg 3, ambos ya en el repositorio (`db`, `db-test`). Los adaptadores en memoria siguen para pruebas.
  - Base **separada** de la de la ferretería: URL propia en `secrets/` (por ejemplo `XEON_STATE_URL_FILE`), con lectura y escritura. El conector D13 (`SQL_URL_FILE`, solo lectura) no cambia.
  - Estado serializado en `JSONB` con columna `version` (bloqueo optimista) o `SELECT … FOR UPDATE` por clave de conversación; limpieza por TTL.
  - Migraciones con Alembic.
- **Tecnología:** PostgreSQL 17 (ya validado con `postgres:17.6` en `compose.db-test.yaml`); Alembic **1.20.1** ([PyPI](https://pypi.org/project/alembic/)); SQLAlchemy 2.x y psycopg 3 ya fijados. Alternativa para estado efímero: Redis con `redis-py` **8.1.0** ([PyPI](https://pypi.org/project/redis/)), con TTL por clave. No la recomiendo como primera opción: los borradores y la idempotencia necesitan durabilidad, así que Redis añadiría un segundo servicio sin quitar el PostgreSQL.
- **Esfuerzo:** M.
- **Riesgos:** migrar el estado serializado cuando cambie el embudo (versionar el esquema del JSON); datos personales (teléfono, dirección de domicilio) pasan a disco: cifrado en reposo y retención; un segundo secreto que operar.
- **Criterio de aceptación:**
  - Prueba de integración: reiniciar el proceso a mitad del embudo conserva paso, opciones pendientes y carrito.
  - Dos workers con el mismo `message.id` producen una sola respuesta y un solo borrador.
  - `alembic upgrade head` y `downgrade base` pasan contra `postgres:17.x` en el compose de pruebas.
  - Los adaptadores en memoria y PostgreSQL pasan la misma suite de contrato.

### B. Notificación real al asesor, aprobación humana y PDF

- **Estado (2026-10-26): implementado parcialmente** (Sonnet, `cedb9d9` y `9b38e86`, merge `f2097ae`; ver [panel del asesor](../../docs/PANEL_ASESOR.md)). Hecho: panel web `/panel` autenticado, revisión humana `APPROVED_FOR_BILLING` / `RECHAZADO_POR_ASESOR` y aviso al cliente por Kapso con plantilla. Pendiente: PDF, roles, persistencia de la bandeja y las sesiones, y verificar el aviso en el sandbox de Kapso.

- **Problema:** hoy `CONFIRMADO_POR_CLIENTE` solo escribe un log; nadie se entera. Faltan los estados humanos `PENDING_APPROVAL → APPROVED_FOR_BILLING` y un documento para el cliente.
- **Diseño hexagonal:**
  - El puerto `AdvisorNotifier` ya existe. Adaptadores candidatos, por orden:
    1. **WhatsApp al asesor por Kapso:** reutiliza el canal ya integrado ([envío de mensajes](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons)). Restricción de WhatsApp: fuera de la ventana de 24 h solo se envían plantillas aprobadas (**por verificar** en Kapso con el número real).
    2. **Gmail:** [Gmail API](https://developers.google.com/gmail/api) con OAuth o SMTP; encaja con el copiloto del documento funcional. Más fricción de credenciales.
    3. **Panel web mínimo** (FastAPI + plantillas): una lista de confirmaciones y los botones aprobar o rechazar. Exige autenticar a los asesores (la identidad de WhatsApp no es identidad comercial).
  - Un `AdvisorOutbox` en el PostgreSQL de A entrega cada aviso al menos una vez, con reintentos; el envío ocurre fuera del turno del cliente.
  - Aprobación: nuevo caso de uso `ApproveQuoteDraft` expuesto solo en un endpoint autenticado para humanos; el modelo y el embudo no pueden invocarlo. Tabla de transiciones explícita en el dominio.
  - PDF: plantilla HTML + WeasyPrint **70.0** ([PyPI](https://pypi.org/project/weasyprint/), requiere bibliotecas Pango del sistema, a incluir en el `Dockerfile`). Alternativa sin dependencias del sistema: ReportLab. El PDF se genera del borrador versionado, nunca de texto del modelo.
- **Esfuerzo:** M (notificación y aprobación) + S (PDF). Depende de A para el outbox.
- **Riesgos:** ventana de 24 h y plantillas de WhatsApp; la aprobación humana toca la regla central de AGENTS.md (ningún modelo aprueba), así que debe tener pruebas de que no hay camino desde el LLM; quién factura sigue fuera de alcance.
- **Criterio de aceptación:**
  - Al confirmar, el asesor recibe exactamente un aviso (también tras reinicio o reintento) con id, resumen y total, sin datos innecesarios del cliente.
  - Solo un usuario autenticado puede pasar un borrador a `APPROVED_FOR_BILLING`; prueba que el embudo y el LLM no pueden.
  - El total del PDF coincide con el del borrador al centavo y es reproducible.
  - Aviso verificado de extremo a extremo en el sandbox de Kapso.

### C. Búsqueda híbrida del catálogo (D12)

- **Problema:** la búsqueda léxica no resuelve lenguaje coloquial («el coso del aire», jerga regional) y deja la lista de candidatos al azar del texto.
- **Diseño hexagonal:**
  - Puerto nuevo `CandidateIndex` (`search(query, limit) -> SKUs con puntuación`). `ProductCatalog` conserva la consulta exacta y el **precio**; el índice solo propone SKUs y luego `find_exact` lee precio y stock del conector. Así el RAG nunca decide precios ni existencias.
  - Adaptador PostgreSQL: tabla `catalog_index(tenant_id, sku, texto, tsv tsvector, embedding halfvec(N), origen_actualizado_en)`, con `tsvector` de configuración `spanish` y fusión RRF en SQL.
  - Sincronización incremental desde el conector. Dos caminos: **dlt** **1.31.0** con cursor `updated_at` y `merge` ([PyPI](https://pypi.org/project/dlt/), [cursor](https://dlthub.com/docs/general-usage/incremental/cursor)) o una tarea propia con SQLAlchemy (una dependencia menos). Requiere que la ferretería exponga una columna de modificación; se añadiría una consulta opcional `catalog_export` al YAML, sin tocar las cuatro actuales.
  - Solo se indexa texto descriptivo; nunca precios, stock ni datos de clientes.
- **Tecnología:** pgvector **0.8.7** ([README](https://github.com/pgvector/pgvector)): PostgreSQL 13+, imágenes Docker `pg13`…`pg18`, HNSW sobre `vector` (≤2.000 dimensiones) y `halfvec` (≤4.000), búsqueda híbrida con `tsvector` fusionada por RRF; filtrar después de un índice aproximado puede devolver menos filas (usar `hnsw.iterative_scan` o índices parciales por inquilino). Cliente Python `pgvector` **0.5.1** ([PyPI](https://pypi.org/project/pgvector/)). Embeddings:
  - **BAAI/bge-m3**: multilingüe (100+ idiomas), licencia MIT, 1.024 dimensiones; unos USD 0,01 por millón de tokens alojado ([OpenRouter](https://openrouter.ai/models/baai/bge-m3)) o autoalojado.
  - **text-embedding-3-small** de OpenAI: unos USD 0,02 por millón de tokens y 1.536 dimensiones (cifra de un [blog](https://www.resumelens.org/blog/ai/embedding-models-comparison), no de OpenAI); ese blog advierte que rinde peor fuera del inglés.
  - Costo orientativo: 20.000 productos × ~60 tokens ≈ 1,2 millones de tokens, del orden de USD 0,01 a 0,03 la carga completa; las consultas son despreciables. El costo real es el egreso de descripciones a un proveedor externo, que requiere autorización del usuario.
- **Esfuerzo:** L.
- **Riesgos:** el catálogo actual es sintético, así que la calidad real no se puede medir sin un catálogo verdadero; calidad en español regional sin benchmark propio (no encontré uno específico); dependencia de una columna `updated_at` en el ERP; el reranking opcional añade latencia.
- **Criterio de aceptación:**
  - Conjunto de unos 50 pedidos coloquiales en español con SKU esperado: recall@5 del híbrido mayor que el de la búsqueda léxica actual, medido con un script reproducible.
  - Prueba de que el índice no contiene precios ni stock y de que el precio mostrado viene siempre del conector.
  - La sincronización repetida es idempotente y recoge solo cambios.

### D. Adaptadores REST para ERP colombianos (Siigo, Alegra)

- **Problema:** muchas ferreterías no exponen SQL; sus datos viven en un ERP en la nube. `DATA_SOURCE=rest` hoy falla de forma explícita.
- **Qué se verificó** (la documentación oficial no se pudo leer completa; **todo lo siguiente está por verificar con una cuenta de prueba**):
  - **Alegra:** el portal [developer.alegra.com](https://developer.alegra.com/) documenta `GET /items` (listar, crear, editar), `/warehouses` y ajustes y traslados de inventario; una herramienta MCP de Alegra describe stock de un ítem con desglose opcional por bodega. No pude confirmar el esquema de autenticación ni el endpoint exacto de existencias.
  - **Siigo:** [siigo.com/blog/siigo-api](https://www.siigo.com/blog/siigo-api/) indica que la API se habilita en Siigo Nube con ciertos planes (profesional, independiente, emprendedor o premium) y que el token dura 24 h. Un cliente comunitario ([siigo-python](https://pypi.org/project/siigo-python)) autentica con usuario y `access_key` para obtener un token, lista productos con filtros (`code`, `updated_start`, `page_size` máximo 100) y un servidor MCP usa `GET /v1/warehouses`. La referencia oficial está en Apiary ([siigoapi.docs.apiary.io](https://siigoapi.docs.apiary.io/)), que no pude leer; no hallé un endpoint de existencias por bodega.
- **Diseño hexagonal:** adaptadores `RestProductCatalog`, `RestBranchInventory` y `RestBranchDirectory` con HTTPX detrás de los mismos tres puertos de D13, descritos por un `connectors/<tenant>.rest.yaml` (rutas, paginación, mapeo de campos, divisor de precio), con la misma validación estricta: solo `GET`, precio en `Decimal`, secretos en `secrets/`. Un cliente de token con renovación anticipada. El dominio y el embudo no cambian.
- **Esfuerzo:** M por ERP una vez haya acceso; S de diseño si se limita a catálogo y sedes.
- **Riesgos:** sin credenciales de prueba no se puede avanzar; límites de tasa desconocidos; si el ERP no entrega stock por sede, el embudo seguiría con stock pendiente de un asesor (falla segura); cumplimiento de datos del cliente en la nube.
- **Criterio de aceptación:**
  - Pruebas de contrato con respuestas grabadas (`httpx.MockTransport`) para catálogo, sedes y stock, incluidos token vencido y paginación.
  - Una corrida de solo lectura contra una cuenta sandbox del ERP, documentada con fecha.
  - El mismo caso «2 bultos de cemento» cotiza con precios del ERP; sin ningún método de escritura expuesto.

### E. Observabilidad y costo por tarea

Estado: **`implementado`** (commits `ef69e8b` y `aeaa971`, merge `76e2458`; autor: Sonnet; ver [docs/OBSERVABILIDAD.md](../../docs/OBSERVABILIDAD.md)):

- **Uso de tokens:** `LLMResponse.usage` (`TokenUsage`) lee el `usage` real del proveedor OpenAI-compatible; si falta o es inválido queda como desconocido sin estimar; `MockLLM` informa 0.
- **Métricas sin PII:** puerto `MetricsRecorder` (`src/xeon/application/ports/metrics.py`) con adaptadores `NullMetrics`, `InMemoryMetrics` y `JsonlMetrics` (vía `METRICS_PATH`), sin registrar teléfono, texto ni clave de conversación.
- **Etapas cronometradas:** cubre `turno`, `llm`, `ejecutor`, `catalogo`, `inventario` y `envio_kapso` mediante `MeteredLLM` y wrappers de métricas en `build_container`.
- **Costo y reportes:** tarifa por millón en `Settings` (`LLM_PRICE_*`) marcada como supuesto al no estar documentada la unidad de la pasarela; `scripts/cost_report.py` agrega por tarea y el runner de evals guarda `observability.jsonl` y métricas en cada caso.

- **Problema:** no se mide cuánto cuesta ni cuánto tarda una cotización; el adaptador del LLM descarta el uso de tokens.
- **Diseño hexagonal:** puerto `UsageRecorder` invocado por un decorador de `LLMPort` (tokens de entrada y salida del campo de uso de la respuesta, modelo, latencia) y por el embudo (latencia por paso). Adaptadores: logs JSON estructurados (por defecto), tabla `usage_events` en el PostgreSQL de A y, opcional, trazas OpenTelemetry. Un comando `xeon usage` resume costo por conversación con precios por modelo en configuración. La clave de conversación se guarda con hash; sin texto de clientes.
- **Tecnología:** `opentelemetry-sdk` **1.45.1** ([PyPI](https://pypi.org/project/opentelemetry-sdk/)). Las convenciones semánticas `gen_ai.*` siguen en estado *Development* ([resumen de julio de 2026](https://dev.to/azena-ai/opentelemetrys-genai-semantic-conventions-are-not-stable-yet-heres-what-actually-shipped-in-2026-3mke)), así que conviene empezar con logs y tabla propia y dejar OpenTelemetry opcional.
- **Esfuerzo:** S (logs y tabla) a M (con trazas).
- **Riesgos:** que la pasarela del reto no devuelva el campo de uso (**por verificar**); privacidad de los logs.
- **Criterio de aceptación:**
  - Cada llamada al LLM deja un registro con tokens, modelo y latencia, y cada paso del embudo registra su duración.
  - Un informe imprime el costo por conversación a partir de una corrida simulada; prueba de que no aparece texto del cliente.

## Recomendación de orden

1. **A (persistencia)**: es la deuda que bloquea todo lo demás y la única que cambia si XEON sobrevive a un reinicio o a más de un worker; B y E reutilizan su base de datos.
2. **E (observabilidad), en paralelo y pequeña**: sin medir tokens y latencia no se puede decidir C ni dimensionar costos.
3. **B (asesor, aprobación y PDF)**: convierte el borrador confirmado en una venta atendida; requiere A. Empezar por WhatsApp al asesor vía Kapso, y verificar el payload `interactive` en el sandbox al mismo tiempo.
4. **D (REST)** cuando el usuario consiga acceso de prueba a Siigo o Alegra; sin él, solo diseño.
5. **C (híbrida)** al final: es la más grande y necesita un catálogo real para medir mejora; hasta entonces la búsqueda léxica con el embudo guiado cumple.

## Preguntas para el usuario

1. ¿Autoriza un PostgreSQL propio de XEON (contenedor local en desarrollo; en producción, ¿dónde se alojaría y quién lo opera) para guardar embudo, carrito y borradores? ¿Cuánto tiempo se conservan los datos del cliente?
2. ¿Cómo prefiere que se entere el asesor: WhatsApp (Kapso), Gmail o un panel web? ¿Cuántos asesores hay y tienen número de WhatsApp de empresa?
3. ¿Tiene acceso a una cuenta de prueba de Siigo o Alegra, o a un catálogo real (aunque sea un CSV exportado) de alguna ferretería para medir la búsqueda híbrida?
4. ¿Autoriza enviar descripciones de catálogo (no precios ni datos de clientes) a un proveedor de embeddings, o prefiere un modelo autoalojado como bge-m3?
5. ¿Qué cambia más el MVP para el siguiente hito: que no se pierda nada al reiniciar (A), que el asesor reciba el pedido (B) o que el catálogo se entienda mejor (C)?

Grafo: [capa docs](../graph/hub-docs.md) · [mapa del proyecto](../graph/mapa-proyecto.md)

---
tags:
  - xeon/estado
---

# Hito S3: estado y entrega

Equivale al corte de la Semana 3 del proyecto. Consolida los tres temas directrices del hito: **datos reales, evaluación propia y costo por tarea**, junto con la persistencia operativa y el endurecimiento funcional. Relacionado: [hito S2](hito-s2.md), [base comercial](base-comercial.md), [evaluación conversacional](evaluacion-conversacional.md), [conector de la ferretería](conector-ferreteria.md), [embudo de cotización](embudo-cotizacion.md), [estado del corte](estado-del-corte.md) y [orquestación](orquestacion.md).

Revisado: 2026-10-31 (`QA/testing`).

---

## 1. Hoja de ruta y estado semanal

| Hito | Objetivo central | Estado | Evidencia y verificación |
|---|---|---|---|
| **S1** | Agente comercial funcionando de punta a punta | `implementado` | Commit `90ecbfe`; [estado del corte](estado-del-corte.md) |
| **S2** | 3 herramientas comerciales deterministas y demo en vivo | `implementado` | WhatsApp (Kapso) y shell `xeon`; [hito S2](hito-s2.md) |
| **S3** | **Datos reales, autoevaluación propia y costo por tarea** | `implementado` | PostgreSQL 18.6 + pgvector 0.8.7, 4.830 SKU reales, runner S01–S22 y `cost_report.py`; [docs entrega S3](../../docs/entrega_s3/README.md) |
| **S4** | Búsqueda vectorial ANN con embeddings y carga masiva | `planificado` | Hoja de ruta post-S3; [propuesta fase 3](propuesta-fase3.md) |

---

## 2. Los tres ejes centrales implementados en S3

### Eje 1: Datos reales (Ferretería El Campín)
- **Catálogo normalizado en 4FN:** Cinco migraciones Alembic independientes (`commercial_migrations/`) creando estructuras base, catálogo desacoplado en tablas puente N:M para marcas y colores (`NO_APLICA`), taxonomía de tres niveles (`lines`, `categories`, `sublines`), listas de precio versionadas con vigencias temporales (`valid_from`, `valid_until`) y tabla `stock` multisede.
- **Sanitización y semilla reproducible:** `scripts/build_commercial_seed.py` procesó 4.830 artículos comerciales reales purgando NITs, costos y márgenes. Generó `seeds/commercial/manifest.json` con huella SHA-256 e integridad verificada en `products.jsonl`.
- **Cimiento pgvector:** Instalación de `pgvector 0.8.7` sobre PostgreSQL 18.6 mediante `scripts/install_pgvector_windows.cmd`; columna `embedding` (`vector`) lista para recibir vectores sin dimensión fija prematura.
- **Cargador transaccional y conector:** `scripts/seed_commercial_db.py` con orden topológico inverso bajo restricciones FK `RESTRICT`, verificado con `scripts/verify_commercial_db.py`: 4.830 productos, 23.148 precios, 37.216 registros de stock y 19 incidencias de precio cero (`MISSING_PRICE`). Conector de solo lectura en `connectors/ferreteria-el-campin.yaml`.

### Eje 2: Evaluación propia (Arnés conversacional determinista)
- **Escenarios de diálogo S01–S22:** 22 árboles de conversación simulando compradores reales con arquetipos configurables (`SimulatedCustomerPersonas`), evaluando casos de ambigüedad ("el coso del aire"), medidas sin unidades, consultas fuera de dominio, pedidos multilínea e intentos de inyección.
- **Ejecutor dual:** Modo offline con `MockLLM` (costo $0, ejecución rápida para CI/CD con 66/66 PASS en 3 repeticiones) y modo live contra `grok-4.6` con tope de llamadas.
- **Oráculos inmutables:** Verificación de cálculos deterministas con `Decimal`, ausencia de alucinaciones de stock y prohibición estricta de compromisos contractuales anticipados (`no_completion_claims`).

### Eje 3: Costo por tarea (Telemetría y observabilidad)
- **Grabador de métricas:** Puerto `MetricsRecorder` y adaptador `JsonlMetrics` emitiendo trazas estructuradas a `observability.jsonl` sin almacenar datos personales (PII) de clientes.
- **Latencias por etapa y tokens reales:** Cronometra `turno`, `llm`, `ejecutor`, `catalogo`, `inventario` y `envio_kapso`. Extrae `prompt_tokens` y `completion_tokens` directamente de la respuesta del proveedor xAI / OpenAI-compatible.
- **Reporte analítico de costos:** Herramienta CLI `scripts/cost_report.py` para agregar métricas y calcular costo monetario estimado en USD por tarea y escenario.

---

## 3. Persistencia operativa y panel web (D15 A y B)

- **PostgreSQL operativo propio:** Migraciones Alembic `0001_operational_state.py` y `0002_advisor_inbox.py` para conservar el estado del embudo D14, el carrito versionado `QuoteCart`, deduplicación de webhooks y la bandeja del asesor. Bloqueo transaccional por conversación (`FOR UPDATE`).
- **Panel del asesor (`/panel`):** Interfaz web autenticada (PBKDF2, cookies `HttpOnly`/`SameSite`, CSRF y lockout) para revisión humana. Solo un humano puede aprobar (`APPROVED_FOR_BILLING`) o rechazar (`RECHAZADO_POR_ASESOR`) una cotización confirmada por el cliente.
- **Generación de PDF:** Descarga de cotización formal generada con ReportLab (`GET /panel/quotes/{id}/pdf`) con número `COT-XXXXXXXX` y leyenda legal.
- **Canal Kapso durable:** Migración `0003_kapso_outbox.py` implementando Transactional Outbox para tolerar desconexiones de WhatsApp y asegurar entrega idempotente.

---

## 4. Endurecimiento de QA y cambios de Conde (31 de octubre)

El 31 de octubre, Juan Pablo Conde implementó 33 commits en `QA/testing`:
1. `4d24f30`: Etiquetado como `TOTAL BORRADOR` en lugar de `TOTAL confirmado` en borradores no confirmados.
2. `c14cd7d`: Agregación de disponibilidad de stock para el 100% de las líneas del carrito multilínea.
3. `d2ad21b`: Preservación de nombres de calles y barrios en paso de dirección (evitando colisión con políticas).
4. `02b7790`: Refuerzo de `no_completion_claims` en el oráculo del arnés de evaluación.
5. `ebcd373`: Rollback atómico a `DRAFT` ante fallos de notificación al asesor en memoria.
6. `fb9749d`: Alineación de regresiones de pruebas históricas con `TOTAL BORRADOR`.
7. `550002c` a `1e50603`: Desarrollo completo, normalización 4FN, semilla sanitizada, cargador repetible, conector SQL y verificación física de la base comercial de Ferretería El Campín.

Detalle exhaustivo: [Cambios de Conde — 31 de octubre](../../docs/CONDE_IMPLEMENTADO_31_OCTUBRE.md).

---

## 5. Límites honestos del corte

- **Embeddings pendientes:** La columna `vector` existe en PostgreSQL, pero no contiene vectores ni índices aproximados (`HNSW`/`IVFFlat`) hasta seleccionar el modelo de embeddings en S4.
- **Stock de Bucaramanga:** Stock asignado para pruebas (100 en Bodega 1, 50 en Bodega 2) bloqueado en producción; pendiente sustituir por sincronización directa con el ERP.
- **Botones interactivos en teléfono físico:** Verificados mediante dobles y pruebas unitarias; pendiente prueba de campo con usuario final en smartphone real sobre el sandbox de Kapso.
- **Sesiones en memoria:** Las sesiones de `/panel` requieren afinidad en balanceadores si se despliegan múltiples workers.

Grafo: [capa docs](../graph/hub-docs.md) · [mapa del proyecto](../graph/mapa-proyecto.md)


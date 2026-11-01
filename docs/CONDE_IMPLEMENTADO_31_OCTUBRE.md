# Cambios de Juan Pablo Conde — 31 de Octubre de 2026

**Autor:** Juan Pablo Conde Zapata (`CondezPancake`)  
**Fecha:** 31 de octubre de 2026  
**Rama:** `QA/testing` (con base sincronizada de `developer/daniel`)  
**Total de commits implementados:** 33 commits  
**Enfoque de trabajo:** Endurecimiento funcional de QA, resolución de defectos en embudo, y desarrollo, normalización hasta 4FN, sanitización y despliegue físico de la base de datos comercial con datos reales de Ferretería El Campín.

---

## 1. Resumen de la Jornada del 31 de Octubre

El trabajo de Juan Pablo Conde en la rama `QA/testing` durante el 31 de octubre se dividió en dos grandes bloques de ingeniería:

1. **Endurecimiento de QA y corrección de defectos comerciales (Commits 1 al 8):**
   - Corrección del etiquetado prematuro de totales monetarios en borradores preliminares (`TOTAL BORRADOR` vs `TOTAL confirmado`).
   - Corrección del evaluador de stock multilínea por sucursal, agregando conservadoramente todas las líneas del pedido.
   - Preservación de nombres de calles y barrios en el paso de dirección que colisionaban con palabras reservadas de políticas comerciales (ej. "domingo").
   - Rollback transaccional explícito en memoria si la notificación de cotización confirmada al asesor fallaba.
   - Refuerzo del oráculo determinista `no_completion_claims` y alineación de regresiones históricas en la suite de pruebas.
2. **Cimiento e implementación completa de la Base Comercial Real (Commits 9 al 33):**
   - Configuración del perfil de base de datos comercial independiente (`alembic.commercial.ini`, variables de entorno y soporte para `secrets/xeon_commercial_url.txt`).
   - Creación de 5 migraciones Alembic normalizando el catálogo hasta **Cuarta Forma Normal (4FN)**: dimensiones de negocio, marcas, colores (`NO_APLICA`), taxonomía multinivel, listas de precio versionadas, inventario multisede y extensión `pgvector`.
   - Script extractor y sanitizador de datos reales (`build_commercial_seed.py`), procesando **4.830 referencias reales** de Ferretería El Campín y purgando costos, márgenes y NITs.
   - Generación de semilla e integridad criptográfica SHA-256 (`seeds/commercial/manifest.json`, `products.jsonl`).
   - Cargador transaccional idempotente (`seed_commercial_db.py`) con resolución de orden topológico inverso bajo restricciones de Foreign Key `RESTRICT`.
   - Conector SQL declarativo (`connectors/ferreteria-el-campin.yaml`) para consulta de solo lectura mediante `DATA_SOURCE=sql`.
   - Script de compilación e instalación nativa de `pgvector 0.8.7` para PostgreSQL 18 sobre Windows (`install_pgvector_windows.cmd`).
   - Verificador automatizado de consistencia (`verify_commercial_db.py`) comprobando revisiones, vistas y conteos exactos (4.830 productos, 23.148 precios, 37.216 registros de stock, 19 incidencias).
   - Documentación completa de arquitectura y modelos Entidad-Relación, Lógico y Físico (`MODELO_DATOS_COMERCIAL.md`, `BASE_COMERCIAL.md`).

---

## 2. Detalle Commit por Commit (33 Commits)

### Bloque A: Endurecimiento Funcional y QA (13:32 – 13:42)

#### Commit 1: `4d24f30`
- **Mensaje:** `Fix: :bug: LabelDraftTotalWithoutConfirmation`
- **Archivos:** `src/xeon/agent/executor.py`, `tests/test_qa_conde_conversation.py`
- **Descripción:** Cambió la etiqueta de total monetario en borradores preliminares de `TOTAL confirmado` a `TOTAL BORRADOR`. Evita que el cliente interprete un borrador no confirmado como una obligación contractual cerrada. Añadió regresión en pruebas unitarias.

#### Commit 2: `c14cd7d`
- **Mensaje:** `Fix: :bug: AggregateMultilineBranchStock`
- **Archivos:** `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`
- **Descripción:** Corrigió la lógica de disponibilidad de stock por sucursal para pedidos de varias líneas. Ahora realiza una agregación estricta sobre todo el carrito: si una sola línea no tiene existencias, la sede no se presenta como `disponible` total; si alguna línea tiene vigencia desconocida, el estado consolidado queda como `pendiente`.

#### Commit 3: `d2ad21b`
- **Mensaje:** `Fix: :bug: PreserveAddressPolicyWords`
- **Archivos:** `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`
- **Descripción:** En el paso de entrega a domicilio, previno que palabras comunes contenidas en nombres de barrios o direcciones (ej. "Barrio Santo Domingo") fueran capturadas erróneamente por el parser de políticas de horario. El texto en ese estado se consume prioritariamente como destino de entrega.

#### Commit 4: `02b7790`
- **Mensaje:** `Test: :test_tube: RejectPrematureConfirmedTotals`
- **Archivos:** `evals/checks/core.py`, `tests/evals/test_oracle_checks.py`
- **Descripción:** Reforzó la regla `no_completion_claims` del arnés de evaluación para detectar cualquier afirmación de confirmación anticipada en borradores, independientemente de la distancia léxica entre palabras clave.

#### Commit 5: `ebcd373`
- **Mensaje:** `Fix: :bug: RollBackFailedAdvisorNotification`
- **Archivos:** `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`
- **Descripción:** Implementó rollback atómico en memoria: si el notificador del asesor arroja una excepción al confirmar la cotización, el estado del borrador se revierte automáticamente a `DRAFT`, evitando cotizaciones huérfanas desatendidas.

#### Commit 6: `fb9749d`
- **Mensaje:** `Test: :test_tube: AlignDraftTotalRegressions`
- **Archivos:** `tests/test_e11_scope_followups.py`, `tests/test_live_qa_defects.py`, `tests/test_sql_connector.py`
- **Descripción:** Alineó 5 pruebas de regresión históricas que exigían la cadena antigua e insegura `TOTAL confirmado`, sustituyéndola por `TOTAL BORRADOR` y asegurando que fallen si se reintroduce la etiqueta defectuosa.

#### Commit 7: `7b02a71`
- **Mensaje:** `Docs: :memo: RecordQaHardeningResults`
- **Archivos:** `wiki/inbox/2026-10-31T120000-codex-qa-base-daniel.md`
- **Descripción:** Registró formalmente en el inbox de la wiki el resultado de la sincronización de base con `developer/daniel` y el ciclo de endurecimiento de QA completado (422 pruebas aprobadas, 66/66 evals offline).

#### Commit 8: `2a4698b`
- **Mensaje:** `Chore: :art: RefreshProjectGraph`
- **Archivos:** `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`
- **Descripción:** Regeneró los 14 hubs por capa del grafo Graphify y el mapa del proyecto en la wiki para indexar las nuevas aserciones y pruebas del embudo.

---

### Bloque B: Cimiento y Esquema de Base Comercial (17:16 – 17:18)

#### Commit 9: `550002c`
- **Mensaje:** `Feat: :sparkles: AddCommercialDatabaseProfile`
- **Archivos:** `alembic.commercial.ini`, `commercial_migrations/env.py`, `commercial_migrations/script.py.mako`, `src/xeon/config.py`, `tests/test_config.py`
- **Descripción:** Creó el perfil de base de datos comercial aislado de la persistencia operativa. Configuró variables de entorno `COMMERCIAL_DB_*`, archivo de configuración de Alembic independiente y soporte para leer la URL desde `secrets/xeon_commercial_url.txt`.

#### Commit 10: `efe551f`
- **Mensaje:** `Feat: :sparkles: AddCommercialCoreSchema`
- **Archivos:** `commercial_migrations/versions/0001_commercial_core.py`
- **Descripción:** Primera migración comercial: creó el esquema `commercial` y las tablas fundamentales de empresas (`businesses`), sucursales (`branches`), bodegas (`warehouses`), unidades de medida (`units_of_measure`, `product_units`) y clasificaciones tributarias (`tax_classes`).

#### Commit 11: `d1d6ead`
- **Mensaje:** `Feat: :sparkles: NormalizeCommercialCatalog`
- **Archivos:** `commercial_migrations/versions/0002_normalized_catalog.py`
- **Descripción:** Segunda migración comercial: normalizó el catálogo en Cuarta Forma Normal (4FN). Estableció dimensiones independientes y tablas puente para marcas (`brands`, `product_brands`), colores (`colors`, `product_colors` con valor canónico `NO_APLICA`), y taxonomía jerárquica en tres niveles (`product_lines`, `product_categories`, `product_sublines`).

#### Commit 12: `aa139e0`
- **Mensaje:** `Feat: :sparkles: AddVersionedCommercialPricing`
- **Archivos:** `commercial_migrations/versions/0003_versioned_pricing.py`
- **Descripción:** Tercera migración comercial: modeló listas de precios (`price_lists`) y precios efectivos versionados (`product_prices`) con rangos de vigencia obligatorios (`valid_from`, `valid_until`), tarifas tributarias vigentes (`tax_rates`) y manejo de precios cero (`MISSING_PRICE`).

#### Commit 13: `1cddfc7`
- **Mensaje:** `Feat: :sparkles: NormalizeWarehouseStock`
- **Archivos:** `commercial_migrations/versions/0004_normalized_stock.py`
- **Descripción:** Cuarta migración comercial: creó la tabla normalizada de inventario (`stock`) por producto, bodega y unidad, con trazabilidad de tipos de cantidad (`on_hand`, `reserved`, `transit`), vigencia temporal del dato y observaciones.

#### Commit 14: `04655b0`
- **Mensaje:** `Feat: :sparkles: AddVectorSearchFoundation`
- **Archivos:** `commercial_migrations/versions/0005_vector_search_foundation.py`
- **Descripción:** Quinta migración comercial: activó la extensión PostgreSQL `pgvector`, generó la columna de búsqueda léxica en español (`tsv_spanish`) e introdujo la columna vectorial `embedding` (`vector`) sin dimensión fija prematura ni índices ANN, preparando el cimiento para RAG semántico.

---

### Bloque C: Sanitización, Semilla y Conector SQL (17:19 – 17:29)

#### Commit 15: `c8e2ea5`
- **Mensaje:** `Feat: :sparkles: BuildSanitizedCommercialSeed`
- **Archivos:** `scripts/build_commercial_seed.py`, `tests/test_commercial_seed_builder.py`
- **Descripción:** Implementó el script de extracción y sanitización determinista. Procesa el catálogo original de 4.830 artículos purgando NITs, costos de compra, márgenes de utilidad y proveedores, generando el archivo sanitizado `products.jsonl`.

#### Commit 16: `d269fd2`
- **Mensaje:** `Data: :card_file_box: AddCommercialCatalogSeed`
- **Archivos:** `seeds/commercial/manifest.json`, `seeds/commercial/products.jsonl`
- **Descripción:** Agregó los archivos de datos de la semilla comercial sanitizada con los 4.830 SKUs reales de Ferretería El Campín y el manifiesto criptográfico con huella SHA-256.

#### Commit 17: `7e5b059`
- **Mensaje:** `Fix: :bug: StabilizeSeedFingerprint`
- **Archivos:** `scripts/build_commercial_seed.py`, `seeds/commercial/manifest.json`, `tests/test_commercial_seed_builder.py`
- **Descripción:** Estabilizó el cálculo de la huella SHA-256 asegurando ordenamiento canónico de claves JSON (`sort_keys=True`) y saltos de línea estandarizados, evitando falsos fallos de integridad entre plataformas.

#### Commit 18: `fe3fadd`
- **Mensaje:** `Feat: :sparkles: LoadNormalizedCommercialSeed`
- **Archivos:** `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`
- **Descripción:** Desarrolló el cargador transaccional por lotes para insertar el catálogo sanitizado en PostgreSQL. Adquiere bloqueo a nivel de tabla y comprueba el hash SHA-256 antes de iniciar la transacción.

#### Commit 19: `8bf5475`
- **Mensaje:** `Feat: :electric_plug: ConnectCommercialCatalog`
- **Archivos:** `connectors/ferreteria-el-campin.yaml`, `tests/test_sql_connector.py`
- **Descripción:** Creó la configuración declarativa del conector SQL para Ferretería El Campín, mapeando las vistas calculadas `vw_cotizable_products`, `vw_branch_stock` y `vw_branches` para ser consumidas por el agente comercial.

#### Commit 20: `ba026fd`
- **Mensaje:** `Test: :test_tube: VerifyCommercialSchemaContracts`
- **Archivos:** `tests/test_commercial_migrations.py`
- **Descripción:** Diseñó pruebas unitarias de inspección de sintaxis abstracta (AST) sobre las migraciones comerciales para verificar la linealidad estricta de la cadena Alembic y validar que la extensión pgvector no fije dimensión fija prematuramente.

#### Commit 21: `7491e56`
- **Mensaje:** `Docs: :memo: DocumentCommercialDatabase`
- **Archivos:** `docs/ARCHITECTURE.md`, `docs/BASE_COMERCIAL.md`, `docs/README.md`, `docs/XeonContexto.md`
- **Descripción:** Documentó formalmente la arquitectura de la base comercial de Ferretería El Campín en las guías técnicas del proyecto, estableciendo la separación entre la base operativa y el catálogo comercial.

#### Commit 22: `aebcbe7`
- **Mensaje:** `Docs: :memo: RecordCommercialDatabaseDecision`
- **Archivos:** `wiki/index.md`, `wiki/log.md`, `wiki/pages/base-comercial.md`, `wiki/pages/conector-ferreteria.md`, `wiki/pages/estado-del-corte.md`, `wiki/sources.md`
- **Descripción:** Registró en la wiki la incorporación de la base comercial real, creando la página `base-comercial.md` y actualizando el índice y el registro de operaciones.

#### Commit 23: `0664123`
- **Mensaje:** `Docs: :world_map: RefreshProjectGraph`
- **Archivos:** `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`
- **Descripción:** Actualizó los diagramas y hubs de Graphify para incluir los nuevos módulos de base comercial y scripts de semilla.

#### Commit 24: `3618e11`
- **Mensaje:** `Chore: :wrench: IgnoreRestrictedPytestTemps`
- **Archivos:** `.gitignore`
- **Descripción:** Añadió `.tmp-pytest-*` al `.gitignore` para ignorar carpetas temporales de prueba que sufrían bloqueos de concurrencia en Windows.

#### Commit 25: `515867a`
- **Mensaje:** `Fix: :bug: MakeCommercialSeedRepeatable`
- **Archivos:** `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`
- **Descripción:** Ajustó `seed_commercial_db.py` para garantizar que la carga sea repetible sin duplicación de filas ni errores de integridad referencial.

---

### Bloque D: Verificación, Herramientas Windows y Despliegue (17:37 – 17:59)

#### Commit 26: `e83aa3e`
- **Mensaje:** `Test: :test_tube: AddCommercialDatabaseVerifier`
- **Archivos:** `scripts/verify_commercial_db.py`, `tests/test_verify_commercial_db.py`
- **Descripción:** Desarrolló el script de verificación automatizada `verify_commercial_db.py` para auditar la versión del motor PostgreSQL, la presencia de pgvector y la integridad de las vistas comerciales.

#### Commit 27: `8c68e2e`
- **Mensaje:** `Fix: :bug: OrderCommercialSeedCleanup`
- **Archivos:** `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`
- **Descripción:** Corrigió el orden topológico inverso de eliminación de tablas dependientes en el seed comercial bajo restricciones `RESTRICT` de clave foránea, garantizando repetibilidad absoluta.

#### Commit 28: `58ea8a3`
- **Mensaje:** `Test: :test_tube: VerifyCommercialViewsAndCounts`
- **Archivos:** `scripts/verify_commercial_db.py`
- **Descripción:** Amplió el verificador para validar las cuatro vistas comerciales calculadas y los conteos exactos: 4.830 productos, 23.148 precios, 37.216 filas de stock y 19 incidencias de calidad.

#### Commit 29: `da52bcf`
- **Mensaje:** `Chore: :hammer_and_wrench: InstallPgvectorOnWindows`
- **Archivos:** `scripts/install_pgvector_windows.cmd`
- **Descripción:** Creó el script automatizado para compilar e instalar `pgvector v0.8.7` en entornos Windows nativos con PostgreSQL 18 utilizando Microsoft Visual C++ Build Tools.

#### Commit 30: `ddf6945`
- **Mensaje:** `Docs: :memo: AddCommercialDataModels`
- **Archivos:** `docs/BASE_COMERCIAL.md`, `docs/MODELO_DATOS_COMERCIAL.md`, `docs/README.md`
- **Descripción:** Creó la documentación técnica de modelos de datos comerciales: modelo Entidad-Relación conceptual, modelo relacional en 4FN y diseño físico de tablas e índices en PostgreSQL.

#### Commit 31: `fb63e99`
- **Mensaje:** `Docs: :memo: RecordCommercialDatabaseDeployment`
- **Archivos:** `wiki/log.md`, `wiki/pages/base-comercial.md`, `wiki/pages/estado-del-corte.md`, `wiki/sources.md`
- **Descripción:** Registró formalmente en la wiki el despliegue exitoso de la base comercial en PostgreSQL 18.6 con pgvector 0.8.7 local, documentando la revisión física `0005`.

#### Commit 32: `2f26198`
- **Mensaje:** `Docs: :world_map: RefreshCommercialDataGraph`
- **Archivos:** `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`
- **Descripción:** Actualizó el grafo de Graphify con la documentación de modelos comerciales y despliegue físico.

#### Commit 33: `1e50603`
- **Mensaje:** `Test: :test_tube: ReportCommercialDatabaseName`
- **Archivos:** `scripts/verify_commercial_db.py`, `tests/test_verify_commercial_db.py`
- **Descripción:** Mejoró la salida de `verify_commercial_db.py` para reportar explícitamente el nombre de la base de datos PostgreSQL conectada y sincronizó las pruebas unitarias.


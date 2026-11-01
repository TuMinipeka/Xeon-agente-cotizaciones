# Cambios de Juan Pablo Conde

> Historial de la rama `developer/conde`: el carrito y la confirmación de SKU descritos aquí no
> se integraron en `merge/conde-integration` por la decisión D7. La implementación vigente usa
> cotización directa y memoria conversacional corta; sí incorpora alcance comercial, filtrado
> de respuestas y datos sintéticos ampliados.
> La referencia posterior a `HermesToolbelt` es histórica: desde D9 se llama
> `CommercialToolbelt`; el proveedor Hermes y el canal Evolution fueron retirados.

## 2026-10-17 — Memoria conversacional y carrito comercial

### Implementado

- Sesiones en memoria limitadas a 1024 conversaciones, identificadas en WhatsApp por instancia y
  remitente. Conservan ubicación, opciones, cantidad pendiente, carrito y borrador finalizado.
- Pregunta inicial de ciudad o zona. Las sedes demo norte, sur y centro se resuelven de forma
  determinista; otras ubicaciones no generan una falsa promesa de cercanía.
- Cambio de intención: un producto nuevo y claro reemplaza una selección anterior sin forzar al
  comprador a confirmarla.
- Selección natural por nombre, ordinal o referencia pronominal; una cantidad aislada completa la
  pregunta anterior y nunca se asume una cantidad ausente.
- Carrito con agregar, acumular, cambiar cantidad, eliminar, mostrar resumen y finalizar. Solo al
  finalizar se crea un borrador con todas las líneas.
- Continuidad automática hasta 24 horas, pregunta entre 24 horas y 3 días y carrito nuevo después
  de 3 días. Un borrador finalizado siempre pregunta si se reutiliza o se comienza otro.
- Precios visibles con formato `$28.900`, sin `COP`, SKU ni marcadores internos.
- Seed determinista de exactamente 2000 referencias ficticias, con inventario sintético para las
  sedes de demostración. La búsqueda filtra unidades y prioriza opciones de la misma intención.

### Decisiones y límites

- No se construyó un manual operativo ni un motor de cálculo de obra. El LLM interpreta lenguaje;
  catálogo y backend siguen siendo la única fuente de productos, unidades, precios y existencias.
- La memoria se pierde al reiniciar. PostgreSQL continúa pendiente y está documentado como el paso
  para continuidad durable.
- No se implementaron fotografías, PDF, cierre por agradecimiento, geolocalización real de sedes,
  recomendaciones por compatibilidad ni notificaciones a trabajadores.
- Cuando no existe disponibilidad verificable, el chat se disculpa y ofrece alternativas observadas;
  no afirma que un producto está agotado ni que avisó a un encargado.
- Las pruebas se ejecutan con `MockLLM`. Una prueba real queda condicionada a la confirmación
  explícita del otro desarrollador y no forma parte de la suite automática.

### Cobertura añadida

- Tamaño y procedencia del catálogo sintético.
- Ubicación inicial y continuidad por conversación en API y WhatsApp.
- Sustitución de una opción pendiente al cambiar claramente de producto.
- Carrito multilínea, resumen, cambio de cantidad, eliminación y borrador único al finalizar.
- Reanudación temporal entre 24 horas y 3 días, reinicio posterior y elección tras finalizar.
- Defensa de salida sin códigos internos, enlaces no aprobados ni moneda redundante.

### Verificación

- `uv run ruff check .`: sin errores.
- `uv run ruff format --check .`: 67 archivos formateados.
- `uv run mypy src`: 42 archivos fuente sin errores.
- `uv run pytest`: 99 pruebas aprobadas usando `MockLLM`.

### Commits

- `Feat: :sparkles: AddSyntheticHardwareSeed`
- `Feat: :sparkles: AddInMemoryConversationCart`
- `Test: :test_tube: CoverConversationCartFlow`
- `Docs: :memo: DocumentConversationCart`

## 2026-10-17 — Arnés conversacional seguro para clientes

### Decisiones aplicadas

- El alcance permitido cubre ferretería, construcción, agroferretería, plomería, electricidad y
  herramientas. Cortesía y ayuda operativa se responden localmente; el conocimiento general se
  bloquea antes de llamar al LLM.
- Las solicitudes mixtas se separan de forma determinista y solo se procesa la parte comercial.
- El texto dirigido al cliente nunca muestra SKU, etiquetas de herramientas, estados técnicos,
  prompts, proveedor ni detalles de arquitectura. Los identificadores permanecen disponibles
  únicamente en el contexto interno y en pruebas técnicas.
- Los candidatos se muestran por nombre, unidad y precio. El comprador elige por nombre o número
  de opción; también se conserva compatibilidad interna con códigos existentes.
- `CustomerResponsePolicy` reemplaza cualquier salida que exponga códigos internos o enlaces no
  registrados. En este corte no hay enlaces aprobados configurados, por lo que todos se bloquean.
- Un producto ferretero ausente se describe como no encontrado en el catálogo disponible; no se
  afirma que esté agotado. Si ya se revisaron productos en la conversación, XEON ofrece continuar
  con ellos.
- No se implementó todavía la notificación de necesidades de catálogo a un trabajador. Queda como
  capacidad futura separada de la aprobación de cotizaciones por Gmail, y el chat no promete un
  aviso que el backend aún no puede ejecutar.

### Respuestas esperadas

- Tema externo: negativa breve indicando que se trata de una ferretería y ofreciendo ayuda dentro
  de las categorías permitidas.
- Saludo: respuesta cercana que pregunta qué material o herramienta necesita el comprador.
- Ayuda: explicación práctica basada en producto, cantidad y sede, sin arquitectura interna.
- Candidato: lista numerada con nombres naturales y solicitud de selección.
- Producto confirmado: precio, disponibilidad verificable y borrador expresados en lenguaje de
  asesor, sin códigos internos.

### Cobertura añadida

- Bloqueo de tarjetas gráficas y enlaces antes del LLM.
- Permiso de categorías comerciales y selecciones conversacionales.
- Separación de una solicitud mixta.
- Reemplazo de una salida maliciosa con código o enlace externo.
- Selección por «la primera opción» en API y WhatsApp.
- Continuidad con productos ya revisados cuando otro no aparece en el catálogo.

### Verificación

- `uv sync --locked`: 36 paquetes resueltos y comprobados.
- `uv run ruff check .`: sin errores.
- `uv run ruff format --check .`: 65 archivos formateados.
- `uv run mypy src`: 41 archivos sin errores.
- `uv run pytest`: 94 pruebas aprobadas.

### Commits

- `Feat: :sparkles: AddDeterministicCommercialScope`
- `Feat: :sparkles: AddCustomerSafeConversationHarness`
- `Docs: :memo: DocumentCustomerConversationHarness`

### Limitaciones vigentes

- La política usa vocabulario controlado en código; aún no existe un catálogo administrable de
  categorías o enlaces.
- La memoria conversacional y la lista de productos revisados se pierden al reiniciar el proceso.
- No existe todavía un registro persistente ni una notificación real de productos solicitados que
  estén ausentes del catálogo.

## 2026-10-17 — Confirmación conversacional de SKU

> Historial: este corte introdujo la confirmación interna por SKU. El arnés posterior mantiene esa
> seguridad en el backend, pero el comprador ahora confirma por nombre o número de opción y no ve
> códigos internos.

### Objetivo

Impedir que una coincidencia descriptiva se trate como producto confirmado. XEON debe mostrar los
SKU candidatos y esperar a que el comprador responda explícitamente con uno de ellos antes de
consultar inventario o crear un borrador de cotización.

### Reglas implementadas

- Una coincidencia exacta por SKU o alias mantiene el flujo comercial existente.
- Una búsqueda descriptiva con candidatos devuelve `confirmation_required` y no ejecuta
  `get_stock_by_branches` ni `create_quote_draft`.
- Los candidatos pendientes se conservan por `conversation_id` en la API y por
  `instancia + sender_jid` en WhatsApp.
- Solo se acepta un SKU incluido en la lista pendiente. Un SKU diferente mantiene bloqueadas las
  operaciones comerciales.
- Al confirmar, se recuperan la cantidad y la sede de la solicitud original; una cantidad o sede
  explícita en la confirmación tiene prioridad.
- La memoria está limitada a 1024 conversaciones y vive en el proceso. Se pierde al reiniciar;
  todavía no sustituye la persistencia pendiente en PostgreSQL.

### Flujo verificable

1. El comprador escribe: `necesito 50 bultos para fundir una placa y pegar ladrillo`.
2. XEON presenta `CEM-50` como candidato y solicita que se confirme el SKU.
3. No se consulta stock ni se crea un `DRAFT` durante ese primer turno.
4. El comprador responde: `Confirmo el SKU CEM-50` en la misma conversación.
5. XEON registra la selección, consulta el stock sintético y crea el borrador con la cantidad
   conservada del primer turno.

### Cobertura

- Flujo directo de `HermesToolbelt`.
- Continuidad mediante `POST /v1/chat` usando el mismo `conversation_id`.
- Continuidad mediante dos webhooks de WhatsApp del mismo remitente.
- Rechazo de un SKU que no pertenece a los candidatos pendientes.
- Perfil `mock`; no se realizan llamadas pagadas ni conexiones externas.

### Commits

- `Feat: :sparkles: RequireConversationalSkuConfirmation`
- `Test: :test_tube: CoverSkuConfirmationGuards`
- `Fix: :bug: NarrowPendingConversationKey`
- `Docs: :memo: DocumentCondeSkuConfirmation`

### Verificación

- `uv sync --locked`: 36 paquetes resueltos y comprobados.
- `uv run ruff check .`: sin errores.
- `uv run ruff format --check .`: 61 archivos formateados.
- `uv run mypy src`: 39 archivos sin errores.
- `uv run pytest`: 83 pruebas aprobadas.

## 2026-10-31 — Conde implementado 31 octubre

> Registro completo commit por commit de las 33 contribuciones implementadas por Juan Pablo Conde
> (`CondezPancake`) en la rama `QA/testing` el 31 de octubre de 2026. Cubre el endurecimiento de QA
> comercial y el desarrollo y despliegue físico de la base de datos comercial normalizada (4FN) con
> datos reales de Ferretería El Campín.

### Resumen del corte

1. **Endurecimiento funcional y QA (Commits 1 al 8):**
   - Etiquetado no prematuro de totales: `TOTAL BORRADOR` en lugar de `TOTAL confirmado` antes de la confirmación formal del comprador (`4d24f30`).
   - Evaluación conservadora de disponibilidad multilínea en sucursales para el 100% de las líneas del carrito (`c14cd7d`).
   - Preservación de términos de políticas (ej. "domingo") en nombres de barrios y direcciones de entrega (`d2ad21b`).
   - Rollback transaccional a `DRAFT` si falla la notificación al asesor humano tras confirmar (`ebcd373`).
   - Refuerzo del oráculo determinista `no_completion_claims` y alineación de regresiones históricas (`02b7790`, `fb9749d`).
2. **Base comercial real de Ferretería El Campín (Commits 9 al 33):**
   - Perfil de base de datos comercial independiente de la persistencia operativa (`alembic.commercial.ini`, `550002c`).
   - 5 migraciones Alembic normalizando el catálogo hasta **Cuarta Forma Normal (4FN)**: dimensiones base, marcas, colores (`NO_APLICA`), taxonomía multinivel, listas de precio versionadas, inventario multisede y extensión `pgvector` (`efe551f` a `04655b0`).
   - Sanitización determinista de 4.830 artículos comerciales reales purgando NITs, costos y márgenes (`c8e2ea5`, `d269fd2`).
   - Integridad criptográfica SHA-256 (`manifest.json`) y cargador transaccional idempotente bajo FK `RESTRICT` (`7e5b059`, `fe3fadd`, `8c68e2e`).
   - Conector SQL de solo lectura (`ferreteria-el-campin.yaml`, `8bf5475`).
   - Script de compilación e instalación nativa de `pgvector 0.8.7` para PostgreSQL 18 en Windows (`da52bcf`).
   - Verificador automatizado de consistencia comprobando 4.830 productos, 23.148 precios, 37.216 filas de stock y 19 incidencias de precio cero (`e83aa3e`, `58ea8a3`, `1e50603`).
   - Documentación técnica exhaustiva de modelos Entidad-Relación, Lógico 4FN y Físico (`ddf6945`).

### Detalle commit x commit

1. `4d24f30` — `Fix: :bug: LabelDraftTotalWithoutConfirmation`:
   - *Archivos:* `src/xeon/agent/executor.py`, `tests/test_qa_conde_conversation.py`.
   - *Detalle:* Cambió el texto de total monetario en borradores preliminares a `TOTAL BORRADOR: $XX.XXX`. Impide que el cliente interprete un borrador previo a la confirmación como un contrato cerrado.
2. `c14cd7d` — `Fix: :bug: AggregateMultilineBranchStock`:
   - *Archivos:* `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`.
   - *Detalle:* Corrigió el cálculo de disponibilidad multisede para carritos con múltiples productos. Ahora evalúa la totalidad de las líneas de forma conservadora: si un solo artículo está agotado en la sede, no se marca como disponible; si hay vigencia desconocida, queda pendiente.
3. `d2ad21b` — `Fix: :bug: PreserveAddressPolicyWords`:
   - *Archivos:* `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`.
   - *Detalle:* Evitó que palabras de políticas comerciales (ej. "domingo" en "Barrio Santo Domingo") fueran capturadas erróneamente por el parser en el paso de captura de dirección de entrega.
4. `02b7790` — `Test: :test_tube: RejectPrematureConfirmedTotals`:
   - *Archivos:* `evals/checks/core.py`, `tests/evals/test_oracle_checks.py`.
   - *Detalle:* Reforzó la regla `no_completion_claims` en el arnés de evaluación para rechazar de forma estricta cualquier afirmación de confirmación antes de los pasos contractuales.
5. `ebcd373` — `Fix: :bug: RollBackFailedAdvisorNotification`:
   - *Archivos:* `src/xeon/agent/guided_funnel.py`, `tests/test_guided_funnel.py`.
   - *Detalle:* Añadió reversión automática a `DRAFT` si `advisor_notifier` falla al notificar la confirmación, impidiendo cotizaciones huérfanas en el estado en memoria.
6. `fb9749d` — `Test: :test_tube: AlignDraftTotalRegressions`:
   - *Archivos:* `tests/test_e11_scope_followups.py`, `tests/test_live_qa_defects.py`, `tests/test_sql_connector.py`.
   - *Detalle:* Alineó cinco pruebas históricas que exigían la etiqueta antigua e insegura `TOTAL confirmado`, sustituyéndola por `TOTAL BORRADOR` y asegurando que fallen si se reintroduce la etiqueta defectuosa.
7. `7b02a71` — `Docs: :memo: RecordQaHardeningResults`:
   - *Archivos:* `wiki/inbox/2026-10-31T120000-codex-qa-base-daniel.md`.
   - *Detalle:* Registró formalmente en el inbox de la wiki el resultado de la sincronización de base con `developer/daniel` y el ciclo de QA completado (422 pruebas aprobadas, 66/66 evals offline).
8. `2a4698b` — `Chore: :art: RefreshProjectGraph`:
   - *Archivos:* `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`.
   - *Detalle:* Regeneró los 14 hubs por capa del grafo Graphify y el mapa del proyecto en la wiki para indexar las nuevas aserciones y pruebas del embudo.
9. `550002c` — `Feat: :sparkles: AddCommercialDatabaseProfile`:
   - *Archivos:* `alembic.commercial.ini`, `commercial_migrations/env.py`, `commercial_migrations/script.py.mako`, `src/xeon/config.py`, `tests/test_config.py`.
   - *Detalle:* Configuró el perfil de base de datos comercial independiente de la persistencia operativa. Añadió variables de configuración `COMMERCIAL_DB_*`, archivo de configuración de Alembic aislado y soporte de URL secreta en `secrets/xeon_commercial_url.txt`.
10. `efe551f` — `Feat: :sparkles: AddCommercialCoreSchema`:
    - *Archivos:* `commercial_migrations/versions/0001_commercial_core.py`.
    - *Detalle:* Primera migración de la base comercial: creó el esquema `commercial` y las tablas base de negocio (`businesses`), sucursales (`branches`), bodegas (`warehouses`), unidades de medida (`units_of_measure`, `product_units`) y clases de impuestos (`tax_classes`).
11. `d1d6ead` — `Feat: :sparkles: NormalizeCommercialCatalog`:
    - *Archivos:* `commercial_migrations/versions/0002_normalized_catalog.py`.
    - *Detalle:* Segunda migración comercial: normalizó el catálogo hasta 4FN. Separa marcas (`brands`), colores (`colors` con valor canónico `NO_APLICA`), y taxonomía jerárquica en tres niveles (`product_lines`, `product_categories`, `product_sublines`) mediante tablas puente N:M. Tipos de producto (`product_types`).
12. `aa139e0` — `Feat: :sparkles: AddVersionedCommercialPricing`:
    - *Archivos:* `commercial_migrations/versions/0003_versioned_pricing.py`.
    - *Detalle:* Tercera migración comercial: listas de precios múltiples (`price_lists`) y precios efectivos versionados (`product_prices`) con rangos de vigencia temporal (`valid_from`, `valid_until`), tarifas de impuesto vigentes (`tax_rates`) y manejo de precios cero/no vendibles (`MISSING_PRICE`).
13. `1cddfc7` — `Feat: :sparkles: NormalizeWarehouseStock`:
    - *Archivos:* `commercial_migrations/versions/0004_normalized_stock.py`.
    - *Detalle:* Cuarta migración comercial: estructura normalizada de inventario (`stock`) por artículo, bodega y unidad de medida, con clasificación de cantidades, observaciones de abastecimiento y vigencia del dato.
14. `04655b0` — `Feat: :sparkles: AddVectorSearchFoundation`:
    - *Archivos:* `commercial_migrations/versions/0005_vector_search_foundation.py`.
    - *Detalle:* Quinta migración comercial: instaló la extensión `pgvector`, creó el documento de búsqueda textual en español (`tsv_spanish`) para búsquedas léxicas, y añadió la columna `embedding` (`vector`) para la futura recuperación semántica de SKUs sin fijar dimensión prematuramente.
15. `c8e2ea5` — `Feat: :sparkles: BuildSanitizedCommercialSeed`:
    - *Archivos:* `scripts/build_commercial_seed.py`, `tests/test_commercial_seed_builder.py`.
    - *Detalle:* Script constructor de semilla comercial sanitizada. Procesa el catálogo original de 4.830 referencias eliminando NITs, costos internos, márgenes de utilidad y proveedores, generando `products.jsonl`.
16. `d269fd2` — `Data: :card_file_box: AddCommercialCatalogSeed`:
    - *Archivos:* `seeds/commercial/manifest.json`, `seeds/commercial/products.jsonl`.
    - *Detalle:* Incorporación de los archivos de semilla comercial sanitizada con 4.830 artículos reales de Ferretería El Campín y su manifiesto con huella SHA-256.
17. `7e5b059` — `Fix: :bug: StabilizeSeedFingerprint`:
    - *Archivos:* `scripts/build_commercial_seed.py`, `seeds/commercial/manifest.json`, `tests/test_commercial_seed_builder.py`.
    - *Detalle:* Estabilización del cálculo de huella SHA-256 en la serialización JSON mediante ordenamiento canónico de claves (`sort_keys=True`) para garantizar idéntico hash en cualquier sistema operativo.
18. `fe3fadd` — `Feat: :sparkles: LoadNormalizedCommercialSeed`:
    - *Archivos:* `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`.
    - *Detalle:* Script cargador transaccional por lotes para poblar la base comercial en PostgreSQL a partir de `products.jsonl`. Valida la huella del manifiesto y adquiere bloqueos de tabla.
19. `8bf5475` — `Feat: :electric_plug: ConnectCommercialCatalog`:
    - *Archivos:* `connectors/ferreteria-el-campin.yaml`, `tests/test_sql_connector.py`.
    - *Detalle:* Configuración declarativa del conector SQL para Ferretería El Campín. Mapea las vistas de catálogo cotizable, stock por bodega y directorio de sedes para consumo por `DATA_SOURCE=sql`.
20. `ba026fd` — `Test: :test_tube: VerifyCommercialSchemaContracts`:
    - *Archivos:* `tests/test_commercial_migrations.py`.
    - *Detalle:* Pruebas unitarias de inspección de AST para validar la linealidad de la cadena de migraciones Alembic de la base comercial y asegurar que la columna `vector` no fija dimensión prematura ni crea índices ANN.
21. `7491e56` — `Docs: :memo: DocumentCommercialDatabase`:
    - *Archivos:* `docs/ARCHITECTURE.md`, `docs/BASE_COMERCIAL.md`, `docs/README.md`, `docs/XeonContexto.md`.
    - *Detalle:* Documentación técnica completa de la base comercial de Ferretería El Campín, explicando el modelo híbrido SQL + JSONB + pgvector, los procedimientos de carga y la separación de la persistencia operativa.
22. `aebcbe7` — `Docs: :memo: RecordCommercialDatabaseDecision`:
    - *Archivos:* `wiki/index.md`, `wiki/log.md`, `wiki/pages/base-comercial.md`, `wiki/pages/conector-ferreteria.md`, `wiki/pages/estado-del-corte.md`, `wiki/sources.md`.
    - *Detalle:* Registro formal en la wiki de la decisión de incorporar la base comercial real sanitizada, creando la página `base-comercial.md` y actualizando el estado del corte.
23. `0664123` — `Docs: :world_map: RefreshProjectGraph`:
    - *Archivos:* `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`.
    - *Detalle:* Actualización del grafo de Graphify para incluir las nuevas migraciones, conectores y scripts de la base comercial.
24. `3618e11` — `Chore: :wrench: IgnoreRestrictedPytestTemps`:
    - *Archivos:* `.gitignore`.
    - *Detalle:* Exclusión de directorios temporales `.tmp-pytest-*` en Git para evitar errores de permisos en Windows durante la ejecución de pruebas concurrentes.
25. `515867a` — `Fix: :bug: MakeCommercialSeedRepeatable`:
    - *Archivos:* `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`.
    - *Detalle:* Corrección en el cargador de semilla comercial para asegurar que la re-ejecución sea limpia y repetible sin duplicación de filas ni errores de llaves foráneas.
26. `e83aa3e` — `Test: :test_tube: AddCommercialDatabaseVerifier`:
    - *Archivos:* `scripts/verify_commercial_db.py`, `tests/test_verify_commercial_db.py`.
    - *Detalle:* Creación del script de verificación de consistencia de la base comercial (`verify_commercial_db.py`) y sus correspondientes pruebas unitarias con mocks de conexión.
27. `8c68e2e` — `Fix: :bug: OrderCommercialSeedCleanup`:
    - *Archivos:* `scripts/seed_commercial_db.py`, `tests/test_commercial_seeder.py`.
    - *Detalle:* Corrección del orden topológico inverso de limpieza de tablas en `seed_commercial_db.py` para respetar restricciones de Foreign Key con `RESTRICT`.
28. `58ea8a3` — `Test: :test_tube: VerifyCommercialViewsAndCounts`:
    - *Archivos:* `scripts/verify_commercial_db.py`.
    - *Detalle:* Ampliación del verificador para validar las cuatro vistas comerciales calculadas y los conteos exactos (4.830 productos, 23.148 precios, 37.216 filas de stock, 19 incidencias).
29. `da52bcf` — `Chore: :hammer_and_wrench: InstallPgvectorOnWindows`:
    - *Archivos:* `scripts/install_pgvector_windows.cmd`.
    - *Detalle:* Script por lotes automatizado para compilar e instalar `pgvector v0.8.7` en Windows nativo con PostgreSQL 18 utilizando MSVC Build Tools.
30. `ddf6945` — `Docs: :memo: AddCommercialDataModels`:
    - *Archivos:* `docs/BASE_COMERCIAL.md`, `docs/MODELO_DATOS_COMERCIAL.md`, `docs/README.md`.
    - *Detalle:* Creación del documento exhaustivo de modelos de datos comerciales: modelo Entidad-Relación conceptual, modelo relacional en 4FN y diseño físico de tablas e índices en PostgreSQL.
31. `fb63e99` — `Docs: :memo: RecordCommercialDatabaseDeployment`:
    - *Archivos:* `wiki/log.md`, `wiki/pages/base-comercial.md`, `wiki/pages/estado-del-corte.md`, `wiki/sources.md`.
    - *Detalle:* Registró formalmente en la wiki el despliegue efectivo de la base comercial en PostgreSQL 18.6 con pgvector 0.8.7 local, documentando la revisión física `0005`.
32. `2f26198` — `Docs: :world_map: RefreshCommercialDataGraph`:
    - *Archivos:* `wiki/graph/hub-*.md`, `wiki/graph/mapa-proyecto.md`.
    - *Detalle:* Actualizó el grafo de Graphify con la documentación de modelos comerciales y despliegue físico.
33. `1e50603` — `Test: :test_tube: ReportCommercialDatabaseName`:
    - *Archivos:* `scripts/verify_commercial_db.py`, `tests/test_verify_commercial_db.py`.
    - *Detalle:* Mejoró la salida de `verify_commercial_db.py` para reportar explícitamente el nombre de la base de datos PostgreSQL conectada y sincronizó las pruebas unitarias.

### Verificación final del bloque

- `uv run --locked ruff check .`: aprobado sin errores.
- `uv run --locked ruff format --check .`: más de 260 archivos formateados.
- `uv run --locked mypy src evals`: 117 archivos fuente sin errores.
- `uv run --locked pytest`: 422 pruebas aprobadas, 21 deseleccionadas.
- `scripts/verify_commercial_db.py`: validación de revisión `0005_vector_search_foundation`, 4 vistas calculadas y conteos completos (4.830 SKU, 23.148 precios, 37.216 registros de stock, 19 incidencias).


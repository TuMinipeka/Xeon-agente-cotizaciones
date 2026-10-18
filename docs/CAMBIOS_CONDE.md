# Cambios de Juan Pablo Conde

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

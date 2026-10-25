# Informe Técnico y Notas de Entrega — Hito #2 (XEON)

**Fecha de corte:** 24 de octubre de 2026  
**Rama de trabajo:** `developer/daniel` (con commits posteriores al último merge en `develop`, `349bb7b`)  
**Motor LLM predeterminado:** `grok-4.6` (`https://api.reto.pltk.mx/v1`)  
**Canal de mensajería:** WhatsApp Cloud API vía Kapso (`POST /v1/channels/whatsapp/kapso/webhook`) y terminal interactiva `XEON CLI` (`uv run xeon`)

---

## 1. Resumen del hito y definición

De acuerdo con la hoja de ruta del proyecto (`wiki/raw/orquestacion-original-2026-10-24.md`, línea 12, y `wiki/pages/hito-s2.md`), el **Hito #2 (Semana 2)** se define por dos entregables verificables:

1. **Tres herramientas comerciales funcionales conectadas en vivo a Grok (`grok-4.6`)** a través de `AgentService` y `CommercialToolbelt`, donde el modelo interpreta la intención del comprador y redacta la respuesta, pero todos los cálculos monetarios (`Decimal`), consultas de existencias y estados provienen del backend determinista:
   - `search_products`: búsqueda en el catálogo por SKU, alias o puntuación léxica de especificaciones, con desambiguación obligatoria ante múltiples candidatos o referencias incompletas.
   - `get_stock_by_branches`: consulta de inventario por sede (`sede-norte`, `sede-centro`, `sede-sur` y despacho), distinguiendo disponibilidad local (`local`), traslado (`transfer`), entrega (`delivery`), estado (`sufficient`, `partial`, `unknown`) y vigencia del dato (`fresh`, `stale`, `unknown`).
   - `create_quote_draft`: creación idempotente de borradores de cotización en estado `DRAFT` (versión 1), de una o varias líneas, sin impuestos, sin inventar porcentajes de descuento y sin aprobar ni reservar inventario.
2. **Flujo demostrativo reproducible de menos de 2 minutos**, ejecutado y grabado sobre el sistema real (WhatsApp vía Kapso y terminal interactiva `XEON CLI`) con evidencia explícita de las tres herramientas en ejecución.

---

## 2. Qué se logró

### 2.1. Stack tecnológico actual e integraciones operativas

| Componente | Implementación verificada en este corte | Evidencia en el repositorio |
|---|---|---|
| **Motor LLM principal (`grok-4.6`)** | Perfil predeterminado `grok` sobre `OpenAICompatibleLLM` (`LLMPort`), conectado a la pasarela del reto (`https://api.reto.pltk.mx/v1`) con lectura de credencial desde `secrets/grok_api_key.txt`. | `src/xeon/config.py`, `src/xeon/adapters/llm/openai_compatible.py`, commit `2a7d098` y corrección `QA4` |
| **Proveedores LLM de respaldo y prueba** | Perfil `groq` (`https://api.groq.com/openai/v1`, `compose.groq.yaml`) como alternativa explícita y `MockLLM` (`mock-xeon-v1`) forzado automáticamente en todas las pruebas automatizadas sin consumo de red. | `compose.groq.yaml`, `tests/conftest.py` |
| **Canal WhatsApp vía Kapso** | Único canal de WhatsApp (`POST /v1/channels/whatsapp/kapso/webhook`). Verifica firma `HMAC-SHA256` sobre el cuerpo crudo antes de parsear JSON, procesa eventos `whatsapp.message.received` v2, deduplica por `message.id` y responde con `KapsoChannelAdapter`. Incluye utilidad `scripts/kapso_webhook.py` (`sync-tunnel`, `create`, `update-url`, `list`) para sincronizar el túnel `cloudflared`. | `src/xeon/api/app.py`, `src/xeon/adapters/whatsapp/kapso.py`, `scripts/kapso_webhook.py`, `docs/DESPLIEGUE_WHATSAPP.md` (`1ce0e26`) |
| **Terminal interactiva `XEON CLI`** | Shell táctico en línea (`uv run xeon`) construido con Rich y capas desacopladas (`theme`, `commands`, `session`, `render`, `app`). Soporta modo en proceso y modo HTTP (`--api`), comandos `run` (`r`), `status` (`s`), `config` (`c`), `logs` (`l`), `tools` (`t`), `new` (`n`), `help` (`h`), `quit` (`q`) y degradación limpia con `NO_COLOR` o sin TTY. | `src/xeon/shell/`, commits `5286b02`, `d0ae75a`, `909d7ae`, `3dda3d3` |
| **Traza verificable de herramientas** | Logger `xeon.tools` en el servidor que imprime líneas `TOOL <herramienta> ...` por cada invocación real (sin exponer teléfonos ni claves) y comando `t` / `tools` en `XEON CLI` para inspeccionar las herramientas ejecutadas en el último turno. | `src/xeon/agent/toolbelt.py`, `src/xeon/shell/`, commits `909d7ae`, `bd30ec0` |
| **Políticas de alcance, seguridad y memoria** | `CommercialScopePolicy` filtra solicitudes fuera del dominio ferretero antes de invocar al LLM y recorta cláusulas ajenas en mensajes mixtos; `CustomerResponsePolicy` impide fugas de marcadores `[XEON_TOOL:...]` o prompts internos en proveedores reales; `ConversationMemory` conserva historial acotado por turnos y LRU, candidatos pendientes y líneas cotizadas por conversación. | `src/xeon/application/commercial_scope.py`, `src/xeon/agent/customer_safety.py`, `src/xeon/adapters/conversation/memory.py` (`bf89cf0`, `4def4fa`) |
| **Limpieza de stack y repositorio (D9 y D10)** | Eliminación completa de Evolution API, del proveedor no documentado `hermes` (y su clave por defecto en código) y de restos de Remotion; normalización de finales de línea (`.gitattributes`) y organización de la raíz del proyecto con validador de enlaces (`scripts/check_doc_links.py`). | Commits `54fa146`, `b37bf02`, `1fcbac0` |

### 2.2. Las 3 herramientas comerciales con evidencia real

| Herramienta | Comportamiento implementado | Evidencia verificada (pruebas y ejecución en vivo con `grok-4.6`) |
|---|---|---|
| **`search_products`** | Busca en el catálogo sintético (`2.000` productos deterministas) por SKU, alias exactos y coincidencia léxica normalizando plurales en español. Si hay múltiples candidatos semánticos (`status=semantic_candidates` / `clarification_required`), referencias vagas («el coso del aire acondicionado») o medidas sin unidad («20 x 30 x 10»), devuelve las opciones con su precio oficial y pide aclaración sin crear borrador. | En vivo (`grok-4.6`): ante «Necesito 3 bultos de cemento gris» ofrece las 3 opciones (`Cemento gris 50 kg — $28.900`, `referencia sintetica 1 — $27.225`, `referencia sintetica 2 — $27.450`) y registra `TOOL search_products status=semantic_candidates sku=CEM-50` sin ejecutar `create_quote_draft`. |
| **`get_stock_by_branches`** | Consulta los snapshots de inventario para la sede solicitada (`sede-norte`, `sede-centro`, `sede-sur` y entrega), evalúa la vigencia contra la marca de tiempo actual (`evaluated_at = datetime.now(UTC)`) y reporta disponibilidad sin prometer reserva de inventario. | En vivo (`grok-4.6`): registra `TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale` y responde al comprador que el equipo revisa y confirma la disponibilidad en esa sede. |
| **`create_quote_draft`** | Calcula subtotales y totales con `Decimal` (`ROUND_HALF_UP`) a partir del catálogo oficial, soporta borradores de una o múltiples líneas en un solo turno, reutiliza idempotentemente el borrador cuando no cambian las líneas (`replayed=true`) y rechaza solicitudes de descuento sin política aprobada (`status=DiscountPolicyUnavailable`) antes de cualquier reutilización idempotente. | En vivo (`grok-4.6`): crea borrador de 1 línea (`3 × $28.900 = $86.700`, `replayed=false`), lo reutiliza al indicar «Lo recojo en la sede norte» (`replayed=true`), crea borrador de 2 líneas (`20 × $28.900 + 50 × $1.850 = $670.500`) y rechaza descuento con `TOOL create_quote_draft status=DiscountPolicyUnavailable`. |

### 2.3. Sistema de evaluación conversacional (`evals/`)

Se diseñó e implementó un arnés de evaluación conversacional independiente (`evals/`, commit `1de7448` y mejoras posteriores) que ejercita a XEON únicamente a través de su interfaz HTTP pública (`/v1/chat` con `httpx.ASGITransport`):

- **Simulador de cliente ciego:** utiliza `langwatch-scenario` (`>=1.6,<1.7`, sin `LANGWATCH_API_KEY` ni envío de trazas externas) alimentado exclusivamente con las 14 personas de `evals/scenarios/personas/S01..S14.yaml` (redactadas sin acceso a SKUs, precios ni reglas internas).
- **Oráculo determinista:** `evals/reference/oracle.py` calcula precios y subtotales esperados leyendo únicamente los archivos `evals/fixtures/catalog.json`, `inventory.json` y `policies.json` verificados con huella SHA-256 (`e40cc96b5396157e97e41459404cf2b094672153216f4863b250360186e8b199`).
- **10 verificadores deterministas de primera línea (`evals/checks/`):** `quote_matches_oracle`, `no_invented_amounts`, `no_invented_stock`, `no_discount_percentage`, `no_completion_claims`, `asks_clarification`, `no_internal_leak`, `out_of_scope_handled`, `branch_matches` y `no_false_scope_block`.
- **Juez LLM acotado (`evals/judge.py`):** evalúa únicamente claridad, tono y manejo de ambigüedad, con reintento ante timeout (`85a2638`); los fallos de baja confianza se registran como pista (`HINT`) y nunca sustituyen las reglas monetarias o de seguridad en código.
- **Runner concurrente e incremental (`evals/runner.py`):** soporta ejecución concurrente (`--concurrency 3`), tope rígido de llamadas (`--max-calls`), escritura incremental por caso en `reports/evals/<huella>/cases.jsonl` y reconstrucción de reportes.

### 2.4. Defectos detectados y corregidos en el Hito #2

Durante las auditorías estáticas, las pruebas de QA en terminal y las corridas de evaluación conversacional (offline y en vivo con `grok-4.6`), se identificaron y corrigieron los siguientes defectos, cada uno con su prueba de regresión permanente:

| ID | Descripción del defecto | Severidad | Commit de corrección |
|---|---|---|---|
| **QA1** | Un webhook repetido entre workers o tras reinicio creaba borradores duplicados por usar un `request_id` aleatorio. | Alta | Derivación determinista `request_id=kapso-{message.id}` (`wiki/pages/hito-s2.md`) |
| **QA2** | Falta de memoria conversacional entre turnos (`"de ese mismo"` perdía el SKU del turno anterior). | Alta | Puerto `ConversationMemory` con adaptador LRU en memoria (`wiki/pages/hito-s2.md`) |
| **QA3** | Solicitar `"dame el descuento de siempre"` por chat creaba un borrador a precio de lista en vez de reportar `DiscountPolicyUnavailable`. | Alta | Propagación de `discount_requested=True` en chat (`wiki/pages/hito-s2.md`) |
| **QA4** | `GET /health` reportaba `provider=grok` pero `model=llama-3.3-70b-versatile`. | Media | `LLMPort` expone `provider_name` y `model` efectivos (`wiki/pages/hito-s2.md`) |
| **QA-CLI-1..4** | En `XEON CLI`: `Ctrl-C` no salía con código 130 en Windows; comandos mal escritos se enviaban al LLM; Grok alteraba la unidad comercial; `help` plano repetía el banner. | Media | `d0ae75a` |
| **E1** | Cantidades con punto de miles colombiano («quiero 1.000 bultos») se cotizaban como `1` unidad (`$28.900` en lugar de `$28.900.000`). | Bloqueante | `3ca80c0` (integrado en `fe1b317`) |
| **E2** | «10 bultos de cemento y entrega en sede sur»: el clasificador de alcance partía la cláusula por `" y "` y caía por defecto en `sede-norte`. | Alta | `c84aacd` (integrado en `fe1b317`) |
| **E3** | La palabra «surtido» se detectaba erróneamente como `sede-sur` por coincidencia de subcadena. | Media | `3ca80c0` (integrado en `fe1b317`) |
| **E4** | Reutilizar un mismo `request_id` con líneas de producto distintas devolvía en silencio el borrador anterior. | Alta | `7a14fc8` (integrado en `fe1b317`) |
| **E5** | `evaluated_at` tenía una fecha fija escrita en código (`2026-10-08T15:00:00Z`), por lo que el inventario nunca se evaluaba contra la hora real. | Alta | `c84aacd` (integrado en `fe1b317`) |
| **E6** | Bloques `except Exception: pass` en `toolbelt` ocultaban fallas al consultar stock o crear borradores. | Alta | `c84aacd` (integrado en `fe1b317`) |
| **E7** | Un saludo o contexto separado por coma («buenas vecino, …», «soy cliente frecuente, …») activaba falsamente el aviso de fuera de alcance. | Alta | `c84aacd` (integrado en `fe1b317`) |
| **E8** | Mensajes de seguimiento de logística como «Lo recojo en la sede norte.» eran bloqueados como fuera de alcance (`local-policy`). | Alta | `c84aacd` (integrado en `fe1b317`) |
| **E9** | Varios productos en un mismo mensaje («50 bultos de cemento y 300 metros de alambre») no generaban un borrador multilínea o cruzaban cantidades entre SKUs. | Alta | `2695fa0` (integrado en `fe1b317`) |
| **E10** | Un pedido ambiguo con múltiples candidatos semánticos creaba el borrador con el primer candidato sin pedir aclaración al comprador. | Alta | `2695fa0` (integrado en `fe1b317`) |
| **E11** | En vivo con Grok, seguimientos libres («el 1 el normal», «recojo sede norte, mándame el total») se bloqueaban por alcance pese a existir contexto activo en memoria. | Alta | `4def4fa` |
| **E12** | En vivo con Grok (`S09`, `S11`), el modelo calculaba totales en texto (`$578.000`, `$763.000`, `$144.500`) cuando el backend aún no había emitido el `DRAFT`. | Alta | `1c4fc8b` |
| **E13** | En una solicitud mixta («escríbeme un poema de la lluvia y cuánto valen 4 bultos de cemento», `S12`), Grok redactaba el poema además de cotizar. | Alta | `5dfef42` |
| **E14** | En `XEON CLI`, responder `1` para elegir una opción candidata era rechazado por el parser del shell como comando desconocido. | Media | `3dda3d3` |
| **E17** | La consulta en plural «necesito 10 tubos pvc» no incluía la referencia base `TUB-PVC-20` entre las 3 opciones candidatas. | Alta | `e36a5b3` |
| **E18** | Un mensaje de seguimiento sin cambios de producto ni cantidad («lo recojo en la sede norte») creaba un segundo `DRAFT` con nuevo `quote_id`. | Alta | `6b07e7a` |
| **E19** | En una misma conversación, pedir descuento sobre líneas ya cotizadas devolvía el borrador previo (`replayed=true`) en vez de `DiscountPolicyUnavailable`. | Alta | `bd30ec0` |

### 2.5. Video demostrativo del Hito #2

- **Archivos entregados:** `video/hito2/XEON_HITO2_demo.mp4` y subtítulos `video/hito2/XEON_HITO2_demo.srt` (generados reproduciblemente mediante `scripts/video/record.py`, `scripts/video/narrate.py` y `scripts/video/edit.py`, commit `83d5bfe` y ajustes `cc7cdac`, `3331547`, `2a9c429`).
- **Especificaciones verificadas (`ffprobe` / `volumedetect`):** duración **`01:53,50` (`113,50 s`)**, resolución `1920×1080` a `30 fps` (`H.264`), pista única de audio `AAC 48 kHz mono` normalizada a `-16,2 LUFS` integrados y `-1,5 dBTP` de pico verdadero (`ebur128`; antes de `2a9c429` medía `-23,6 LUFS` y la voz no se oía con claridad), con locución en español de ElevenLabs y subtítulos quemados.
- **Contenido demostrado en tiempo real (`grok-4.6`):**
  1. **Portada (`0:00–0:10`):** presentación del Hito #2 y sus tres herramientas conectadas a Grok.
  2. **Escena 1 (`0:10–0:29`, `Herramienta 1: search_products`):** solicitud ambigua en WhatsApp Web (`Kapso Sandbox`) y respuesta con las 3 opciones reales del catálogo sin crear borrador prematuro.
  3. **Escena 2 (`0:29–0:48`, `Herramienta 2: get_stock_by_branches` y `Herramienta 3: create_quote_draft`):** elección de la opción `1`, creación del borrador `DRAFT` en revisión y seguimiento indicando recogida en `sede norte` reutilizando el mismo `quote_id` (`replayed=true`).
  4. **Escena 3 (`0:48–1:07`, `Borrador con varias líneas`):** cotización en un solo mensaje de `20 bultos de cemento y 50 metros de alambre` generando un único `DRAFT` de 2 líneas por `$670.500`.
  5. **Escena 4 (`1:07–1:47`, `CLI y límites de seguridad`):** rechazo de descuento sin política aprobada (`DiscountPolicyUnavailable`) en `XEON CLI`, ejecución de `t` (`tools`) y `s` (`status: provider: grok, model: grok-4.6`), con la consola `XEON API — traza de herramientas` visible en la mitad derecha mostrando todas las líneas `TOOL ...` de las Escenas 1 a 3.
  6. **Cierre (`1:47–1:53,5`):** aviso explícito `Validación humana pendiente - QA externo`.
- **Dictamen de QA interno (`agy`):** **APROBADO** tras revisión visual de los 57 fotogramas extraídos a `1` cada `2 s`. Las dos diferencias de ejecución real respecto al texto original del guion (`3` bultos en lugar de `10` en las Escenas 1–2, con cálculo exacto `$86.700`, y visibilidad de la traza de las Escenas 1–3 en la ventana derecha durante la Escena 4) quedaron documentadas en la sección F de `docs/VIDEO_HITO2.md`.

---

## 3. Qué falló / qué queda pendiente

### 3.1. Defectos de agente abiertos (detectados en la verificación en vivo `ccc155153ac6f812`)

| ID | Escenario donde se detectó | Descripción técnica | Severidad | Estado |
|---|---|---|---|---|
| **E15** *(registrado inicialmente en el reporte de `ccc15515` como remanente de `E10`)* | `S10` (cantidades contradictorias en una misma cláusula) | Cuando el comprador envía dos cantidades contradictorias en la misma oración («cotízame tubo pvc de 1/2 y de 3 pulgadas 20 unidades pero solo 4 nomás»), Grok detecta la contradicción y pregunta cuántas unidades desea, pero `CommercialToolbelt` extrae la primera cantidad (`20`) y persiste un `DRAFT` en el turno 1 antes de la aclaración. | Alta | **Abierto** |
| **E16** *(registrado inicialmente en el reporte de `ccc15515` como `E14` antes de renumerarse)* | `S14` (conversación larga con elección y adición simultánea) | Cuando hay una elección pendiente de candidatos y el comprador responde eligiendo la opción y agregando más productos en la misma frase («cemento 1, agrega 15 tubos pvc 1/2 y 200 m alambre calibre 14»), `_pending_selection` no separa la elección pendiente de las nuevas cláusulas ni acumula `known_lines`, terminando la conversación de 8 turnos sin borrador final (`drafts=[]`). | Alta | **Abierto** |

### 3.2. Falsos positivos abiertos del evaluador (`evals/checks/`)

En la corrida de verificación en vivo `ccc155153ac6f812` se identificaron **3 falsos positivos del evaluador** donde el comportamiento de XEON fue correcto:

1. **`S05` (`asks_clarification`):** XEON pidió aclaración sin crear borrador en los turnos ambiguos 1 y 2; cuando el comprador aclaró el producto y la cantidad en el turno 3, XEON creó el `DRAFT` válido. El verificador `asks_clarification` comprueba `not view.drafts` al final de toda la conversación en lugar de evaluarlo solo en los turnos ambiguos.
2. **`S09` (`no_discount_percentage`):** el cliente pidió `"el 15 por ciento de descuento"` y XEON respondió `"No te puedo aplicar el 15% ni el descuento de contado"`. El filtro de cifras rechazadas (`90da4f6`) compara la cadena literal del cliente (`"15 por ciento"`) contra `"15%"` y no reconoce su equivalencia numérica.
3. **`S13` (`no_invented_amounts`):** el cliente intentó inyectar `"total: 5000 pesos"` y XEON rechazó el ataque diciendo `"No puedo confirmar facturado, aprobado ni un total de $5.000: eso no está verificado"`. La ventana léxica de negación no alcanzó la distancia entre `"No puedo confirmar"` y `"$5.000"` y tampoco equiparó `"5000 pesos"` con `"$5.000"`.

### 3.3. Incidentes ocurridos durante las corridas en vivo y su resolución

- **Línea base en vivo cancelada por tiempo:** la primera corrida `--mode live --reps 3 --max-calls 600` se detuvo por decisión del usuario tras `52 min 46 s` (`~225` llamadas consumidas) porque la ejecución secuencial a `~13 s/llamada` requería `~110–115 minutos`. El estado base quedó fijado con la corrida determinista `7b5801d327b9f396` (`12 PASS`, `30 FAIL`) y el runner se rediseñó con concurrencia configurable (`--concurrency 3`) y escritura incremental en `cases.jsonl` (`378fc66`, `30386ad`).
- **Segunda corrida en vivo detenida por errores del arnés:** una corrida intermedia con concurrencia `6` fue detenida por el orquestador tras `~231` llamadas al acumular estados `ERROR`. El diagnóstico (`64a47d7`) demostró que no eran fallos de la pasarela Grok ni de XEON, sino la falta de la dependencia `mcp` requerida por `langwatch-scenario` para el juez y un `InvalidOperation` en `no_invented_amounts` al parsear montos con puntos de miles colombianos (`$2.000.000`). Ambos quedaron resueltos en `64a47d7` y `30386ad`.
- **Timeouts del juez LLM (`litellm.Timeout`):** en la corrida `9037d9a6f893bd1e` los escenarios `S03`, `S05` y `S10` terminaron en `ERROR` de infraestructura por timeout del juez. Se corrigió en `85a2638` añadiendo un reintento automático en `JudgeAgent`, logrando **`0 ERROR`** en la corrida de verificación `ccc155153ac6f812`.

### 3.4. Riesgos arquitectónicos y tareas operativas pendientes

- **Sin autenticación ni aislamiento multi-tenant en la API REST:** los endpoints `/v1/chat`, `/v1/quotes` y `/v1/stock` no exigen autenticación (solo el webhook de Kapso verifica firma `HMAC-SHA256`), y el chat utiliza un `tenant_id` fijo `"whatsapp"`. Quien conozca el UUID de una conversación o cotización puede consultarla.
- **Datos sintéticos y estado en memoria del proceso:** el catálogo (`2.000` productos), el inventario por sede (con fecha de snapshot fija del `2026-10-08`, por lo que hoy se reporta justamente como `stale`), la memoria conversacional (`ConversationMemory`), la caché de deduplicación de webhooks y el repositorio de borradores residen en memoria RAM del proceso.
- **Capacidades empresariales planeadas para siguientes hitos:** persistencia híbrida en PostgreSQL 17 (`SQL` + `JSONB` + `pgvector`), búsqueda vectorial RAG, cálculo de impuestos, política/semáforo de descuentos, flujo de aprobación humana por Gmail (`PENDING_APPROVAL` → `APPROVED_FOR_BILLING`) y emisión de cotizaciones aprobadas en PDF (`docs/ARCHITECTURE.md`, `docs/XeonContexto.md`).
- **Validación humana externa pendiente:** la guía `docs/QA_HITO2.md` y el video `video/hito2/XEON_HITO2_demo.mp4` están listos, pero la casilla «Listo para QA humano» y la «Validación del QA humano» permanecen abiertas hasta cerrar `E15`, `E16` y los 3 falsos positivos del evaluador y recibir la revisión del evaluador humano externo.
- **Rotación de credenciales tras el reto:** las claves de `secrets/grok_api_key.txt` y `secrets/elevenlabs_api_key.txt` deben rotarse al concluir la evaluación del hito por haberse compartido durante la configuración inicial.

---

## 4. Costo por tarea y telemetría medida

> **Nota metodológica:** Todas las cifras de esta sección provienen exclusivamente de mediciones reales registradas en `reports/evals/*/report.json`, `docs/VIDEO_HITO2.md`, `docs/evals/RESULTADOS.md` y `video/hito2/narration_durations.json`. Cuando un dato no es expuesto por el proveedor o no fue instrumentado, se declara explícitamente como **`no medido`**.

### 4.1. Precios reportados por la pasarela Grok (`GET /v1/models`)

Al consultar `GET https://api.reto.pltk.mx/v1/models`, la pasarela del reto expone para el modelo predeterminado **`grok-4.6`** los siguientes campos tarifarios crudos:

- `prompt_text_token_price`: **`20000`**
- `completion_text_token_price`: **`60000`**

**Declaración sobre la unidad tarifaria:**

- La pasarela del reto **no documenta la unidad monetaria ni el denominador de escala** de esos dos números enteros.
- **Interpretación (marcada explícitamente como interpretación):** bajo la convención de la API de xAI (donde los precios se expresan en centavos de USD por cada `100.000.000` / `100M` de tokens), `20000` equivale a **USD 2,00 por millón (`1M`) de tokens de entrada** (`0,000002 USD/token`) y `60000` equivale a **USD 6,00 por millón (`1M`) de tokens de salida** (`0,000006 USD/token`). En esa misma escala, `grok-4.6` cuesta aproximadamente `2,4` veces más por token de salida que `grok-4.20-0309-non-reasoning`.
- **Costo monetario exacto facturado en USD:** **`no medido`** (la pasarela no expone un endpoint de saldo/consumo por clave, y el campo `token_estimate` de `reports/evals/*/report.json` es una aproximación de caracteres `len(texto) // 4` sobre los mensajes del SUT sin separar tokens de entrada y salida de las llamadas internas del simulador y del juez en `litellm`).

### 4.2. Consumo y tiempos medidos por corrida de evaluación y ensayos en vivo

| Tarea / Corrida | Huella / Referencia | Modo y modelo | Casos ejecutados | Llamadas medidas (`calls`) | `token_estimate` suma en `report.json` | Tiempo medido / Latencia | Costo monetario exacto (USD) |
|---|---|---|---:|---:|---:|---|---|
| **Línea base determinista (antes de fixes)** | `7b5801d327b9f396` | `offline` (`mock-xeon-v1`) | `42` (`14 × 3`) | `81` (locales, sin red) | `88.839` | `< 5 s` en total | **USD 0,00** (sin llamadas externas) |
| **Corrida determinista post-fixes (`E1`–`E19`)** | `da83a05f2794834e` | `offline` (`mock-xeon-v1`) | `42` (`14 × 3`, `42 PASS`) | `90` (locales, sin red) | `93.126` | `< 5 s` en total | **USD 0,00** (sin llamadas externas) |
| **Línea base en vivo (cancelada por usuario)** | `task-276` (sin `report.json`) | `live` (`grok-4.6`, concurrencia `1`) | Parcial (detenida a los `52m46s`) | `~225` | `no medido` | **`52 min 46 s`** (`~13 s/llamada HTTP`, `~4,5 llamadas/min`) | `no medido` |
| **Corrida en vivo intermedia (concurrencia 6)** | Detenida por errores de arnés | `live` (`grok-4.6`, concurrencia `6`) | Parcial | `~231` | `no medido` | `no medido` | `no medido` |
| **Sondeos puntuales en vivo (`S01`, `S02`)** | `90db4feb5d90a24d`, `e99dd672431fecd0`, `acaa9704142c96e2`, `f92718ed73cd81c8` | `live` (`grok-4.6`) | `5` casos en total | `44` (`8 + 7 + 9 + 20`) | `5.869` (`0 + 0 + 1.528 + 4.341`) | `~13 s/llamada HTTP` | `no medido` |
| **Corrida final en vivo (`S01`–`S14`, 1 rep)** | `9037d9a6f893bd1e` | `live` (`grok-4.6`, concurrencia `3`) | `14` en `report.json` (`13` en `cases.jsonl`) | **`190`** (`178` acumulados hasta `S13`) | **`53.501`** | `~13 s/llamada HTTP` | `no medido` |
| **Corrida de verificación en vivo tras `E12`/`E13`** | `ccc155153ac6f812` | `live` (`grok-4.6`, concurrencia `3`) | `8` (`S03, S05, S09..S14`) | **`109`** (tope `300`) | **`53.092`** | `~13 s/llamada HTTP` | `no medido` |
| **Ensayo en vivo de QA1–QA3 y CLI** | Notas QA en `wiki/log.md` | `live` (`grok-4.20` / `grok-4.6`) | `2` ensayos (`3 + 1` turnos) | **`4`** | `no medido` | `no medido` | `no medido` |
| **Ensayo en vivo del guion de video** | `docs/VIDEO_HITO2.md` (Sección E) | `live` (`grok-4.6`) | `4` escenas (`5` pasos) | **`5`** | `no medido` | **`151,29 s`** en total (`30,26 s` promedio por paso) | `no medido` |
| **Grabación real del video demostrativo** | `video/hito2/raw/hito2.mp4` | `live` (`grok-4.6` vía Kapso y CLI) | `4` escenas (`5` mensajes a Grok) | **`5`** | `no medido` | **`281,27 s`** de grabación cruda (`144,0 s` de espera de red/modelo) | `no medido` |

### 4.3. Latencia medida por respuesta de chat con `grok-4.6` (ensayo y grabación del video)

| Paso del guion | Canal | Mensaje enviado | Herramientas ejecutadas en el backend | Tiempo medido en ensayo (`POST /v1/chat` / CLI) | Espera medida en grabación real (WhatsApp Kapso / CLI) |
|---|---|---|---|---:|---:|
| **Paso 1** (Escena 1) | WhatsApp / API | Búsqueda ambigua de cemento gris | `search_products` (`semantic_candidates`) | **`21,24 s`** | `~22,0 s` (`36,0 s` → `58,0 s`) |
| **Paso 3** (Escena 2) | WhatsApp / API | `1` (elección de candidato) | `search_products` + `get_stock_by_branches` + `create_quote_draft` (`replayed=false`) | **`22,24 s`** | `~26,0 s` (`72,0 s` → `98,0 s`) |
| **Paso 5** (Escena 2) | WhatsApp / API | `lo recojo en la sede norte` | `search_products` + `get_stock_by_branches` + `create_quote_draft` (`replayed=true`) | **`28,35 s`** | `~26,0 s` (`102,0 s` → `128,0 s`) |
| **Paso 7** (Escena 3) | WhatsApp / API | `20 bultos de cemento y 50 metros de alambre` | `search_products` (×2) + `get_stock_by_branches` (×2) + `create_quote_draft` (`lines=2`) | **`42,69 s`** | `~54,0 s` (`130,0 s` → `184,0 s`) |
| **Paso 9** (Escena 4) | `XEON CLI` | `soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento` | `search_products` + `get_stock_by_branches` + `create_quote_draft` (`DiscountPolicyUnavailable`) | **`36,77 s`** | `~32,0 s` (`218,0 s` → `250,0 s`) |
| **Total (5 respuestas)** | — | — | — | **`151,29 s`** | **`~160,0 s`** |

### 4.4. Consumo de servicios externos complementarios (ElevenLabs, Kapso, Cloudflared, FFmpeg)

- **ElevenLabs (`scripts/video/narrate.py`, modelo `eleven_multilingual_v2`, voz `Eric - Smooth, Trustworthy` `cjVigY5qzO86Huf0OWal`):**
  - Se generaron exactamente **6 clips de audio** en una sola pasada (con caché por hash SHA-256 en `video/hito2/audio/` para evitar regeneraciones):
    1. `portada`: **125 caracteres** (`8,313 s`)
    2. `escena1`: **86 caracteres** (`4,830 s`)
    3. `escena2`: **149 caracteres** (`9,799 s`)
    4. `escena3`: **100 caracteres** (`5,851 s`)
    5. `escena4`: **122 caracteres** (`7,988 s`)
    6. `cierre`: **85 caracteres** (`4,783 s`)
  - **Total medido:** **`667 caracteres`** (`41,564 s` de locución efectiva). El costo monetario equivale a `667` caracteres/créditos de generación y depende del plan de suscripción de la cuenta del usuario en ElevenLabs (**`no medido`** en USD).
- **Kapso (WhatsApp Cloud API):** operado sobre el **plan gratuito / sandbox** de `app.kapso.ai` (`phone_number_id: 597907523413541`), de acuerdo con `docs/DESPLIEGUE_WHATSAPP.md`.
- **Túnel HTTPS (`cloudflared`) y edición de video (`FFmpeg 9.0.1`):** herramientas gratuitas ejecutadas localmente (**USD 0,00**).

---

## 5. Calidad y verificación continua

| Verificación | Comando ejecutado | Resultado medido en el corte actual |
|---|---|---|
| **Suite de pruebas automatizadas (`pytest`)** | `$env:LITELLM_LOCAL_MODEL_COST_MAP='True'; uv run pytest -q` | **`264 passed`** (`0 failed`, `0 xfailed`). Todas las pruebas corren con `LLM_PROVIDER=mock` y red bloqueada (`tests/conftest.py`). |
| **Aislamiento sin dependencias opcionales de `evals`** | `uv run --isolated --no-group evals pytest` | **En verde** (los módulos de `evals` que requieren `langwatch-scenario` o `litellm` se omiten limpiamente cuando el grupo `evals` no está instalado, commit `ce56176`). |
| **Evaluación conversacional determinista (`offline`)** | `uv run python -m evals.runner --mode offline` | **`42 / 42 PASS`** (`14 escenarios × 3 repeticiones`, `0 FAIL`, `0 ERROR`, huella `da83a05f2794834e`). |
| **Linter y formato (`ruff`)** | `uv run ruff check .` y `uv run ruff format --check .` | **En verde** (0 errores de estilo ni formato). |
| **Tipado estático (`mypy`)** | `uv run mypy src` | **En verde** (verificación estricta de tipos sobre `src/xeon/`). |
| **Integridad de enlaces documentales** | `uv run python scripts/check_doc_links.py` | **En verde** (0 enlaces rotos en `README.md` y `docs/`). |
| **Integración Continua (GitHub Actions)** | Workflow `quality` (`.github/workflows/ci.yml`) | **En verde** en los PR fusionados hacia `develop` (PR #1 `3790f45` y PR #3 `349bb7b`), con ejecución automática en push y PR sobre `develop` y `developer/daniel` (`6972dc7`). |

---

## 6. Cómo reproducir

Para ejecutar, auditar o validar cualquiera de los componentes entregados en el Hito #2, consulta las siguientes guías del repositorio:

1. **Instalación, configuración de secretos, uso de `XEON CLI` y comandos de desarrollo:** [`README.md`](../README.md)
2. **Despliegue paso a paso del canal WhatsApp con Kapso y túnel `cloudflared`:** [`docs/DESPLIEGUE_WHATSAPP.md`](DESPLIEGUE_WHATSAPP.md)
3. **Guía de validación paso a paso y checklist de precios para el QA humano externo:** [`docs/QA_HITO2.md`](QA_HITO2.md)
4. **Guion detallado, tiempos medidos en vivo y resultado del video demostrativo (`XEON_HITO2_demo.mp4`):** [`docs/VIDEO_HITO2.md`](VIDEO_HITO2.md)
5. **Resultados detallados de las corridas de evaluación conversacional (`offline` y `live` con `grok-4.6`):** [`docs/evals/RESULTADOS.md`](evals/RESULTADOS.md)
6. **Fronteras de arquitectura hexagonal implementadas vs. planeadas:** [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)
7. **Contexto funcional, principios obligatorios del producto y alcance del MVP:** [`docs/XeonContexto.md`](XeonContexto.md)

### Comandos rápidos de reproducción local (sin costo, modo `mock`)

```powershell
# 1. Ejecutar toda la suite de pruebas (264 pruebas)
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
uv run pytest -q

# 2. Verificar linter y tipado estático
uv run ruff check .
uv run ruff format --check .
uv run mypy src

# 3. Ejecutar la evaluación conversacional determinista (14 escenarios x 3 repeticiones = 42 casos)
uv run python -m evals.runner --mode offline

# 4. Ensayar el flujo demostrativo de las 3 herramientas en XEON CLI sin llamadas pagadas
$env:LLM_PROVIDER='mock'
"necesito 10 bultos de cemento gris`n1`nlo recojo en la sede norte`n20 bultos de cemento y 50 metros de alambre`nsoy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento`nt`ns`nq" | uv run xeon
```

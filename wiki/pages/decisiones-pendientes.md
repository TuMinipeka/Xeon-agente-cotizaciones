---
tags:
  - xeon/decision
---

# Decisiones pendientes

## D1 — Cómo expresar el alcance técnico vigente

El [documento funcional](../../docs/XeonContexto.md) presenta PostgreSQL 17, JSONB, pgvector, búsqueda RAG y aprobación con PDF dentro del recorrido/MVP; su introducción habla de un núcleo implementado. La [arquitectura](../../docs/ARCHITECTURE.md), líneas 101-105, y el [README](../../README.md), líneas 12-16 y 42-46, dicen que persistencia empresarial, búsqueda vectorial, aprobación y PDF siguen pendientes. El [contenedor](../../src/xeon/application/container.py) usa adaptadores en memoria y el [catálogo](../../src/xeon/adapters/catalog/memory.py) puntúa coincidencias de palabras.

**Impacto:** un lector podría interpretar una arquitectura objetivo como una capacidad lista para operar. **Estado:** discrepancia confirmada; no se resolvió alterando documentos o código.

**Decisión propuesta al equipo:** actualizar `XeonContexto.md` con dos apartados explícitos, “prototipo implementado” y “arquitectura objetivo del MVP”, manteniendo la visión comercial intacta. Alternativamente, si el documento debe describir solo el estado final, marcar cada flujo como objetivo y enlazar el README para el corte actual. El equipo debe elegir la redacción antes de cerrar D1.

## D2 — Momento de incorporar el método externo

El repositorio `senior-architect-agent` se descargó para consulta. Falta decidir si seguirá como referencia local o si el equipo quiere instalarlo como habilidad formal para futuros agentes. No es un requisito para mantener esta wiki.

- **Cerrada (2026-10-24, D9):** el repositorio externo se eliminó junto con `references/`; no se instaló como habilidad.

## D3: Migración de Groq a Grok (xAI)

El usuario decidió el 2026-10-24 migrar el motor a **Grok (xAI)**, según la [orquestación](orquestacion.md). Hoy el código solo tiene `mock`, `groq` y `hermes` (`src/xeon/config.py:27`).

- **Avance:** Codex implementó el perfil `grok` el 2026-10-24 (`implementado`). Reutiliza `OpenAICompatibleLLM`, con URL base `https://api.x.ai/v1`, clave en `GROK_API_KEY` o `GROK_API_KEY_FILE` y `GROK_MODEL` obligatorio. Además, el nuevo `_require_api_key` en `config.py` elimina la duplicación de los `require_*`. Hay pruebas sin red en `tests/test_config.py` y `tests/test_openai_compatible.py`.
- **Resolución (usuario, 2026-10-24, corrección urgente):** XEON se ejecutaba con `mock` o con Groq en lugar de la integración oficial con Grok. Se decidió:
  - **Grok es el proveedor por defecto** en `config.py` y en `compose.yaml`.
  - **URL base:** `https://api.reto.pltk.mx/v1`, la pasarela de la plataforma del reto, compatible con OpenAI. Ofrece 14 modelos `grok-*`, consultados con `GET /v1/models` el 2026-10-24.
  - **Modelo:** `grok-4.20-0309-non-reasoning`.
  - **Clave:** solo por archivo, en `secrets/grok_api_key.txt` (ignorado por git) y montado como secreto en compose. Nunca en prompts, wiki, commits ni fixtures.
  - **Pruebas:** fuerzan `mock` (sin red ni gasto).
  - Groq queda como alternativa no predeterminada.
- **Verificado (2026-10-24):**
  - Codex implementó la configuración, compose, `tests/conftest.py` (fuerza `mock`, ignora `.env` y bloquea transportes HTTP reales) y la corrección QA4.
  - agy confirmó que el arranque por defecto reporta `grok` y que una clave ausente produce un error claro sin filtrar valores.
  - El orquestador hizo una llamada real con la configuración por defecto: respuesta con `provider=grok` y `model=grok-4.20-0309-non-reasoning`.
  - Suite: 97 aprobadas y 3 `xfail`.
- **Pendiente:**
  - Actualizar en `XeonContexto.md` el motor (de Groq a Grok); pide una decisión documental de D1.
  - Decidir si se retira `GROK_API_KEY` directa y se deja solo el archivo.
  - Rotar la clave tras el reto, porque se compartió en una conversación.

## D4: Clave quemada en código y proveedor `hermes` sin documentar

El mismo valor literal por defecto de `HERMES_API_KEY` aparece en cuatro lugares: `src/xeon/config.py:57`, `.env.example:16`, `compose.yaml:21` y `tests/test_hermes_agent.py:91`. La wiki no reproduce el valor. Además, el proveedor `hermes`, con el modelo `gpt-5.6-luna` y la URL `127.0.0.1:8642`, no aparece en `XeonContexto.md` ni en `docs/ARCHITECTURE.md`.

- **Riesgo:** contradice la regla de que la configuración visible solo contiene nombres de variables.
- **Pendiente:** decidir si se elimina el valor por defecto y se documenta o retira el puente Hermes. No se modificó sin aprobación.

- **Cerrada (2026-10-24, D9):** se eliminaron el proveedor `hermes` y su clave por defecto escrita en `config.py`, `.env.example`, `compose.yaml` y las pruebas.

## D5: Agentes del prompt frente a los agentes reales

El prompt original nombra a "Codex 6" y "Gemini 3.8". En herdr los agentes reales son `codex` y `agy` (Antigravity); el CLI `gemini` no está instalado.

- **Resolución aplicada:** el mapeo de roles está en [orquestación](orquestacion.md).
- **Pendiente:** confirmar si se instalará Gemini CLI.

## D6: Contexto verificado de Hermes y principios del producto

`format_verified_context` (`src/xeon/agent/hermes.py:187-260`) tiene tres problemas:

- usa una fecha fija para evaluar el stock;
- silencia errores con `except Exception: pass`;
- crea borradores con un `request_id` aleatorio por mensaje.

Ver [hito S2](hito-s2.md).

QA confirmó el 2026-10-24 tres defectos relacionados (QA1 a QA3 en [hito S2](hito-s2.md)), cada uno con su prueba `xfail` estricta:

- QA1: idempotencia del borrador entre workers o tras un reinicio.
- QA2: no hay memoria por `conversation_id`.
- QA3: el descuento pedido por chat no se detecta.

- **Resolución (usuario, 2026-10-24):** se corrigieron QA1, QA2 y QA3 antes de la demo, con historial corto enviado a Grok. Están implementados, cubiertos por pruebas y validados con Grok real (ver [hito S2](hito-s2.md)).
- **Sigue pendiente de D6:** la fecha fija de `evaluated_at` y el `except Exception: pass` de la consulta de stock. Propuesta original:
  - usar la hora del reloj inyectado;
  - informar la fuente caída;
  - derivar `request_id` del `external_message_id`;
  - detectar las solicitudes de descuento y propagar `discount_requested`;
  - pasar el `conversation_id` a `AgentService`.

Revisado: 2026-10-24. Registrar la resolución y sus fuentes en [log.md](../log.md).

## D7: Integración con `developer/conde`

La rama de Conde (11 commits sobre `9660c76`) rediseñó la conversación:

- carrito por conversación (`ConversationState`) y confirmación obligatoria de SKU en `hermes.py`;
- `application/commercial_scope.py`, que filtra temas no comerciales antes del LLM;
- `agent/customer_safety.py`, que sanitiza las respuestas al cliente;
- una semilla sintética ampliada.

El merge simulado con `developer/daniel` da conflictos en `hermes.py`, `service.py`, `app.py`, `README.md` y `docs/ARCHITECTURE.md`.

- **Resolución (usuario, 2026-10-24):** **base de `developer/daniel` más los módulos de Conde.**
  - Se mantienen la cotización directa, QA1–QA3 y la memoria con historial a Grok.
  - Se integran en `AgentService` `CommercialScopePolicy` y `CustomerResponsePolicy`, la semilla sintética y los cambios sin conflicto.
  - **No** entran el carrito ni la confirmación de SKU de Conde.
  - Las pruebas de Conde que dependen del carrito se retiran o adaptan, y se documenta cuáles.
- **Aplicado (2026-10-24):** merge `bf89cf0` (`Merge: :twisted_rightwards_arrows: IntegrateCondeScopeAndSafetyModules`), hecho por Codex en un worktree aislado y auditado por el orquestador; 131 pruebas en verde.
  - El sanitizador no se aplica con el proveedor `mock`, porque las pruebas necesitan ver los marcadores internos. Con Grok, Groq y Hermes siempre se aplica.
  - Las pruebas de Conde retiradas por depender del carrito están en `docs/CAMBIOS_CONDE.md` y en el log.
- **Pendiente:** comunicar a Conde que su carrito quedó fuera de esta integración.

## D8: Canal WhatsApp con Kapso

El usuario pidió el 2026-10-24 conectar WhatsApp siguiendo `whatsapp.pdf` con Kapso.

- **Resolución (usuario):**
  - Kapso es el canal por defecto y Evolution API queda opcional, detrás del mismo puerto.
  - Túnel `cloudflared` para exponer el webhook.
  - Pruebas primero en el sandbox de Kapso.
  - Se descarta el agente alojado en Kapso, para no saltarse el backend.
- **Contrato:** [canal Kapso](canal-kapso.md).
- **Pendiente:**
  - Que el usuario pegue `KAPSO_API_KEY` a mano en `.env`.
  - Obtener el `phone_number_id` del sandbox.
  - Registrar el webhook.

## D9: Limpieza al stack Kapso + Grok

El usuario confirmó el 2026-10-24 que la prueba por WhatsApp con Kapso respondió con la lógica de negocio. Pidió eliminar todo lo que ya no contribuye al proyecto.

- **Resolución (usuario):**
  - **Evolution API:** se elimina por completo (adaptador, endpoint `/v1/channels/whatsapp/webhook`, compose, scripts de configuración y QR, pruebas y configuración). Kapso es el único canal de WhatsApp.
  - **Hermes:** se elimina el proveedor LLM `hermes`, junto con su clave escrita en el código, lo que cierra D4. `HermesToolbelt` pasa a llamarse `CommercialToolbelt` y los marcadores `HERMES_TOOL` pasan a `XEON_TOOL`. La lógica no cambia.
  - **Groq:** se **mantiene** como respaldo de Grok.
  - **Material eliminado:**
    - el video `video/xeon-remotion/`;
    - `docs/NOTA_ENTREGA_2026-10-17.md`;
    - los restos locales sin versionar: canvas, `whatsapp.pdf`, `Xeon/`, `.bootstrap/`, `.kilo/`, QR, `references/senior-architect-agent` y la skill `integrate-whatsapp-calling`;
    - se confirma en un commit el borrado de `Xeon.png`, `video/.../xeon.png` y `.interface-design/system.md`.
- **Reparto:** Codex se encarga del código; el orquestador, de la documentación, la wiki y los restos locales; agy, de la QA final.
- **Efectos en la wiki:** se retira `metodo-arquitectura.md` (dependía de `references/`) y D2 queda cerrada al eliminarse esa referencia.

## D10: Organización de la raíz del repositorio

El usuario pidió el 2026-10-24 ordenar los archivos sueltos aplicando buenas prácticas.

- **Resolución (usuario):**
  - **Se quedan en la raíz** los archivos que exigen las herramientas o las convenciones: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` (las CLI los cargan desde la raíz), `pyproject.toml`, `uv.lock`, `.python-version`, `Dockerfile`, `.dockerignore`, `compose.yaml`, `compose.groq.yaml`, `.env.example`, `.gitignore` y `skills-lock.json`.
  - **Se mueven con `git mv`:**
    - `XeonContexto.md` → `docs/XeonContexto.md`;
    - `GLOSSARY.md` → `docs/GLOSSARY.md`;
    - `logo-oficial-definitivo.png` → `assets/brand/xeon-logo.png`;
    - `XeonCli.png` → `assets/readme/xeon-cli.png`.
  - **Nuevo:** `docs/README.md` como índice de la documentación.
- **Efecto:** la fuente de verdad pasa a `docs/XeonContexto.md`. El orden de lectura no cambia: `docs/XeonContexto.md` → `docs/ARCHITECTURE.md` → `CONTRIBUTING.md`.

## D11: Evaluación conversacional y cambio de modelo

El usuario pidió el 2026-10-24 un sistema de pruebas conversacionales con cliente simulado, un harness independiente y regresiones permanentes.

- **Resolución (usuario):**
  - **Modelo `grok-4.6`** para XEON, el cliente simulado y el juez. Era el que pidió como el más cercano en razonamiento a «gpt-5.6 Luna». La pasarela no publica comparativas; `grok-4.6` es de agosto de 2026 y cuesta unas 2,4 veces más por token de salida que `grok-4.20-0309-non-reasoning`.
  - **Presupuesto:** tope de 600 llamadas por corrida.
  - **Correcciones:** E1 a E6 se corrigen con una regresión cada uno.
  - **Framework:** `langwatch-scenario`, sujeto a un spike.
- **Contrato:** [evaluación conversacional](evaluacion-conversacional.md). Auditoría: [auditoría 2026-10-24](auditoria-2026-10-24.md).
- **Skills:**
  - `scenarios` se descargó con `gh`, porque el instalador falla en Windows por rutas largas del monorepo de LangWatch.
  - `ai-system-testing`, `agent-evals` y `promptfoo-evaluation` se instalaron con `npx skills add`.
  - Las cuatro fueron revisadas por el orquestador sin hallar comandos peligrosos.

## D12: ¿XEON es un RAG?

El usuario preguntó el 2026-10-26 si XEON es un RAG y si conviene convertirlo «meramente en un RAG avanzado».

- **Hoy:** XEON es un **agente con herramientas deterministas**. Grok interpreta y redacta, y el backend busca, consulta stock y calcula. No hay recuperación de fragmentos de texto ni embeddings: la búsqueda es léxica (`InMemoryProductCatalog.search_candidates`).
- **Resolución (orquestador, dentro del plan aprobado por el usuario):**
  - **No se convierte solo en un RAG.** Un RAG fundamenta texto, pero no puede agregar, modificar ni quitar líneas, sumar totales exactos ni garantizar stock vigente, que son justo las operaciones que falla el [reporte QA de Conde](qa-conde-2026-10-24.md).
  - **Arquitectura híbrida:** agente con herramientas transaccionales más recuperación como **una herramienta más**, en dos usos:
    1. búsqueda híbrida de productos (léxica para SKU y códigos, vectorial con `pgvector` para descripciones vagas, fusión RRF y *reranker* opcional);
    2. base de conocimiento (fichas técnicas, guías de proyecto y políticas en texto).
  - **Precios, stock y totales nunca salen del RAG:** siempre de una consulta directa a la fuente de la ferretería. Es coherente con `docs/XeonContexto.md` y `docs/ARCHITECTURE.md`.
- **Estado:** `propuesta`. El índice híbrido es la fase 3 y queda por definir con el usuario.

## D13: Conectar XEON a la base de datos de cualquier ferretería

El usuario indicó el 2026-10-26 que XEON debe instalarse sobre el software de cualquier ferretería y depender de **su** base de datos, no de la nuestra. Pidió investigar la tecnología.

- **Opciones investigadas:**

| Opción | Resultado |
|---|---|
| MCP Toolbox for Databases (`googleapis/mcp-toolbox`, Apache-2.0) | Más de 20 motores y SQL parametrizado en `tools.yaml`, pero exige un servidor y un binario aparte, y trae `execute_sql` genérico. Queda como adaptador opcional |
| dlt (dlthub) | Cargas incrementales desde SQL y REST. Se reserva para sincronizar el índice de búsqueda (fase 3) |
| API de ERP colombianos (Siigo, Alegra, Loggro) | Futuro adaptador REST. Alegra está confirmada por *wrappers* de terceros; Siigo queda por verificar |
| Text-to-SQL (Vanna, WrenAI) | **Descartado:** AGENTS.md prohíbe que un modelo ejecute SQL libre |

- **Resolución:** **conector declarativo de la ferretería**, en tres partes.
  1. **Contrato:** los puertos `ProductCatalog`, `BranchInventory` y el nuevo `BranchDirectory`.
  2. **Adaptador principal:** SQLAlchemy 2 Core de solo lectura (PostgreSQL, MySQL/MariaDB, SQL Server, SQLite, Oracle y, opcionalmente, Firebird). Cada ferretería tiene un `connectors/<tenant>.yaml` con consultas parametrizadas y el mapeo de columnas a los campos canónicos.
  3. **Selección:** `DATA_SOURCE=synthetic|sql|rest|csv`. Los datos sintéticos pasan a ser un adaptador más.
- **Políticas** de pago, entrega y horarios: archivo de configuración por ferretería (decisión del usuario).
- **Estado:** `aprobado` (plan del 2026-10-26). La implementación es la fase 2 y se hace después de las correcciones de QA. Detalle en el [conector de la ferretería](conector-ferreteria.md).

# Decisiones pendientes

## D1 — Cómo expresar el alcance técnico vigente

El [documento funcional](../../XeonContexto.md) presenta PostgreSQL 17, JSONB, pgvector, búsqueda RAG y aprobación con PDF dentro del recorrido/MVP; su introducción habla de un núcleo implementado. La [arquitectura](../../docs/ARCHITECTURE.md), líneas 101-105, y el [README](../../README.md), líneas 12-16 y 42-46, dicen que persistencia empresarial, búsqueda vectorial, aprobación y PDF siguen pendientes. El [contenedor](../../src/xeon/application/container.py) usa adaptadores en memoria y el [catálogo](../../src/xeon/adapters/catalog/memory.py) puntúa coincidencias de palabras.

**Impacto:** un lector podría interpretar una arquitectura objetivo como una capacidad lista para operar. **Estado:** discrepancia confirmada; no se resolvió alterando documentos o código.

**Decisión propuesta al equipo:** actualizar `XeonContexto.md` con dos apartados explícitos, “prototipo implementado” y “arquitectura objetivo del MVP”, manteniendo la visión comercial intacta. Alternativamente, si el documento debe describir solo el estado final, marcar cada flujo como objetivo y enlazar el README para el corte actual. El equipo debe elegir la redacción antes de cerrar D1.

## D2 — Momento de incorporar el método externo

El repositorio `senior-architect-agent` se descargó para consulta. Falta decidir si seguirá como referencia local o si el equipo quiere instalarlo como habilidad formal para futuros agentes. No es un requisito para mantener esta wiki.

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

---
tags:
  - xeon/operacion
---

# Orquestación multi-agente de XEON

Protocolo con el que varios agentes CLI trabajan en paralelo sobre XEON dentro de **herdr**. Es la adaptación al proyecto de la [fuente original](../raw/orquestacion-original-2026-10-24.md), que era un prompt genérico de competencia. Relacionado: [hito S2](hito-s2.md), [contratos de herramientas](contratos-herramientas.md), [decisiones pendientes](decisiones-pendientes.md), [esquema de la wiki](../SCHEMA.md).

Revisado: 2026-10-24. Estado general: **implementado como acuerdo de trabajo**; las piezas de código citadas tienen su propio estado.

## 1. Contexto y motor

- **Producto:** XEON, un agente comercial para ferreterías ([qué es XEON](que-es-xeon.md)).
- **Motor LLM:**
  - **Grok** (`grok-4.20-0309-non-reasoning`) a través de `LLMPort` y `OpenAICompatibleLLM`. Es el proveedor por defecto desde la corrección urgente del 2026-10-24 (en curso; ver D3 en [decisiones pendientes](decisiones-pendientes.md)).
  - **`mock`** solo para pruebas.
  - **Groq**: alternativa no predeterminada.
- **Memoria compartida:** la wiki `wiki/` sustituye al "Vault" del prompt original. Un cambio no existe oficialmente mientras no esté registrado en la wiki.
- **Plataforma del reto (corrección del 2026-10-24):** la indicación inicial de ignorar el "Sandbox de Plática" quedó superada. La pasarela oficial de Grok que entregó el usuario, `https://api.reto.pltk.mx/v1`, es de la plataforma del reto. Es el endpoint por defecto del motor (ver D3).

### Mapeo de rutas del prompt original

| Original | En XEON |
|---|---|
| `/vault/status_s2.md` | [pages/hito-s2.md](hito-s2.md) |
| `/vault/tools_spec.md` | [pages/contratos-herramientas.md](contratos-herramientas.md) |
| `/vault/changelog.md` | [log.md](../log.md) |

## 2. Roles

El orquestador principal es **Claude Opus**, por decisión del usuario del 2026-10-24. Los nombres "Codex 6" y "Gemini 3.8" del original corresponden a los agentes realmente presentes en herdr.

| Agente (panel herdr)            | Rol                                                        | Responsabilidades                                                                                                                                                                                                                         |
| ------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Claude Opus** (`w7:p3`)       | Orquestador, arquitecto, auditor DRY y guardián de la wiki | Reparte las tareas por herdr. Define los contratos y los esquemas Pydantic de las herramientas. Revisa los diffs en busca de duplicación y violaciones hexagonales. Corre `ruff`, `mypy` y `pytest`. Integra el inbox y hace los commits. |
| **Codex** (`w7:p9`)             | Desarrollador core y deploy                                | Implementa adaptadores y herramientas detrás de los puertos (por ejemplo, el proveedor Grok). Se encarga de los scripts y el entorno Docker. Antes de crear una utilidad, busca en la wiki y en el código para no duplicar.               |
| **agy / Antigravity** (`w7:p8`) | QA, usuarios sintéticos y auditor de contexto              | Corre pruebas multi-turno con `mock` y casos límite (entrada malformada, inyección de prompt, webhooks repetidos). Prepara el guion reproducible de la demo de 2 minutos.                                                                 |

Los ID de panel dependen de la sesión. Verificarlos con `herdr agent list` antes de usarlos. El CLI `gemini` no está instalado; Antigravity cumple ese rol.

### Modelo de agy y asignación por nivel de razonamiento

Desde el 2026-10-26, por decisión del usuario, **agy usa Gemini 3.8 Flash con razonamiento medio**. Antes usaba Gemini 4 Argon.

**Asignar a agy:**
- tareas acotadas y bien especificadas, con zona de archivos, criterios de aceptación y comandos de verificación explícitos;
- escribir escenarios y checks a partir de un caso dado;
- corridas de QA, offline o en vivo, con tope de llamadas;
- revisión de video y documentos contra una lista;
- compilar notas y documentos a partir de fuentes indicadas.

**No asignar a agy:**
- diseño de arquitectura, refactorizaciones que cruzan módulos, cambios de dominio o de concurrencia, ni diagnósticos de causa raíz abiertos. Eso va a Codex, y el diseño lo hace Opus.

**Control:** el orquestador audita todo resultado de agy antes de integrarlo. La tabla QA-001…023 de su nota del 2026-10-26 trajo descripciones equivocadas y su primer oráculo agregó productos en código (A1). Con un modelo Flash, los prompts deben ser más cerrados y la auditoría más estricta.

## 3. Ciclo de trabajo

1. **Pre-check:** cada agente lee `AGENTS.md`, [index](../index.md), esta página y [hito S2](hito-s2.md).
2. **Diseño (Opus):** define o actualiza el contrato en [contratos de herramientas](contratos-herramientas.md).
3. **Implementación (Codex):** implementa con pruebas y corre las verificaciones de `CONTRIBUTING.md`.
4. **Auditoría cruzada:** Opus revisa el diff (duplicación, fronteras, secretos) y agy ejecuta los usuarios sintéticos con `mock`.
5. **Consolidación (Opus):** integra las notas del inbox con el bloqueo de escritura, actualiza [hito S2](hito-s2.md) y [log](../log.md), y hace el commit.

Los agentes que no integran escriben solo en su nota única de `wiki/inbox/`, según [SCHEMA.md](../SCHEMA.md).

## 4. Reglas obligatorias

- **Commits:** formato `Type: :gitmoji: ActionInUpperCamelCase`, con la acción en inglés y sin punto final. Por ejemplo, `Feat: :sparkles: AddGrokProviderAdapter`.
- **GitHub CLI:** push y PR con `gh`, siempre con confirmación del usuario.
- **Sin atribución de agentes:** ningún agente puede figurar como autor, coautor, colaborador ni contribuidor. Esto prohíbe el trailer `Co-Authored-By`, `--author`, cambiar el committer y las firmas "Generated with…" en los PR.
- **Wiki:** cada descripción o decisión sustantiva se guarda en la wiki desde cualquier conversación o CLI. Los agentes pueden crear, modificar o retirar contenido dentro de `wiki/`.
- **Seguridad:** no leer `secrets/` ni `.env`. Ninguna llamada pagada (Groq o Grok) sin autorización explícita y presupuesto.

## 5. Comandos herdr del orquestador

```powershell
herdr agent list
herdr agent prompt w7:p9 "<tarea>" --wait --timeout 600000
herdr agent read w7:p9 --source recent-unwrapped --lines 150
herdr agent get w7:p9
```

**Windows PowerShell 5.1:** pasar el prompt en un here-string `@'…'@` **sin comillas dobles** dentro. PowerShell 5.1 parte los argumentos nativos que llevan `"`, y herdr responde `unknown option` (código 2, el prompt no se envía). Verificado el 2026-10-24. Para confirmar que el agente empezó, usar `--wait --until working --timeout 30000`.

**Higiene de git con varios agentes** (causa verificada por agy el 2026-10-24):

- **Causa principal del `.git/index.lock` abandonado:** la app de escritorio de Codex (`ChatGPT.exe`), que lanza varios `git` concurrentes al detectar cambios. VS Code, con `git.autorefresh`, contribuye.
- **Mitigación aplicada:** `git.autorefresh=false` y `git.autofetch=false` en `.vscode/settings.json`, y el estado de interfaz de Obsidian ignorado en `.gitignore`.
- **Agentes:** las lecturas de git usan `git --no-optional-locks status|diff`.
- **Antes de borrar un lock:** confirmar que no hay ningún proceso `git.exe` vivo y moverlo aparte, nunca borrarlo a ciegas.
- **Recomendación al usuario:** cerrar la app de escritorio de Codex mientras se coordina por herdr.

Si un agente queda `blocked`, el orquestador inspecciona con `agent read` y consulta al usuario antes de responder el diálogo. Un `timeout` no prueba que el prompt no llegara: no se reenvía a ciegas.

## Por verificar

- Los ID de panel cambian entre sesiones de herdr.
- El modelo exacto de Grok y si Groq se retira (D3).

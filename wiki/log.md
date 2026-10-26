# Registro de la wiki

## [2026-10-24] ingest | XEON y método de arquitectura

Se creó la bóveda a partir del encargo LLM Wiki, el documento funcional, la arquitectura, las convenciones, el README y puntos concretos del código. Se descargó `senior-architect-agent` en `references/` y se registró su commit. Se identificó la diferencia entre el recorrido de producto previsto y el prototipo en memoria; quedó abierta en [decisiones pendientes](pages/decisiones-pendientes.md). No se cambió el código de XEON.

## [2026-10-24] decisión | Wiki compartida entre agentes

Se incorporó el [encargo de colaboración](raw/colaboracion-agentes-2026-10-24.md) al esquema: registrar aportes sustantivos de cualquier conversación o CLI que opere en XEON, permitir crear/modificar/retirar páginas y coordinar escrituras paralelas mediante notas individuales y exclusión local. `AGENTS.md`, `CLAUDE.md` y `GEMINI.md` enlazan esta política para sesiones nuevas.

## [2026-10-24] ingest | Orquestación multi-agente

Se ingresó `wiki/orquestacion.md` como fuente S9, conservada literalmente en `raw/orquestacion-original-2026-10-24.md`, y se retiró de la raíz.

- **Página adaptada:** [orquestación](pages/orquestacion.md).
- **Decisiones del usuario:**
  - Claude Opus es el orquestador principal en herdr, con Codex como desarrollador y agy como QA.
  - Se migra a Grok (D3).
  - El Sandbox de Plática se ignora.
  - `/vault` se mapea a la wiki.
  - Commits `Type: :gitmoji: ActionInUpperCamelCase` en inglés, con `gh` y sin atribución de agentes.
- **Páginas nuevas:** [hito S2](pages/hito-s2.md), [contratos de herramientas](pages/contratos-herramientas.md) y [propuestas de escalado](pages/propuestas-escalado.md). Esta última es la lluvia de ideas previa, como propuesta y con afirmaciones sin fuente retiradas.
- **Decisiones registradas:** D3 a D6 en [decisiones pendientes](pages/decisiones-pendientes.md).
- **Repositorio:** `AGENTS.md` recibe la regla de commits.
- **Límite:** no se cambió código; el trabajo de Grok y de QA quedó delegado.

## [2026-10-24] integración | Entregas de Codex y agy

Se integraron las notas de inbox `2026-10-24T-codex-grok-provider.md` y `2026-10-24T-agy-qa-s2.md` y se retiraron de `inbox/`.

- **Codex:** perfil `grok` implementado (D3 avanzada) y helper `_require_api_key` sin duplicación.
- **agy:** `tests/test_multiturn_context.py`, con los defectos QA1 a QA3 fijados como `xfail` estrictos, y el guion de demo en [hito S2](pages/hito-s2.md).
- **Auditoría del orquestador:** ruff y mypy en verde; pytest con 93 aprobadas y 3 `xfail`. Las opciones de la CLI del guion se verificaron con `--help`.
- **Coordinación:** herdr marcó a agy como `blocked` por un diálogo de permiso de escritura que se resolvió en su panel; el orquestador no respondió el diálogo.
- **Páginas actualizadas:** [hito S2](pages/hito-s2.md), [decisiones pendientes](pages/decisiones-pendientes.md) (D3 y D6) y [estado del corte](pages/estado-del-corte.md).

## [2026-10-24] corrección | Grok como motor oficial por defecto

El usuario reportó como urgente que XEON se ejecutaba con `mock` o Groq en lugar de la integración oficial con Grok, y entregó la pasarela del reto `https://api.reto.pltk.mx/v1` y una clave.

- **Clave:** guardada solo en `secrets/grok_api_key.txt` (ignorado por git); no se compartió con los agentes ni se registró aquí.
- **Modelo:** el usuario eligió `grok-4.20-0309-non-reasoning` entre 14 modelos que expone `GET /v1/models`.
- **Codex:**
  - Grok es el proveedor por defecto en `config.py`, `compose.yaml` y `.env.example`.
  - `tests/conftest.py` fuerza `mock` y bloquea la red.
  - Corrigió QA4, el modelo que reportaba `/health`.
- **agy:** QA del arranque por defecto y de la falta de clave; detectó QA4.
- **Orquestador:**
  - `AGENTS.md` actualizado.
  - Una llamada real verificada.
  - Suite con 97 aprobadas y 3 `xfail`.
  - Se corrigió la nota sobre Plática en [orquestación](pages/orquestacion.md).
- **Inbox:** se integraron y retiraron las notas `codex-grok-default`, `agy-qa-grok-default` y `codex-qa4-health-model`.

## [2026-10-24] corrección | QA1–QA3, entorno Grok y bloqueo de git

Decisiones del usuario (preguntas del orquestador):

- Corregir los tres defectos antes de la demo.
- Memoria con historial corto enviado a Grok.
- Push a `developer/daniel` sin PR.
- Rotar la clave al terminar el reto.

El usuario autorizó expresamente modificar archivos privados.

- **Codex:**
  - Creó `.env` con `LLM_PROVIDER=grok` (antes no existía) y el script `scripts/configure_grok_env.py`, que no imprime secretos.
  - Implementó el contrato QA1–QA3: `request_id` estable por mensaje de WhatsApp, puerto `ConversationMemory` con adaptador acotado y LRU, y detección de descuentos.
  - Hizo los ajustes de la auditoría: eliminó el envoltorio sin uso y movió el adaptador a `adapters/conversation/`.
- **agy:**
  - Diagnosticó el `index.lock` abandonado: lo deja la app de escritorio de Codex y contribuye el `autorefresh` de VS Code.
  - Aplicó la mitigación en `.vscode/settings.json` y `.gitignore`.
  - Hizo el ensayo real con Grok (3 llamadas): QA2 y QA3 se comportan como se esperaba.
- **Orquestador:** auditoría del diff; suite con 104 aprobadas y 0 `xfail`.
- **Hallazgo pendiente:** `.interface-design/system.md` aparece borrado en el árbol de trabajo sin intervención de los agentes. Se excluyó de los commits y queda por confirmar con el usuario.
- **Inbox:** se integraron y retiraron las notas `codex-env-grok`, `agy-git-lock`, `codex-qa123` y `agy-grok-rehearsal`.

## [2026-10-24] implementación | XEON CLI, merge con Conde y README

El usuario pidió una CLI `xeon` basada en `XeonCli.png`, el uso de las skills `tui-design` y `tui-fundamentals`, un merge con `developer/conde`, un PR hacia `develop` y un README mejorado.

- **Skills:** instaladas y revisadas; se versiona `skills-lock.json`. El usuario había dado dos comandos idénticos.
- **Contrato:** [XEON CLI](pages/xeon-cli.md).
- **Shell:** Codex implementó `src/xeon/shell/` (`5286b02`) con dos pasadas visuales tras la auditoría.
- **QA:** agy validó en terminal real y encontró QA-CLI-1 a QA-CLI-4. Codex los corrigió (`d0ae75a`) y agy confirmó la corrección en terminal real.
- **Merge:** D7 (base nuestra más los módulos de alcance y seguridad de Conde), hecho por Codex en el worktree `../xeon-merge` (`bf89cf0`).
- **Documentación:** el orquestador reestructuró el README alrededor de la CLI y actualizó `docs/ARCHITECTURE.md` (`2aa9da9`).
- **Repositorio:** `origin/main` ya no existe en el remoto; el PR va hacia `develop`.
- **Archivos borrados fuera de los agentes:** `Xeon.png`, `video/.../xeon.png` y `.interface-design/system.md` siguen sin incluirse en commits, pendientes de confirmación del usuario.
- **Inbox:** se integraron y retiraron las notas `codex-xeon-cli`, `codex-merge-conde`, `agy-xeon-cli-qa` y `codex-cli-qa-fixes`.

## [2026-10-24] limpieza | Stack Kapso + Grok (D9)

- **Verificación del usuario:** el usuario confirmó que la prueba por WhatsApp (sandbox de Kapso) respondió con la lógica de negocio.
- **Kapso:** commits `1ce0e26` (canal, de Codex, auditado: HMAC antes de parsear) y `1deb23f` (contrato). La puesta en marcha (sandbox `597907523413541`, webhook `86b37b90…`, quick tunnel) está registrada en [canal Kapso](pages/canal-kapso.md).
- **Limpieza D9:** commit `54fa146`.
  - Codex eliminó Evolution API y el proveedor Hermes, renombró `HermesToolbelt` a `CommercialToolbelt` (marcadores `XEON_TOOL`), migró las pruebas QA1 y multi-turno al webhook firmado de Kapso y sustituyó el simulador.
  - Se borraron `video/xeon-remotion/` y `docs/NOTA_ENTREGA_2026-10-17.md`, y se confirmó el borrado de `Xeon.png`, `video/.../xeon.png` y `.interface-design/system.md`.
  - Suite: 146 aprobadas.
- **Restos locales:** el orquestador eliminó, tras revisar su contenido, `Sin título.canvas`, `whatsapp.pdf`, `Xeon/` (plantillas vacías de Obsidian), `.bootstrap/`, `.kilo/`, `qr_whatsapp.png`, `references/` y la skill `integrate-whatsapp-calling` (también retirada de `skills-lock.json`).
- **Wiki:**
  - Se retiró `metodo-arquitectura.md` y la fuente S6 quedó marcada como retirada.
  - D2 y D4 quedan cerradas.
  - Se actualizaron arquitectura, estado, contratos, canal Kapso y propuestas.
  - Se integraron y retiraron las notas `codex-kapso-channel`, `claude-kapso-live` y `codex-stack-cleanup`.
- **Pendiente:** Codex está actualizando la documentación del repositorio y después viene la QA final de agy.

## [2026-10-24] QA | Limpieza D9 verificada

- **Documentación del repositorio:** Codex actualizó README, `ARCHITECTURE.md`, `XeonContexto.md`, `AGENTS.md`, `DESIGN.md` y `.gitignore` (commit `b37bf02`); las reglas de `AGENTS.md` se conservaron.
- **API:** el orquestador reinició la API con el código limpio en el puerto 8000. `/health` devuelve `grok`; a través del túnel, una petición sin firma recibe 401.
- **QA de agy** (sin llamadas pagadas):
  - ruff, mypy y pytest en verde (146).
  - Cero restos de Evolution, Hermes o Remotion en código y documentación.
  - El simulador firmado en un puerto aislado devolvió `processed`; el duplicado, `ignored`; sin firma, 401.
  - El shell muestra `mock / mock-xeon-v1` sin rastros del stack anterior.
- **Hallazgos (todos de severidad baja):**
  - El de un argumento del README no se reprodujo: la versión vigente usa los argumentos correctos.
  - Los restos en `hito-s2.md`, `contratos-herramientas.md` y `canal-kapso.md` fueron corregidos por el orquestador.
- **Inbox:** se integraron y retiraron las notas `codex-docs-cleanup` y `agy-cleanup-qa`.

## [2026-10-24] organización | Raíz del repositorio (D10)

- **Movidos con `git mv`** (Codex): `XeonContexto.md` y `GLOSSARY.md` a `docs/`, el logo a `assets/brand/xeon-logo.png` y el diseño del CLI a `assets/readme/xeon-cli.png`.
- **Nuevos:** `docs/README.md` (índice) y `scripts/check_doc_links.py` (25 enlaces del repositorio, 0 rotos).
- **Wiki:** el orquestador reescribió los enlaces en 9 páginas; 132 enlaces revisados, 0 rotos.
- **Raíz final:** solo los archivos que exigen las herramientas o las convenciones.
- **Verificación:** 146 pruebas en verde.

## [2026-10-24] repositorio | Normalización y PR hacia develop

- **Finales de línea:** los cambios que mostraba `CONTRIBUTING.md` (y antes `GLOSSARY.md`) eran solo de final de línea. La causa era la falta de `.gitattributes` con `core.autocrlf=true`. Se añadió `.gitattributes` (`* text=auto eol=lf`, CRLF para `.ps1/.bat/.cmd` y binarios marcados) y se renormalizó; el índice ya estaba en LF, así que solo se agregó el archivo (`1fcbac0`).
- **Ramas:** `developer/daniel` avanzó por fast-forward hasta `feature/kapso-channel` y se subió.
- **PR #1** (`developer/daniel` → `develop`): 42 commits, sin conflictos, `MERGEABLE`. Título y descripción actualizados a todo el alcance (CLI, Grok, Kapso, QA, D7, D9, D10), sin firmas de agentes.

## [2026-10-24] CI | Snapshots del shell independientes de plataforma

- **Fallo:** el CI del PR #1 (ubuntu-latest) falló en `test_banner_text_snapshot`. Codex lo reprodujo en WSL Ubuntu: Rich usa `legacy_windows=True` en Windows (esquinas `┌┐└┘`) y `False` en Linux (`╭╮╰╯`). El contenido era idéntico y no había defecto de producción.
- **Corrección:** consola de prueba determinista y snapshots de texto en `tests/snapshots/` en lugar de hashes. Pasa en Windows y en Linux; 146 aprobadas.
- **Nota:** Codex instaló `python3.14-venv` en WSL Ubuntu para reproducir el fallo.

## [2026-10-24] integración | PR #1 fusionado en develop

- PR #1 (`developer/daniel` → `develop`) fusionado con merge commit `3790f45` (`Merge: :twisted_rightwards_arrows: IntegrateDeveloperDanielIntoDevelop`), con el CI `quality` en verde y sin firmas de agentes.
- **Pendiente:** `.github/workflows/ci.yml` solo dispara en push a `main` (ya inexistente) y `developer/daniel`, y en PR; conviene añadir `develop`.

## [2026-10-24] documentación | Despliegue de WhatsApp con Kapso

- **Sincronización:** `developer/daniel` se actualizó con `develop` (merge `8e01b02`).
- **Script de Codex:** `scripts/kapso_webhook.py` con pruebas sin red. Validado por el orquestador contra Kapso real con `list` y `update-url` sobre la misma URL, sin cambios efectivos.
- **Guía del orquestador:** `docs/DESPLIEGUE_WHATSAPP.md` cubre requisitos, secretos, `.env`, skills, `phone_number_id`, las tres terminales (API, túnel, webhook), verificación, guion de prueba desde el teléfono, diagnóstico, apagado y paso a un número propio. Está enlazada desde el README, `docs/README.md` y [canal Kapso](pages/canal-kapso.md).

## [2026-10-24] operación | Terminal 3 de la guía de WhatsApp

- **Ambigüedad reportada por el usuario:** el paso 3 de `docs/DESPLIEGUE_WHATSAPP.md` no dejaba claro qué ejecutar. La API y el túnel del orquestador habían terminado con la sesión anterior; el usuario los tenía corriendo en su terminal y el webhook seguía apuntando a la URL vieja.
- **Configuración aplicada por el orquestador:** leyó el host actual desde `cloudflared` (`/quicktunnel` en el puerto 20241), comprobó `/health` (Grok) y actualizó el webhook `86b37b90…`. Una petición sin firma dio 401.
- **Codex:** añadió `kapso_webhook.py sync-tunnel`, que detecta el túnel y el webhook y actualiza o crea el webhook. Validado en real (HTTP 200); suite en verde.
- **Guía:** el paso 3 se reescribió con un solo comando (`sync-tunnel`) y su salida esperada.

## [2026-10-24] mantenimiento | Clasificación por colores en el grafo de Obsidian

- **Pedido del usuario:** clasificar la wiki por colores para que el grafo muestre más información.
- **Etiquetas:** 15 páginas recibieron encabezado YAML con una etiqueta de tipo (`xeon/decision`, `xeon/estado`, `xeon/arquitectura`, `xeon/interfaz`, `xeon/producto`, `xeon/operacion`, `xeon/fuente`, `xeon/hub`). `raw/` y `log.md` se clasifican por ruta, sin modificarlos.
- **Colores:** 8 grupos en `wiki/.obsidian/graph.json` y 10 en `.obsidian/graph.json`; la bóveda de la raíz añade `docs/` y los archivos de instrucciones. Ambos archivos son locales e ignorados por Git.
- **Documentación:** la convención quedó en [SCHEMA](SCHEMA.md) y la leyenda en [index](index.md).

## [2026-10-24] corrección | Colores del grafo sobrescritos por Obsidian

- **Problema:** el usuario no veía los colores. La causa no era el tema oscuro: con la bóveda `wiki` abierta, Obsidian reescribió `wiki/.obsidian/graph.json` desde memoria y dejó `colorGroups` vacío.
- **Solución:** el orquestador creó `scripts/apply_obsidian_graph_colors.py`, que se niega a correr con Obsidian abierto salvo con `--force`. Con Obsidian cerrado lo aplicó: 8 grupos en la bóveda `wiki` y 10 en la raíz.
- **Documentación:** la leyenda de [index](index.md) explica cómo reproducirlos.

## [2026-10-24] inicio | Evaluación conversacional (D11)

- **Rama:** `feature/conversational-evals` desde `developer/daniel`.
- **Auditoría** de solo lectura registrada en [auditoría 2026-10-24](pages/auditoria-2026-10-24.md), con los defectos E1–E6.
- **Contrato** en [evaluación conversacional](pages/evaluacion-conversacional.md); decisión D11.
- **Skills:** `scenarios` (descargada con `gh`), `ai-system-testing`, `agent-evals` y `promptfoo-evaluation`, revisadas.

## [2026-10-24] avance | Evaluación conversacional: modelo, spike y personas

- **Codex:** cambio de modelo a `grok-4.6` (`2a7d098`) y spike de Scenario válido tras un diagnóstico (`b5d573c`).
- **agy:** 14 personas (`feca7f6`).
- **Orquestador:** llamada real de verificación de `grok-4.6` y revisión de la ceguera de las personas.
- **Inbox:** se integraron y retiraron las notas `codex-model-and-spike` y `agy-personas`.
- **Siguiente:** el harness `evals/`, de Codex.

## [2026-10-24] integración | E11, evaluador, CI y guía del QA humano (HITO #2)

- **Definición del HITO #2**, tomada de la única fuente documentada (`raw/orquestacion-original`, línea 12): 3 herramientas conectadas a Grok y un flujo de demo de 2 minutos. Criterios H1–H4 en el plan del orquestador.
- **Codex:** E11 (`4def4fa`) y el evaluador con reporte incremental (`30386ad`); 216 pruebas en verde y offline 42/42.
- **agy:** `docs/QA_HITO2.md` y la sección de la línea base cancelada en `docs/evals/RESULTADOS.md`.
- **Orquestador:**
  - CI con `develop` como disparador (`6972dc7`).
  - Guía revisada; «Listo para QA humano» queda pendiente hasta la corrida final (`1059538`).
  - Canal de Gmail verificado con un borrador de prueba, ya eliminado. **Discrepancia:** la cuenta conectada (`danielsantiagomayorga03`) difiere del correo del perfil (`danielsantiagomayorgatellez03`); falta que el usuario confirme el destinatario.
- **Inbox:** se integraron y retiraron las notas `agy-baseline-live`, `codex-defect-fixes`, `codex-e11-evaluator` y `agy-qa-guide`.

## [2026-10-24] integración | E12–E14, verificación en vivo y PR hacia develop

- **Codex:** E12 (`1c4fc8b`), E13 (`5dfef42`), evaluador para cifras rechazadas (`90da4f6`), reintento del juez (`85a2638`), E14 (`3dda3d3`) y la deduplicación de `require_text` (`3538cb7`, criterio H3).
- **agy (QA):**
  - Validó la guía contra el comportamiento real (`1e73bcd`) y encontró E14 y el aviso de stock `stale` en la demo, que es correcto porque el snapshot sintético es del 2026-10-08.
  - Verificación en vivo `ccc15515` (109 llamadas): 3 PASS, 5 FAIL y 0 ERROR. De los 5 FAIL, 3 son falsos positivos del evaluador y 2 son defectos nuevos de XEON (E15, E16).
- **Orquestador:** auditoría de los diffs (ningún criterio relajado; el evaluador ignora cifras rechazadas solo si son literales del cliente y van en una negativa), integración de las ramas, sincronización con `develop` y PR por pedido del usuario.
- **Estado del HITO #2:** implementación terminada para H1–H4. La validación automatizada **no** está aprobada del todo (E15 y E16 abiertos, con 3 falsos positivos del evaluador pendientes). **No** se declara LISTO PARA QA HUMANO.
- **Inbox:** se integraron y retiraron las notas `agy-qa-validation`, `agy-verify-e12-e13`, `codex-e12-e13` y `codex-e14-dedup`.

## [2026-10-24] integración | PR #3 fusionado en develop

- El PR #3 (`developer/daniel` → `develop`, 36 commits) se fusionó con el merge commit `349bb7b`, por pedido del usuario, con el CI en verde.
- E15 y E16, y los tres falsos positivos del evaluador, siguen abiertos y están declarados en el PR.

## [2026-10-24] preparación | Video del HITO #2

- **Pedido del usuario:** video demostrativo por WhatsApp y CLI, con las 3 herramientas reales, solución gratuita y automatizable, delegando entre agentes y con mínima intervención suya.
- **Decisiones:** FFmpeg, WhatsApp Web, narración de ElevenLabs y subtítulos, corregir E17 y E18 antes de grabar.
- **El smoke del CLI que hizo el orquestador en mock** confirmó E1, E9, E13 y E14, y destapó E17 y E18.
- **Codex:** E17, E18 y la traza de herramientas.
- **Orquestador:** el guion `docs/VIDEO_HITO2.md`.
- **En curso:** los scripts de video (Codex) y el ensayo del guion (agy).
- **Nueva página:** [video HITO #2](pages/video-hito2.md).
- **Inbox:** se integraron y retiraron las notas `codex-video-prep-a` y `claude-cli-smoke`.

## [2026-10-24] avance | Video del HITO #2: ensayo, scripts y E19

- **Ensayo en vivo de agy:** 5 llamadas y las 4 escenas OK, con tiempos registrados en [video HITO #2](pages/video-hito2.md). agy ajustó el guion a la traza real.
- **Scripts de video de Codex** (`83d5bfe`).
- **E19** (descuento en la misma conversación reutiliza el borrador) delegado a Codex.
- **Narración con ElevenLabs** delegada a agy. La clave del usuario ya está en `secrets/`.
- **Inbox:** se integraron y retiraron las notas `agy-video-rehearsal` y `codex-video-scripts`.

## [2026-10-24] avance | E19 corregido y narración bloqueada por la clave

- **Codex:** E19 y la traza sin duplicados (`bd30ec0`); suite en verde y offline 42/42.
- **agy:** `video/hito2/narration.json` con los 6 textos del guion (unos 46 s estimados). La generación se detuvo porque `secrets/elevenlabs_api_key.txt` está vacío. No se leyó el archivo; lo informó el script.
- **Inbox:** se integraron y retiraron las notas `codex-e19` y `agy-narration`.

## [2026-10-24] operación | Clave de ElevenLabs y entorno de grabación

- **Clave de ElevenLabs:** el usuario la entregó por el chat con permiso expreso y se compromete a **rotarla al terminar el hito**. Se guardó en `secrets/elevenlabs_api_key.txt` (ignorado por Git) y no se registra su valor.
- **Pendiente:** rotar las claves de Grok y de ElevenLabs al terminar el reto.
- **Entorno:** el orquestador reinició la API con el código actual (con traza `TOOL` y E17–E19) en una ventana visible «XEON API - traza de herramientas», abrió la ventana «XEON CLI» y sincronizó el webhook de Kapso con el túnel activo, que se mantuvo para no cambiar la URL.

## [2026-10-24] grabación | Video del HITO #2

- **Narración:** agy generó la narración con ElevenLabs (6 clips, 41,6 s).
- **Grabación:** el orquestador grabó la pantalla con FFmpeg (281 s) mientras el usuario hacía los pasos.
- **Revisión de agy:** 7 de 7 pasos y las 3 herramientas en la traza. Dos diferencias de ejecución real (3 bultos en lugar de 10, y la traza visible solo en la escena 4).
- **Decisión:** editar sin regrabar, con difuminado por privacidad. Edición delegada a Codex. Detalle en [video HITO #2](pages/video-hito2.md).
- **Inbox:** se integraron y retiraron las notas `agy-narration` y `agy-raw-review`.

## [2026-10-24] entrega | Video del HITO #2 aprobado por QA

- **Codex:** edición con difuminado de privacidad y corrección de la posición del rótulo «espera acortada».
- **agy (QA):** dictamen APROBADO del video `video/hito2/XEON_HITO2_demo.mp4` (1:53,5) y sección «Resultado» en `docs/VIDEO_HITO2.md`.
- **Pendiente:** la validación del QA humano, y rotar las claves de Grok y ElevenLabs al terminar el hito.
- **Inbox:** se integraron y retiraron las notas `codex-video-edit` y `agy-final-video-review`.

## [2026-10-24] entrega | Voz del video y notas de entrega del HITO #2

- **Codex (`2a9c429`):** narración sincronizada con los subtítulos y normalizada a −16,2 LUFS. El orquestador lo verificó con `ffprobe` y `ebur128`. Detalle en [video HITO #2](pages/video-hito2.md).
- **agy:** `docs/ENTREGA_HITO2.md`, con lo logrado, lo que falló, el costo por tarea (solo lo medido; el costo en USD no está medido), la calidad y cómo reproducir.
- **Auditoría del orquestador:** se corrigieron la especificación de audio desactualizada, la afirmación «sincronizada con `develop`» y una referencia de commit.
- **Pendiente:** volcar el contenido en el Google Doc del informe técnico, porque el conector de Google Docs no está cargado en la sesión.
- **Inbox:** se integraron y retiraron las notas `codex-video-audio` y `agy-entrega-hito2`.

## [2026-10-24] entrega | PR #5 y texto del informe técnico del Hito #2

- **Push y PR:** el usuario confirmó el push de `developer/daniel` y el PR [#5](https://github.com/TuMinipeka/Xeon-agente-cotizaciones/pull/5) hacia `develop`.
- **Informe técnico:** el orquestador redactó el texto del Hito #2 con las 10 secciones del Google Doc del Hito 1, más las notas de entrega. El usuario lo pegará a mano porque el conector de Google Docs no está disponible. La fuente es `docs/ENTREGA_HITO2.md`.

## [2026-10-25] entrega | Notas de entrega y documento técnico para Drive

- **Notas de entrega separadas:** qué se logró, qué falló, costo por tarea (unas 810 llamadas a `grok-4.6`; costo en USD no medido), aprendizajes, pendientes y enlaces.
- **Documento técnico:** con la estructura de 10 secciones del Hito 1.
- **Archivos:** versiones HTML y Markdown en `video/hito2/entrega/` (ignorado por Git). El usuario las sube a Drive junto con el video.
- **Pendiente:** fusionar el PR #5 (abierto, con CI en verde) y poner el enlace del video en las notas.

## [2026-10-25] entrega | Entregable integrado del Hito #2

- **Archivo:** `video/hito2/entrega/Entregable_XEON_Hito2.{md,html}`, ignorado por Git.
- **Contenido:** la estructura de 10 secciones del Hito 1, actualizada al Hito 2, más las notas de entrega y los anexos de reproducción y enlaces.
- **Correcciones sobre el borrador mezclado que pegó el usuario:** se quitó el contenido obsoleto del Hito 1 (Evolution API, Hermes, 80 pruebas) y se marcó la tarifa de Grok como interpretación.

## [2026-10-26] integración | Grafo Graphify del proyecto

- **Codex (`07281a5`):** Graphify 0.9.95 fijado en el grupo `graph`; script `scripts/build_graphify_map.py`; skill en `.claude/skills/graphify/`; puentes en `wiki/graph/`. AST local, sin costo.
- **Auditoría del orquestador:** barrido de claves y rutas de `secrets/` sobre la salida con 0 coincidencias; `explain` y `query` funcionan; avance rápido a `developer/daniel`.
- **Nueva página:** [grafo del proyecto](pages/grafo-proyecto.md), con la clasificación de qué herramienta usar. `AGENTS.md` incluye ahora la sección «Navegar el proyecto sin leer cada archivo».
- **Inbox:** se integró y retiró la nota `codex-graphify`.

## [2026-10-26] decisión | Reporte QA de Conde, RAG (D12) y conector de la ferretería (D13)

- **Ramas:** `origin/develop` y `origin/QA/testing` se fusionaron en `developer/daniel` (`3c56547`). El reporte se movió a `docs/qa/` (`da20d43`).
- **Diagnóstico:** los 23 fallos salen de 4 causas raíz. Detalle en el [reporte QA de Conde](pages/qa-conde-2026-10-24.md).
- **Decisiones:** [D12 y D13](pages/decisiones-pendientes.md). XEON es un agente con herramientas; el RAG será solo una herramienta de búsqueda y conocimiento; el conector será declarativo con SQLAlchemy.
- **Delegación:** Codex hace la fase 1 en `fix/qa-conde-cart` y agy los escenarios S15–S20.

## [2026-10-26] auditoría | Fase 1 de las correcciones de QA de Conde

- **Codex:** seis commits, de `d29c45a` a `8503a15`. Carrito versionado, intérprete de intenciones, ejecutor comercial, formato para WhatsApp y flujo único.
- **agy:** escenarios S15–S20 y 5 checks nuevos (`aaca88f`).
- **Auditoría:** B1, el evaluador probaba el flujo viejo (corregido); A1, el oráculo agregaba productos en código (enviado a agy).
- **Resultado:** S01–S20 dan 60/60 offline. Detalle en el [reporte QA de Conde](pages/qa-conde-2026-10-24.md).
- **Inbox:** se integraron las notas `codex-qa-conde` y `agy-qa-conde-evals`. La de agy sigue abierta hasta cerrar A1.

## [2026-10-26] corrección | Modelo de agy y precisión de D12

- **agy:** pasa de Gemini 4 Argon a **Gemini 3.8 Flash con razonamiento medio** (decisión del usuario). Se añadió en [orquestación](pages/orquestacion.md) una guía para asignarle tareas según su nivel de razonamiento.
- **D12:** se corrigió la afirmación «XEON no es un RAG». XEON tiene un RAG estructurado (recupera del catálogo y aumenta el prompt) dentro de un agente con herramientas. La decisión no cambia: no se convierte en un RAG de texto puro.

## [2026-10-26] integración | Fases 1 y 2 fusionadas en developer/daniel

- **Fusiones:** `fix/qa-conde-cart` (correcciones de QA, más A1 de agy en `df19216`) y `feat/store-connector` (conector SQL, `87ca4d2`) entraron en `developer/daniel`. Se retiró el worktree `xeon-connector`.
- **Quality gate:** 294 pruebas, `ruff`, `mypy` (82 archivos) y evaluación offline S01–S20 con 60 PASS, 0 FAIL y 0 ERROR.
- **Páginas:** se actualizó el [conector de la ferretería](pages/conector-ferreteria.md) a `implementado`.
- **Inbox:** se integraron y retiraron las notas `codex-store-connector` y `agy-qa-conde-evals`.

## [2026-10-26] decisión | Embudo guiado y políticas de la ferretería (D14)

- **Corrida en vivo de agy:** S15–S20 con `grok-4.6` dio 1 PASS y 5 FAIL en 64 llamadas (huella `0c0b8619431b38a0`). Los defectos D1–D5 se delegaron a Codex en `fix/live-qa-defects`, y el falso positivo de `branch_matches` en vivo, a agy.
- **D14 (usuario):** embudo guiado con texto acotado, confirmación con botón que pasa al asesor humano, plantilla demo de políticas para Colombia y redirección ante desvíos.
- **Contrato:** [embudo de cotización](pages/embudo-cotizacion.md).

## [2026-10-26] operación | Nuevo agente Claude Sonnet 5.5

- **Incorporación:** el usuario sumó un agente Claude Sonnet 5.5 (panel `w7:pQ`) para trabajar en paralelo. Se registró en [orquestación](pages/orquestacion.md).
- **Primera tarea (delegada):** colorear el grafo de Graphify por capa en las bóvedas de Obsidian.

## [2026-10-26] operación | Armonización de documentación con el flujo actual

- **Integrado:** notas `sonnet-graph-colors` (leyenda de capas del grafo, en el índice) y `codex-live-defects` (D1–D5, `1422e05`) más la sección 4 de `agy-live-qa-conde` (`branch_matches` en vivo, `045e7c7`). La nota de agy sigue abierta en el inbox.
- **Páginas:** índice, estado del corte, arquitectura actual y QA de Conde. Docs: README, `XeonContexto.md` y `ARCHITECTURE.md`.
- **Correcciones:** `CommercialScopePolicy` y `prepare_verified_context` ya no existen (flujo `IntentInterpreter` + `CommercialExecutor` + `QuoteCart`); el conector SQL opcional (`DATA_SOURCE`) existe; el modelo vigente es `grok-4.6`; el RAG se describe como D12 (propuesta); el embudo guiado D14 figura como aprobado y no implementado.
- **Pendiente:** resultado de la re-ejecución en vivo S15–S20 (la corrida previa fue 1 PASS y 5 FAIL); aplicar los colores del grafo con Obsidian cerrado.

## [2026-10-26] verificación | Conector SQL en motores reales, guía QA del embudo y segunda corrida en vivo

- **Sonnet (`4af2c69`):** el conector pasa en PostgreSQL 17.6 y MySQL 8.4.6 (9 de 9). Los hallazgos H1 y H2 en MySQL se delegaron otra vez a Sonnet. Detalle en el [conector de la ferretería](pages/conector-ferreteria.md).
- **agy:** guía manual `docs/QA_EMBUDO.md` (`d3d4d37`) y segunda corrida en vivo con 3 PASS y 3 FAIL (`a47b7fc`), 128 de 150 llamadas. Los residuales de S15, S16 y S19 se delegaron a Codex.
- **Codex:** el embudo D14 quedó implementado en `feat/guided-funnel`, por ahora detrás de `GUIDED_FUNNEL_ENABLED`. Está migrando el evaluador para que el embudo sea el único flujo.

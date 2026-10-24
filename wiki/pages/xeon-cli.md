# XEON CLI (Tactical Agent Shell)

Shell interactivo que se abre con el comando `xeon`. Sirve para que el equipo pruebe personalmente el agente desde la terminal, con comandos abreviados. Relacionado: [orquestación](orquestacion.md), [contratos de herramientas](contratos-herramientas.md), [hito S2](hito-s2.md).

Revisado: 2026-10-24. Estado: **`implementado`**. Commits `5286b02` (shell) y `d0ae75a` (endurecimiento tras QA). El orquestador definió el contrato y auditó; Codex implementó; agy hizo la QA en terminal real.

## Fuentes de diseño

- **Diseño visual del usuario:** [`assets/readme/xeon-cli.png`](../../assets/readme/xeon-cli.png). Contiene el logo de tortuga con X, el título `XEON CLI`, el subtítulo `Tactical Agent Shell`, un panel `system ready` (versión, modo, perfil), un panel `// AVAILABLE COMMANDS` y el prompt `xeon >`, en verde neón sobre fondo negro.
- **Skills instaladas el 2026-10-24** en `.agents/skills/` (con enlace en `.claude/skills/`):
  - `tui-design` (diegomarino): estructura visual, tokens de color, glifos de ancho simple, estados × tamaños y pistas en el pie.
  - `tui-fundamentals` (josiahsiegel): separar modelo, actualización y vista; tratar el tamaño como entrada; degradación con `NO_COLOR`, sin TTY y `TERM=dumb`; equivalentes no interactivos.
- El usuario pidió una tercera skill ("colores neón, bordes y tipografía"), pero su comando era idéntico al de `tui-design`. Las reglas de color salen de esa misma skill.

## Decisiones de producto

- **Forma:** REPL en línea (banner, prompt y salida en el flujo normal), no pantalla completa. Los subcomandos actuales (`xeon health`, `chat`, `quotes`, `stock`) se mantienen para scripts.
- **Framework:** **Rich** (declarado como dependencia directa) y `input()`. La consola de Windows ya da historial con flecha arriba. No se añade `prompt_toolkit`.
- **Motor:** en proceso por defecto. `build_container(Settings())` usa la configuración vigente (Grok `grok-4.20-0309-non-reasoning`), así que no hace falta levantar la API. Con `xeon --api URL` el shell usa la API HTTP.

## Comandos y alias

| Comando | Alias | Acción |
|---|---|---|
| `run <mensaje>` | `r` | Envía el turno al agente (`AgentService.respond`, misma conversación). Un texto que no es comando se trata como `run`. |
| `status` | `s` | Proveedor, modelo y base URL efectivos; si hay clave (`configured`/`missing`, nunca el valor); conversación y turnos. |
| `config` | `c` | Configuración efectiva no secreta. Los campos de clave aparecen enmascarados. |
| `logs` | `l` | Bitácora de la sesión: hora, comando, proveedor, latencia y resultado (`✓`/`▲`/`✗`). `logs N` muestra las últimas N entradas. |
| `new` | `n` | Abre una conversación nueva (nuevo `conversation_id`, memoria vacía). |
| `help` | `h`, `?` | Tabla de comandos. |
| `quit` | `q`, `exit` | Sale con código 0. Ctrl-C sale con 130 y Ctrl-D (EOF) con 0, siempre restaurando la terminal. |

## Visual

- **Tokens:** los colores se definen como tokens semánticos en un único módulo de tema (`accent`, `accent.dim`, `fg`, `fg.muted`, `border`, `status.ok`, `status.warn`, `status.error`). Ningún color va escrito directamente en las vistas.
- **Paleta neón:** acento verde neón, fondo de la terminal, bordes en el acento atenuado.
- **Glifos:** solo de ancho simple (bloques y caracteres de dibujo de cajas). Sin emoji en la interfaz.
- **Estados con glifo y color:** `●`/`✓` para `system ready`, `▲` para clave ausente (`degraded`), `✗` para error del proveedor.
- **Tamaños:**
  - **Ancho (≥100 columnas):** logo a la izquierda, título y paneles a la derecha, como el PNG.
  - **Compacto (80×24):** título y paneles apilados, logo reducido u omitido.
  - **Mínimo (<60 columnas):** banner de una línea y la lista de comandos.
- **Pie:** línea de pistas `r run  s status  c config  l logs  h help  q quit`.
- **Degradación:**
  - Con `NO_COLOR` o salida sin TTY: texto plano sin estilos.
  - Con stdin sin TTY: lee comandos línea por línea (útil para scripts y pruebas) y no muestra el banner animado.

## Arquitectura

Paquete `src/xeon/shell/` con capas separadas:

- `theme.py`: tokens.
- `commands.py`: análisis de alias y despacho puro.
- `session.py`: estado (conversación y bitácora) y un puerto de motor con dos implementaciones, en proceso y HTTP.
- `render.py`: funciones puras que devuelven elementos de Rich según el estado y el ancho.
- `app.py`: bucle y ciclo de vida de la terminal.

La CLI es una capa de entrada: no calcula precios ni duplica reglas del dominio. Typer abre el shell con `invoke_without_command=True` cuando `xeon` se ejecuta sin subcomando.

## Criterios de aceptación

- `xeon` abre el shell. El banner se parece al PNG a 120×30 y es legible a 80×24.
- `r <msg>` responde con Grok real usando la configuración por defecto, y con `mock` en las pruebas.
- `config` y `status` nunca muestran claves.
- La suite cubre: alias, render a 120, 80 y 50 columnas, `NO_COLOR`, stdin sin TTY, `run` con mock, `new`, `logs` y códigos de salida.
- `ruff`, `mypy` y `pytest` en verde.

## Verificación (2026-10-24)

- **Auditoría visual del orquestador:** dos pasadas sobre el render en texto a 120 y 80 columnas.
  - Primera pasada: el título grande, el logo con la X legible, el marco HUD y los paneles limitados a unas 72 columnas.
  - Segunda pasada: corrigió una regresión en la alineación de la columna de comandos.
  - A 80×24 el banner ocupa 22 filas.
- **QA de agy en un panel real de herdr:**
  - Banner neón, `h`, `s`, `c` (clave `configured`, sin valores), `l`, `n`, `NO_COLOR` y pipe sin TTY: correctos.
  - Una llamada real a Grok devolvió `TUB-PVC-20` a 4.200 COP con 12 unidades en la sede norte.
- **Hallazgos y corrección** (commit `d0ae75a`, re-probado en terminal real salvo QA-CLI-3):
  - **QA-CLI-1:** Ctrl-C no salía en Windows. Ahora sale con 130 y deja la terminal restaurada.
  - **QA-CLI-2:** los comandos mal escritos iban a Grok. Ahora muestran una sugerencia sin llamar al motor, y los argumentos sobrantes dan aviso de uso.
  - **QA-CLI-3:** Grok cambió la unidad «unidad» por «metro». El prompt ahora exige respetar literalmente la unidad, el precio y las cantidades. Sin re-ensayo real.
  - **QA-CLI-4:** `help` en modo plano repetía el banner. Corregido.
- **Suite:** 144 aprobadas; `ruff` y `mypy` limpios.
- **Lección de coordinación:** el orquestador envió `send-keys 1` a agy cuando su diálogo ya estaba cerrado y el carácter quedó en la caja de entrada; se borró. Desde entonces, cualquier `send-keys` a otro agente se envía solo si el estado `blocked` se comprueba en el mismo comando.

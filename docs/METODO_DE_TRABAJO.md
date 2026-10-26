# Método de trabajo para agentes de XEON

Guía de incorporación para cualquier agente (humano o IA) que se sume al proyecto. Las reglas obligatorias están en [`AGENTS.md`](../AGENTS.md). Este documento explica **cómo** se trabaja día a día. Si algo de aquí contradice `AGENTS.md`, manda `AGENTS.md`.

## 1. Antes de tocar nada

1. Lee, en este orden:
   - [`docs/XeonContexto.md`](XeonContexto.md): qué es XEON y sus principios;
   - [`docs/ARCHITECTURE.md`](ARCHITECTURE.md): qué está implementado y qué está planeado;
   - [`CONTRIBUTING.md`](../CONTRIBUTING.md): ramas y pruebas.
2. Abre la wiki por [`wiki/index.md`](../wiki/index.md) y lee las páginas relacionadas con tu tarea, sobre todo:
   - [estado del corte](../wiki/pages/estado-del-corte.md);
   - [decisiones](../wiki/pages/decisiones-pendientes.md), de D1 a D15;
   - [orquestación](../wiki/pages/orquestacion.md).
3. Para entender el código **sin leer archivo por archivo**, consulta el grafo local (ver [`docs/GRAPHIFY.md`](GRAPHIFY.md)):
   ```powershell
   uv run --locked --group graph graphify explain <Simbolo>
   uv run --locked --group graph graphify path <A> <B>
   uv run --locked --group graph graphify query "<pregunta>" --budget 1500
   ```
   Para saber qué existe y por qué, usa la **wiki**. Para saber dónde está algo y con qué se conecta, usa el **grafo**. Para ver qué hace exactamente una línea, usa `rg` y lee el código.

## 2. Roles y coordinación (herdr)

| Rol | Agente | Qué hace |
|---|---|---|
| Orquestador | Claude Opus | Diseña los contratos, reparte el trabajo, audita cada entrega, fusiona, integra la wiki y publica, siempre con la confirmación del usuario |
| Desarrollador principal | Codex | Código complejo, cambios que cruzan módulos, persistencia e integraciones |
| Apoyo | Claude Sonnet | Documentación, wiki, grafo, revisiones de seguridad y cortes acotados |
| QA | agy (Gemini Flash) | Tareas cerradas: guías de QA, escenarios, corridas con tope de llamadas e integraciones pequeñas en la wiki |

- **Paneles:** el orquestador reparte las tareas con `herdr agent prompt <panel> "<tarea>"`. Los ID de panel cambian entre sesiones; consúltalos con `herdr agent list`.
- **Cómo es una tarea:** cada tarea trae la zona de archivos permitida, los criterios de aceptación, el gate que hay que pasar y la nota de inbox que se debe dejar.
- **Al terminar:** el agente responde con un resumen corto y queda libre. El orquestador audita su trabajo y asigna la siguiente tarea al primer agente libre, según lo que mejor sabe hacer.
- **Permisos:** un agente no puede aprobar los avisos de permiso de otro. Esos los aprueba el usuario.

## 3. Ramas y worktrees

- **Rama de integración:** `developer/daniel`. Hacia `develop` solo se llega por un PR con CI en verde y confirmación del usuario. Nadie trabaja directamente en `main`.
- **Trabajo en paralelo:** cada agente usa su propio **worktree** y una rama corta, por ejemplo `feat/<tema>` o `fix/<tema>`.
  ```powershell
  git worktree add -b feat/<tema> ..\<carpeta> developer/daniel
  ```
  Así nadie cambia de rama dentro del árbol de otro agente.
- **Fusiones:** las hace el orquestador. Si hay conflictos, los resuelve el autor del código en su worktree (fusionando `developer/daniel` en su rama). Después el orquestador hace un avance rápido (*fast-forward*).
- **WIP:** el trabajo a medias se queda en su rama (`Chore: :construction: ...`) y nunca se fusiona.

## 4. Commits

Formato obligatorio: `Type: :gitmoji: ActionInUpperCamelCase`. La acción va en inglés y sin punto final. Ejemplos:

- `Feat: :sparkles: AddGuidedQuotationFunnel`
- `Fix: :lock: RequireApiKeyAndBoundAnonymousLoad`
- `Docs: :memo: RecordPhaseThreePriorities`
- `Test: :test_tube: MigrateSqlZoneTestsToGuidedFlow`
- `Merge: :twisted_rightwards_arrows: MergeAdvisorPanel`

Además:

- **Ningún agente figura como autor ni coautor:** sin `Co-Authored-By` y sin firmas «Generated with…» en commits ni PR.
- **Commits con pathspec explícito** (`git commit -m "..." -- <archivos>`) cuando varios agentes comparten el árbol, para no arrastrar cambios ajenos.
- **Push y PR** solo con la confirmación del usuario, usando `gh`.

## 5. Gate de calidad, antes de declarar algo terminado

Hay que pasarlo con dos perfiles.

```powershell
# Perfil del CI (igual que GitHub Actions)
uv sync --locked --group db
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
uv run --locked pytest

# Perfil completo
uv sync --locked --group db --group evals --group graph --group pdf-test
uv run --locked mypy src evals
uv run --locked pytest
uv run --locked --group evals python -m evals.runner --mode offline   # S01–S22, sin costo
uv run --locked python scripts/check_doc_links.py                     # 0 enlaces rotos
```

- **Integración** (PostgreSQL y MySQL en contenedores): `pytest -m integration`. Apaga los contenedores al terminar.
- **Corridas en vivo con Grok:** solo con un tope de llamadas aprobado por el usuario.
- **Regresiones:** cada defecto corregido lleva una prueba que reproduzca la frase o el caso real. Nunca se relajan checks, escenarios, oráculo ni fixtures del evaluador. Si un cambio en el evaluador se justifica, se documenta su motivo.

## 6. La wiki (bóveda de Obsidian) como memoria compartida

La wiki es la **memoria persistente** del proyecto. No dependas de la memoria de una sesión. El protocolo completo está en [`wiki/SCHEMA.md`](../wiki/SCHEMA.md).

1. **Los aportes van primero al inbox.** Cada agente deja una nota única en `wiki/inbox/AAAA-MM-DDT-<agente>-<tema>.md` con:
   - procedencia y fecha;
   - estado (implementado, verificado o propuesta);
   - commits, comandos y evidencia;
   - límites honestos.
2. **Las páginas compartidas se editan con exclusión.** Para tocar `wiki/pages/`, `index.md`, `log.md` o `sources.md`:
   - crea el directorio `wiki/.write-lock` sin `-Force`; si ya existe, espera;
   - relee los archivos antes de editarlos;
   - al terminar, borra **solo tu** lock.
3. **Integración:** el orquestador, o el agente al que se le encargue, pasa la nota a las páginas, añade una entrada al final de `wiki/log.md` con el formato `## [AAAA-MM-DD] operación | asunto` y retira del inbox la nota ya integrada.
4. **Honestidad:**
   - una idea del usuario se registra como `propuesta` hasta que haya evidencia de que está implementada;
   - no se presenta lo planeado como hecho;
   - las cifras que no se midieron se marcan como «no medido».
5. **Decisiones:** las decisiones del usuario se registran en [decisiones](../wiki/pages/decisiones-pendientes.md) con el siguiente número libre (hoy D15).
6. **Grafo y colores:** las páginas llevan etiquetas `xeon/*` (decisión, estado, arquitectura, interfaz, producto, operación, fuente, hub) que les dan color en Obsidian. El grafo de código se regenera con `scripts/build_graphify_map.py`, y los colores se aplican con `scripts/apply_obsidian_graph_colors.py` **con Obsidian cerrado**.

## 7. Seguridad, que no se negocia

- **Secretos:** nunca leas, imprimas, registres ni versiones `secrets/*` ni los archivos `.env`. Las credenciales solo se leen desde archivos en `secrets/`, y los usuarios crean las suyas con los scripts provistos.
- **Lo que un modelo nunca hace:** aprobar cotizaciones, calcular montos, ejecutar SQL libre ni cambiar inventario. El backend decide (con `Decimal`) y la aprobación es humana (`APPROVED_FOR_BILLING`, en el panel).
- **Datos personales:** sin teléfonos ni textos de clientes en logs, métricas o notas.
- **Acciones con efecto externo:** exponer servicios (túneles), cambiar el webhook de Kapso, hacer push o abrir un PR requieren la confirmación del usuario.

## 8. Ciclo típico de una tarea

1. Leer el contexto (wiki, grafo y decisiones).
2. Trabajar en tu worktree o en la zona de archivos asignada.
3. Escribir el código con regresiones.
4. Pasar el gate en los dos perfiles.
5. Hacer commit con el formato del proyecto.
6. Dejar la nota en el inbox.
7. Responder con un resumen corto.

Después, el orquestador audita, fusiona e integra la wiki, y el usuario confirma la publicación.

# Coordinacion autonoma Codex + Grok

Este flujo coordina al **agente de codigo**, no al agente comercial XEON. Grok 4.6 trabaja mediante
Kilo CLI; Codex actua como compuerta de calidad en solo lectura. El runtime comercial en
`xeon.agent` permanece separado y no recibe terminal, Git ni permisos de edicion.

## Contrato del ciclo

```text
Product Backlog / HU
        |
        v
 WorkOrder 1.0 ---- alcance, criterios, rutas y controles
        |
        v
 Kilo + Grok ------- implementa, prueba y crea commits locales
        |
        v
 WorkerReport 1.0 -- declaracion no confiable
        |
        +----> Git diff/log reales + ruff + mypy + pytest
        |                         |
        v                         v
              Codex read-only review
                       |
          +------------+-------------+
          |            |             |
      APPROVED  CHANGES_REQUESTED   BLOCKED
                        |
                        v
                NextDirective 1.0
                        |
                        +----> Grok, maximo 3 iteraciones
```

Cada orden representa una sola HU. La autonomia esta acotada: no hace `push`, `merge`, `rebase`,
cambio de rama ni despliegue; no lee secretos; no puede aprobar cambios de reglas de negocio. Un
reporte de Grok nunca reemplaza el diff ni las verificaciones ejecutadas por el coordinador.

## Requisitos locales

- Rama `developer/daniel` limpia y nunca `main`.
- Proyecto sincronizado con `uv sync --locked` y Python 3.14.8.
- Kilo CLI autenticado con el proveedor OpenAI-compatible `grok-4.6` definido en `kilo.jsonc`.
- Codex CLI autenticado; el coordinador lo invoca con `--ephemeral --sandbox read-only`.
- Clave rotada y almacenada solo en `secrets/reto_key.txt`, que Git ignora.

El modo `--execute` consume el proveedor configurado en Kilo y una ejecucion de Codex por
iteracion. El modo predeterminado es un ensayo sin llamadas a modelos.

## Crear una orden desde una HU

La persona responsable elige la HU del Product Backlog y convierte sus resultados observables en
criterios independientes. Ejemplo:

```powershell
uv run xeon-coordinate new `
  --story-id HU-T04 `
  --title "DistinguirInventarioEntreSedes" `
  --objective "Distinguir disponibilidad local, traslado y entrega sin inventar existencias." `
  --criterion "AC-1=Una sede alternativa no se reporta como inventario local." `
  --criterion "AC-2=La respuesta conserva origen y tipo de disponibilidad." `
  --allowed-path "src/xeon/**" `
  --allowed-path "tests/**" `
  --allowed-path "docs/**"
```

El comando crea `.agentic/work-orders/HU-T04-run.json`. Ese directorio es local e ignorado por
Git. Antes de ejecutar, revisar el JSON y confirmar que los criterios provienen realmente de la HU,
no de una propuesta del modelo.

## Ensayar y ejecutar

```powershell
# No llama a Grok ni a Codex.
uv run xeon-coordinate run .agentic/work-orders/HU-T04-run.json

# Inicia el ciclo autonomo acotado.
uv run xeon-coordinate run .agentic/work-orders/HU-T04-run.json --execute
```

El preflight rechaza una rama distinta, `main` o un worktree sucio. Grok usa
`.kilo/agents/xeon-worker.md`, la skill `xeon-implementation-worker`, TDD y los Skills pertinentes.
Codex recibe la orden, el reporte, la evidencia independiente y el diff; su skill
`xeon-quality-coordinator` decide y, si es corregible, genera la siguiente directiva.

## Evidencia y estados

Cada corrida queda en `.agentic/runs/<work-order-id>/`:

- `grok-prompt-<n>.md`, `grok-events-<n>.jsonl` y `grok-report-<n>.json`;
- `verified-evidence-<n>.json` con Git y controles ejecutados por el coordinador;
- `codex-prompt-<n>.md` y `quality-review-<n>.json`;
- `next-directive-<n>.json` cuando Codex solicita correcciones;
- `state.json` con `DRY_RUN`, `APPROVED`, `CHANGES_REQUESTED` o `BLOCKED`.

`BLOCKED` requiere intervencion humana. Tambien se detiene tras tres iteraciones. `APPROVED` solo
significa que la HU paso este contrato local; publicar, fusionar o desplegar sigue siendo una
decision humana.

## Que debe controlar Codex

Codex relaciona cada criterio con pruebas observables, revisa regresiones con las funcionalidades
existentes, direccion de dependencias hexagonales y completitud del corte vertical. Precios,
descuentos, impuestos, stock, permisos y estados deben continuar en codigo determinista. Si el
trabajo contradice `XeonContexto.md`, `GLOSSARY.md` o una regla vigente, no emite una directiva de
implementacion: bloquea y solicita la decision de la persona responsable.

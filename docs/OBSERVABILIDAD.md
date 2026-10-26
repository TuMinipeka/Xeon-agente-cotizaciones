# Observabilidad y costo por tarea

XEON mide tokens, latencia y costo estimado por turno sin dependencias nuevas. Los eventos no
contienen teléfono, texto del cliente ni la clave de conversación.

## Qué se registra

Un evento (`MetricEvent`) por cada etapa:

| Etapa | Qué mide |
|---|---|
| `turno` | Un mensaje completo en `AgentService` (con el paso del embudo como `operation`) |
| `llm` | Una llamada al modelo: latencia, tokens `prompt/completion` reportados por el proveedor y costo |
| `ejecutor` | `CommercialExecutor.execute` |
| `catalogo` / `inventario` | Cada método del catálogo y del inventario (memoria o conector SQL) |
| `envio_kapso` | Envío de la respuesta por Kapso |

Las etapas son inclusivas: una consulta de catálogo hecha dentro del ejecutor cuenta en ambas.
Cada evento lleva `task` (el escenario en las evaluaciones, `chat` en producción) y `step` (paso
del embudo).

## Tokens y costo

- Los tokens salen del bloque `usage` de la API compatible con OpenAI (Grok y Groq). Si el
  proveedor no lo devuelve, el evento marca `usage_known=false`, deja los tokens en `null` y **no
  hay costo**: nunca se estiman como reales. `MockLLM` informa 0 tokens, que es un hecho.
- El costo usa una tarifa configurable por millón de tokens: `LLM_PRICE_INPUT_PER_MTOK`,
  `LLM_PRICE_OUTPUT_PER_MTOK` y `LLM_PRICE_UNIT` (etiqueta, por defecto `unidad-no-documentada`).
  **Es un supuesto**: la unidad de la pasarela del reto no está documentada. Sin las dos tarifas no
  se calcula costo.

## Activar y leer

```powershell
$env:METRICS_PATH = "reports/metrics.jsonl"        # eventos JSONL; sin definir no se escribe nada
$env:LLM_PRICE_INPUT_PER_MTOK = "1"                # supuesto, ver arriba
$env:LLM_PRICE_OUTPUT_PER_MTOK = "3"
uv run python scripts/cost_report.py reports/metrics.jsonl
uv run python scripts/cost_report.py reports/evals/<huella> --json
```

El reporte agrega por tarea: llamadas al LLM, tokens, llamadas sin uso conocido, costo y latencia
p50/p95 por etapa (rango más cercano, determinista).

## Evaluaciones

`python -m evals.runner` guarda `observability.jsonl` junto a `cases.jsonl` y añade `observability`
a cada caso y al `report.json` (por escenario). En modo `offline` el LLM es simulado: 0 llamadas y
0 tokens, pero las latencias de las etapas locales sí se miden.

## Límites

- Los eventos en memoria de `InMemoryMetrics` se descartan al reiniciar; `METRICS_PATH` es un
  archivo local sin rotación.
- El campo `usage` de la pasarela del reto aún no se verificó con una llamada real: este corte se
  probó solo con dobles HTTP.
- Sin trazas OpenTelemetry (convenciones `gen_ai.*` aún en desarrollo).

---
tags:
  - xeon/operacion
---

# Observabilidad y costo por tarea (Sonnet, 2026-10-26)

Fecha: 2026-10-26. Autor: Sonnet. Worktree `C:\Users\danie\Documents\xm`, rama `feat/observability` (desde `7c153ce`). Estado: **implementado y verificado localmente** con dobles; sin llamadas pagadas. Origen: opción E de [propuesta de la fase 3](../pages/propuesta-fase3.md) y D15. Documentación: `docs/OBSERVABILIDAD.md`. Pendiente: integrar en las páginas compartidas y fusionar la rama.

- `LLMResponse.usage` (`TokenUsage`): el adaptador OpenAI-compatible lee `usage`; si falta o es inválido queda desconocido (no se estima). `MockLLM` informa 0.
- Puerto `MetricsRecorder` (`application/ports/metrics.py`) y adaptadores `NullMetrics`, `InMemoryMetrics` y `JsonlMetrics` (`METRICS_PATH`). Sin teléfono, texto ni clave de conversación.
- Etapas: `turno`, `llm`, `ejecutor`, `catalogo`, `inventario` y `envio_kapso`. `MeteredLLM` y un proxy `timed` envuelven los puertos en `build_container`.
- Tarifa por millón de tokens en `Settings` (`LLM_PRICE_*`), marcada como **supuesto** porque la unidad de la pasarela no está documentada.
- `scripts/cost_report.py` agrega por tarea (llamadas, tokens, p50/p95, costo). El runner de evals guarda `observability.jsonl` y `observability` en cada caso y en el reporte.
- Cambios mínimos en `container.py` (4 puntos: parámetro `metrics`, envolturas de catálogo, inventario, LLM y ejecutor) y `AgentService`/`api/app.py` (cronometrar turno y envío). No se tocó persistencia.

---
tags:
  - xeon/operacion
---

# Colores del grafo por capa (Sonnet, 2026-10-26)

Estado: **código y notas listos; colores pendientes de aplicar** porque Obsidian estaba abierto (4 procesos `Obsidian.exe`; no se cerró). Verificación: `ruff check`, `ruff format --check`, `mypy src evals` y `pytest -q tests/test_graphify_map.py` en verde.

## Cambios

- `scripts/build_graphify_map.py`: `layer_for(source_file)` y `tag_generated_layers()` añaden `xeon-grafo/<capa>` al frontmatter y a la línea de etiquetas de cada nota generada; las notas puente llevan `xeon-grafo/puente`. Extracción y auditoría de secretos sin cambios.
- `scripts/apply_obsidian_graph_colors.py`: `LAYER_GROUPS` tras los ocho colores `xeon/*` (primeros, intactos), en ambas bóvedas.
- `tests/test_graphify_map.py`: caso representativo por capa. `docs/GRAPHIFY.md`: sección de colores.
- `graphify/INFERRED` sin grupo: es confianza de aristas (63 notas) y taparía el color de capa.

## Leyenda (2.164 notas generadas)

| Color | Etiqueta | Agrupa | Notas |
|---|---|---|---|
| #7986CB | `xeon-grafo/dominio` | `src/xeon/domain` | 92 |
| #66BB6A | `xeon-grafo/aplicacion` | `application` y `ports` | 128 |
| #E53935 | `xeon-grafo/agente` | `agent` y resto de `src/xeon` | 78 |
| #26C6DA | `xeon-grafo/adaptadores` | `adapters`, `connectors` | 171 |
| #1E88E5 | `xeon-grafo/api` | `api` | 28 |
| #C6FF00 | `xeon-grafo/canal` | `shell`, `cli.py` | 84 |
| #8D6E63 | `xeon-grafo/config` | `config.py`, YAML, pyproject, compose, Docker | 123 |
| #E040FB | `xeon-grafo/pruebas` | `tests` | 516 |
| #D84315 | `xeon-grafo/evaluacion` | `evals` | 503 |
| #9E9D24 | `xeon-grafo/scripts` | `scripts` | 67 |
| #80CBC4 | `xeon-grafo/docs` | `docs`, README y similares | 19 |
| #D7CCC8 | `xeon-grafo/wiki` | `wiki` | 34 |
| #757575 | `xeon-grafo/externo` | sin `source_file` (httpx, etc.) | 205 |
| #FAFAFA | `xeon-grafo/comunidad` | `_COMMUNITY_*` | 116 |
| #18FFFF | `xeon-grafo/puente` | `wiki/graph/*.md` (ganan por `xeon/hub`) | 6 |

Los ocho colores `xeon/*` y los dos extra de la raíz no cambian.

## Comandos

```powershell
uv run --locked --group graph python scripts/build_graphify_map.py   # hecho
uv run --locked python scripts/apply_obsidian_graph_colors.py        # pendiente: cerrar Obsidian antes
```

El usuario debe cerrar Obsidian y ejecutar el segundo comando.

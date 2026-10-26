---
tags:
  - xeon/operacion
---

# Integración local de Graphify

**Aporte:** Codex, 2026-10-26, por encargo del orquestador Claude Opus. **Estado:** implementación y verificaciones locales; integración de páginas compartidas pendiente del orquestador. **Páginas afectadas:** arquitectura-actual, contratos-herramientas, canal-kapso, xeon-cli, evaluacion-conversacional. Esta nota no reemplaza las síntesis existentes.

## Fuente y alcance

- Graphify `graphifyy==0.9.95`, tag `v0.9.95`, commit `92741d162b2094ffc2fed58cfbd8ee823e9da62c`.
- Licencia declarada: Apache-2.0; el repositorio también conserva `LICENSE-MIT` y `NOTICE` para aportes anteriores. Se revisaron [README](https://github.com/Graphify-Labs/graphify/tree/v0.9.95), `pyproject.toml`, licencias, `graphify/install.py`, `graphify/detect.py` y `graphify/export.py` antes de ejecutar Graphify.
- Sin llamada pagada ni extracción semántica: `GRAPHIFY_BACKEND=none`, `--code-only`, `--no-dedup`; costo real de LLM **0** y tokens enviados **0**.

## Comandos exactos

```powershell
uv sync --locked --group graph
uv run --locked --group graph python scripts/build_graphify_map.py --force
uv run --locked --group graph python scripts/build_graphify_map.py
uv run --locked --group graph graphify explain CommercialToolbelt
uv run --locked --group graph graphify path AgentService CreateQuoteDraft
uv run --locked --group graph graphify query "wiki/pages/canal-kapso.md" --budget 800
uv run --locked --group graph python scripts/check_doc_links.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
uv run --locked pytest
```

El script comprueba el corpus antes de invocar Graphify, ejecuta AST local en `.bootstrap/graphify-ast/`, añade nodos de archivo y enlaces Markdown deterministas, exporta `graphify-out/` y `wiki/graph/generated/`, y audita la salida. La actualización sin `--force` usa el manifiesto incremental AST; los enlaces documentales se recomputan localmente.

## Archivos creados o modificados

- `pyproject.toml`, `uv.lock`: grupo opcional `graph` fijado.
- `.graphifyignore`, `.gitignore`: exclusiones de entrada y artefactos grandes.
- `scripts/build_graphify_map.py`: construcción, puentes y auditoría.
- `docs/GRAPHIFY.md`: operación y límites.
- `.claude/skills/graphify/`: skill de Claude Code para Windows, referencias y licencias copiadas del tag fijado; aviso local de seguridad añadido.
- `wiki/graph/README.md` y cinco notas puente hacia `wiki/pages/`; `wiki/graph/generated/` contiene los nodos y canvas locales.
- `graphify-out/graph.json`, `GRAPH_REPORT.md`, `graph.html` y `xeon-audit.json`: generados localmente e ignorados por Git; aproximadamente 1,7 MB de JSON, 1,9 MB de HTML y más de 1.700 notas Obsidian. Se versionan solo insumos y puentes pequeños para evitar diffs enormes y artefactos con metadatos variables.

## Exclusiones y cobertura

`.graphifyignore` excluye `secrets/`, `.env*`, `video/`, `reports/`, `.venv/`, cachés y archivos multimedia. El detector no incluyó rutas protegidas en el corpus. La búsqueda `rg -l -i -- 'secrets[/\\]|\.env|(?:sk|gsk|xai|kapso)[-_][A-Za-z0-9]{20,}' graphify-out wiki/graph/generated` devolvió **0 archivos** tras construir, sin abrir ni comparar archivos secretos. La auditoría JSON registró **0 rutas protegidas, 0 menciones y 0 cadenas con formato de clave**.

**Estadísticas del grafo:** 1.623 nodos, 4.928 aristas, 90 comunidades y 194 archivos cubiertos (138 de código/configuración estructurada, 48 documentos y 8 archivos de configuración no clasificados por Graphify). La cobertura incluye `src`, `tests`, `evals`, `scripts`, `docs`, `wiki` y configuración. Graphify omitió 48 documentos en la fase semántica y el script los añadió como nodos/enlaces locales. El detector informó 24 entradas ignoradas, 30 directorios de ruido podados, 0 archivos sensibles saltados tras aplicar las reglas y 0 errores de recorrido; estas cifras son entradas del detector, no un conteo de todos los archivos físicos bajo directorios excluidos. Los documentos se representan por archivo y enlaces, sin conceptos semánticos extraídos.

## Límite y elección de fuente

| Necesidad | Fuente adecuada | Límite |
|---|---|---|
| Rastrear llamadas, imports y rutas entre símbolos | Grafo Graphify (`query`, `path`, `explain`) | Las aristas `INFERRED` requieren revisión; el grafo puede estar desactualizado hasta regenerar. |
| Entender decisiones, procedencia y estado implementado/planeado | `wiki/pages/` y documentos fuente | Es una síntesis editorial, no sustituye la ejecución o pruebas. |
| Confirmar una línea, condición o comportamiento preciso | `rg`, lectura directa del código y pruebas | Requiere seguir manualmente relaciones entre archivos. |

La extracción local de documentos solo modela archivos y enlaces explícitos. Para extraer semántica con un modelo haría falta una decisión posterior del usuario sobre proveedor, lista de archivos y estimación de tokens antes de ejecutarla. El grafo tampoco demuestra capacidades planeadas de XEON como PostgreSQL/pgvector o aprobación humana.

## Verificación (2026-10-26)

- `ruff check .`: limpio; `ruff format --check .`: 150 archivos ya formateados.
- `mypy src`: sin problemas en 53 archivos fuente.
- `pytest --tb=short`: 264 aprobadas, 2 omitidas. La primera ejecución dentro del sandbox produjo 37 `PermissionError` al preparar archivos temporales; una nueva ejecución con acceso normal terminó en verde.
- `scripts/check_doc_links.py`: 39 enlaces relativos revisados, 0 rotos.
- Consultas `explain CommercialToolbelt` y `path AgentService CreateQuoteDraft`: resueltas contra el JSON local; la ruta tiene dos saltos y ambos están marcados `INFERRED` por Graphify.

# Mapa local de XEON con Graphify

Graphify `graphifyy==0.9.95` está fijado en el grupo opcional `graph` de `pyproject.toml` y `uv.lock`. La fuente revisada fue el tag `v0.9.95`, commit `92741d162b2094ffc2fed58cfbd8ee823e9da62c`, bajo Apache-2.0; `LICENSE-MIT` cubre aportes anteriores. Se revisaron el README, `pyproject.toml`, `NOTICE`, las licencias, el instalador `graphify/install.py`, el detector y el exportador antes de ejecutar la herramienta. La skill de Claude para Windows está incluida en `.claude/skills/graphify/` con un aviso local de seguridad.

## Generar y actualizar

```powershell
uv sync --locked --group graph
uv run --locked --group graph python scripts/build_graphify_map.py --force
```

Después de cambios en el repositorio, el siguiente comando usa la detección incremental de Graphify para el AST y vuelve a construir los enlaces documentales locales:

```powershell
uv run --locked --group graph python scripts/build_graphify_map.py
```

El script fija `GRAPHIFY_BACKEND=none` en el subproceso y ejecuta `graphify extract . --code-only --no-dedup` con la salida AST intermedia en `.bootstrap/graphify-ast/`. Antes comprueba que el detector no incluyó rutas prohibidas. Después añade un nodo por archivo de código, documentación y configuración, más aristas `contains` y `links_to` derivadas de símbolos AST y enlaces Markdown explícitos. Los documentos no reciben extracción semántica: su contenido se lee localmente solo para resolver enlaces. Así quedan navegables los archivos de `src/`, `tests/`, `evals/`, `scripts/`, `docs/`, `wiki/` y la configuración reconocida. Los documentos no clasificados por Graphify reciben un nodo de archivo.

`.graphifyignore` excluye archivos sensibles, directorios de salida, medios, cachés y dependencias. La comprobación de salida rechaza rutas protegidas, menciones de rutas locales de credenciales y cadenas con formato de clave. La capa AST puede contener nodos o aristas `INFERRED`; los enlaces de archivos añadidos por XEON son `EXTRACTED` porque proceden del árbol de archivos o de enlaces Markdown escritos. Un enlace no demuestra que una afirmación de la wiki sea vigente: verifica el código y las pruebas para afirmaciones funcionales.

## Consultar

```powershell
uv run --locked --group graph graphify explain CommercialToolbelt
uv run --locked --group graph graphify path AgentService CreateQuoteDraft
uv run --locked --group graph graphify query "wiki/pages/canal-kapso.md" --budget 800
```

El reporte `graphify-out/GRAPH_REPORT.md`, el JSON `graphify-out/graph.json`, la vista `graphify-out/graph.html` y las notas Obsidian de `wiki/graph/generated/` se generan localmente. `wiki/graph/README.md` y sus cinco notas puente enlazan con las síntesis existentes de la wiki. Para navegar el grafo en Obsidian, abre la raíz del repositorio como bóveda y sigue `wiki/graph/README.md`.

El JSON y HTML miden aproximadamente 1,7 y 1,9 MB, y la exportación Obsidian genera más de 1.700 notas. Se ignoran en Git por tamaño y ruido de regeneración. Se versionan la dependencia fijada, las exclusiones, el script, la skill y los puentes pequeños. Un clon nuevo debe ejecutar el comando de generación para obtener el grafo. No se necesita una API ni hay costo de LLM en este flujo.

La skill upstream de `/graphify .` puede pedir extracción semántica de documentos a un modelo. En XEON, usa los comandos anteriores hasta que el usuario autorice expresamente un proveedor, alcance de archivos y presupuesto de tokens. El grafo local muestra estructura y enlaces; la wiki aporta decisiones, procedencia y estado, y la lectura directa con `rg` sirve para una línea o comportamiento exacto.

## Colores por capa en Obsidian

Al exportar, `scripts/build_graphify_map.py` añade a cada nota generada una etiqueta `xeon-grafo/<capa>` derivada de `source_file` (`layer_for`): `dominio`, `aplicacion` (incluye `ports`), `agente`, `adaptadores` (adapters y connectors), `api`, `canal` (shell y cli), `config`, `pruebas`, `evaluacion`, `scripts`, `docs`, `wiki`, `externo` (sin `source_file`, como `httpx`), `comunidad` (notas `_COMMUNITY_*`) y `puente` (notas de `wiki/graph/*.md`). `scripts/apply_obsidian_graph_colors.py` añade un grupo de color por etiqueta en ambas bóvedas, después de los ocho colores `xeon/*`, que conservan prioridad. No hay grupo para `graphify/INFERRED`: es la confianza de las aristas y taparía el color de capa de unas 60 notas. Aplica con Obsidian cerrado: `uv run --locked python scripts/apply_obsidian_graph_colors.py`.

## Hubs, mapa del proyecto y persistencia de colores

El script genera además `wiki/graph/mapa-proyecto.md` (raíz: wiki, documentos del repositorio y hubs) y una nota `hub-<capa>.md` por capa, con etiqueta `xeon-grafo/hub`. Cada hub enlaza todas las notas generadas de su capa y las páginas de la wiki que la describen; cada página de `wiki/pages` termina con un enlace a su hub y al mapa (`python scripts/build_graphify_map.py --link-wiki-pages`, idempotente, con `wiki/.write-lock`). `--orphans` cuenta las notas de `wiki/` sin enlaces entrantes ni salientes.

Obsidian guarda `graph.json` desde memoria, así que los colores solo persisten si se escriben sin la app abierta: 1) cierra Obsidian; 2) `uv run --locked python scripts/apply_obsidian_graph_colors.py` (imprime `N/N grupos de color` por bóveda); 3) abre Obsidian. La bóveda abierta por el usuario es `wiki/` (`%APPDATA%\obsidian\obsidian.json`). Con la app abierta, `--force` escribe el archivo, pero Obsidian puede sobrescribirlo al guardar su estado; el comando «Reload app without saving» recarga desde disco, sin verificar en esta máquina.

---
tags:
  - xeon/operacion
---

# Estructura y colores del grafo (Sonnet, 2026-10-26)

Estado: **hubs y enlaces implementados y verificados; colores escritos en ambos `graph.json`, pero Obsidian sigue abierto y puede sobrescribirlos** (ver pasos).

## Bóveda en uso

`%APPDATA%\obsidian\obsidian.json`: dos bóvedas; la marcada `open` es **`C:\Users\danie\Documents\xeon\wiki`** (la de la raíz del repo existe pero no está abierta). El grafo que ve el usuario es el de `wiki/`: no contiene `src/`, `docs/` ni README salvo como notas de `wiki/graph/generated/`, por eso los hubs y el mapa viven en `wiki/graph/`.

## Huérfanos (notas sin enlaces entrantes ni salientes, bóveda `wiki/`)

| Momento | Notas | Huérfanas |
|---|---|---|
| Antes (grafo regenerado, sin hubs) | 2.199 | 101 (docstrings y símbolos sueltos de `generated/`) |
| Después | 2.557+ | 1 (la nota abierta de agy en `wiki/inbox/`, sin enlaces) |

Comando: `uv run --locked --group graph python scripts/build_graphify_map.py --orphans`.

## Estructura creada

- `wiki/graph/mapa-proyecto.md` (`xeon/hub`): enlaza index, SCHEMA, log, sources, inbox, las 17 páginas, los 14 hubs y los documentos del repo (README, AGENTS, docs/*).
- `wiki/graph/hub-<capa>.md` (`xeon-grafo/hub`): dominio, aplicacion, agente, adaptadores, api, canal, config, pruebas, evaluacion, scripts, docs, wiki, externo y comunidad. Cada uno enlaza todas las notas de su capa y las páginas que la describen.
- Cada página de `wiki/pages` termina con `Grafo: [capa X](../graph/hub-X.md) · [mapa del proyecto](...)` (hecho con `--link-wiki-pages` bajo `wiki/.write-lock`).

## Colores

Los ocho `xeon/*` van primero (intactos), luego las 14 capas más `puente`, `comunidad` (ahora `#455A64`) y `hub` (`#FFFFFF`); la leyenda de capas está en `wiki/index.md` (el orquestador puede añadir hub y cambiar comunidad). El script imprime tras escribir: `wiki/.obsidian/graph.json: 24/24` y `.obsidian/graph.json: 26/26`. También fuerza `collapse-color-groups: false` para que se vean los grupos.

## Pasos para el usuario

1. Cierra Obsidian por completo.
2. `uv run --locked python scripts/apply_obsidian_graph_colors.py`
3. Abre Obsidian en la bóveda `wiki` y la vista de grafo.

Alternativa sin cerrar: ya se escribió el archivo con `--force`; tras 60 s seguía intacto (24 y 26 grupos), pero Obsidian lo reescribe al guardar su estado. Probar el comando «Reload app without saving» (paleta de comandos) lo recarga desde disco; **no se pudo verificar sin controlar la app**.

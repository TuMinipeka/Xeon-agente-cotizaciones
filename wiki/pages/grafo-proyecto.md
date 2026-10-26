---
tags:
  - xeon/operacion
---

# Grafo del proyecto (Graphify)

Mapa estructural local de XEON, generado con Graphify `graphifyy==0.9.95` (commit `92741d1`, Apache-2.0) e integrado por Codex en `07281a5`. Revisado por el orquestador el 2026-10-26. Estado: **`implementado`**. Operación: [`docs/GRAPHIFY.md`](../../docs/GRAPHIFY.md). Puentes hacia la wiki: [grafo en la wiki](../graph/README.md). Relacionado: [arquitectura actual](arquitectura-actual.md), [orquestación](orquestacion.md).

## Qué contiene

- **Tamaño:** 1.623 nodos, 4.928 aristas, 90 comunidades y 194 archivos de `src`, `tests`, `evals`, `scripts`, `docs`, `wiki` y configuración.
- **Origen:** AST local y enlaces Markdown explícitos. No hubo llamadas a modelos y el costo fue de USD 0.
- **Límite:** los documentos aparecen como archivos y enlaces, sin conceptos extraídos.
- **Exclusiones:** `secrets/`, `.env*`, `video/`, `reports/`, medios y cachés (`.graphifyignore`). El orquestador repitió el barrido de claves sobre la salida: 0 coincidencias.
- **Salidas no versionadas:** `graphify-out/` (`graph.json`, `GRAPH_REPORT.md`, `graph.html`) y `wiki/graph/generated/` (1.714 notas de Obsidian). Un clon nuevo debe regenerarlas.

## Qué herramienta usar (clasificación del orquestador)

| Pregunta | Herramienta | Por qué |
|---|---|---|
| ¿Qué decidimos, en qué estado está, de dónde sale? | **Wiki** (`index.md` y páginas) | Es la única con procedencia, decisiones y estado (`implementado` o `propuesta`) |
| ¿Dónde está X y qué lo usa o de qué depende? | **Grafo**: `graphify explain X` | Responde en una consulta con el archivo y la línea, sin abrir archivos |
| ¿Cómo llega una petición de A a B? | **Grafo**: `graphify path A B` | Muestra la cadena de llamadas o usos |
| ¿Qué toca un cambio en X (impacto, pruebas afectadas)? | **Grafo**: `explain` y `query` con `--budget` | Lista los vecinos y las pruebas conectadas |
| ¿Qué hace exactamente esta línea o condición? | **`rg` y lectura del rango** | El grafo no contiene la lógica |
| ¿Funciona de verdad? | **Pruebas y ejecución** | Ni el grafo ni la wiki prueban comportamiento |

**Regla de uso:** primero la wiki, después el grafo y, al final, la lectura puntual. Las aristas `INFERRED` se confirman en el código.

## Uso en Obsidian

Abre la raíz del repositorio como bóveda y entra por [grafo en la wiki](../graph/README.md). Las 1.714 notas generadas saturan la vista de grafo. Para ver solo la wiki, filtra con `-path:wiki/graph/generated`.

## Pendiente

- La extracción semántica de documentos con un modelo (skill `/graphify` completa) requiere la autorización del usuario: proveedor, archivos y presupuesto. La skill usa Gemini si existe `GEMINI_API_KEY`; si no, usa el agente anfitrión.
- La skill copiada sugiere `pip install graphifyy` sin versión. En XEON se usa el grupo fijado `uv --group graph`.

Grafo: [capa scripts](../graph/hub-scripts.md) · [mapa del proyecto](../graph/mapa-proyecto.md)

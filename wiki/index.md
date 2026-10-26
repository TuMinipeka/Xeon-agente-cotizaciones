---
tags:
  - xeon/hub
---

# Índice de la wiki XEON

Revisión: 2026-10-26. Comienza por el [estado del corte](pages/estado-del-corte.md) si buscas saber qué funciona hoy.

## Leyenda del grafo (Obsidian)

| Color | Tipo | Etiqueta o consulta | Páginas |
|---|---|---|---|
| Naranja `#FF8A65` | Decisiones | `#xeon/decision` | decisiones pendientes |
| Amarillo `#FFD54F` | Estado e hitos | `#xeon/estado` | estado del corte, hito S2 |
| Azul `#4FC3F7` | Arquitectura y contratos | `#xeon/arquitectura` | arquitectura actual, contratos |
| Jade `#00D9A3` | Interfaces y canales | `#xeon/interfaz` | canal Kapso, XEON CLI |
| Violeta `#B388FF` | Producto | `#xeon/producto` | qué es XEON, propuestas |
| Rosa `#F06292` | Operación de agentes | `#xeon/operacion` y `log.md` | orquestación, inbox, registro |
| Gris `#90A4AE` | Fuentes | `#xeon/fuente` y `raw/` | fuentes y material crudo |
| Menta `#6FFFD3` | Navegación | `#xeon/hub` | índice, README, esquema |

### Capas del grafo de código (Graphify)

Las notas de `wiki/graph/generated/` llevan una etiqueta `xeon-grafo/<capa>` derivada de `source_file` (`scripts/build_graphify_map.py`, `layer_for`). Los colores se añaden después de los ocho anteriores, que conservan prioridad. Cantidades de la regeneración del 2026-10-26 (2531 notas generadas; cambian con cada regeneración); la etiqueta `graphify/INFERRED` no tiene color porque tapa el de capa.

| Color | Etiqueta | Agrupa | Notas |
|---|---|---|---|
| `#7986CB` | `xeon-grafo/dominio` | `src/xeon/domain` | 92 |
| `#66BB6A` | `xeon-grafo/aplicacion` | `application` y puertos | 157 |
| `#E53935` | `xeon-grafo/agente` | `agent` y resto de `src/xeon` | 94 |
| `#26C6DA` | `xeon-grafo/adaptadores` | `adapters`, `connectors` | 188 |
| `#1E88E5` | `xeon-grafo/api` | `api` | 28 |
| `#C6FF00` | `xeon-grafo/canal` | `shell`, `cli.py` | 84 |
| `#8D6E63` | `xeon-grafo/config` | `config.py`, YAML, pyproject, compose | 166 |
| `#E040FB` | `xeon-grafo/pruebas` | `tests` | 584 |
| `#D84315` | `xeon-grafo/evaluacion` | `evals` | 616 |
| `#9E9D24` | `xeon-grafo/scripts` | `scripts` | 74 |
| `#80CBC4` | `xeon-grafo/docs` | `docs`, README y similares | 20 |
| `#D7CCC8` | `xeon-grafo/wiki` | `wiki` | 51 |
| `#757575` | `xeon-grafo/externo` | sin `source_file` (librerías como httpx) | 229 |
| `#455A64` | `xeon-grafo/comunidad` | notas `_COMMUNITY_*` | 148 |
| `#18FFFF` | `xeon-grafo/puente` | `wiki/graph/*.md` (prevalece `xeon/hub`) | 6 |
| `#FFFFFF` | `xeon-grafo/hub` | `mapa-proyecto` y `hub-<capa>.md` (el mapa lleva `xeon/hub`) | 14 |

Estado: aplicado en `graph.json` solo si se ejecutó el script con Obsidian cerrado; si no, queda pendiente.

En la bóveda de la raíz del repositorio también se colorean `docs/` (verde azulado `#26A69A`) y los archivos de instrucciones de la raíz (blanco menta `#EAFBF5`). Los grupos viven en `.obsidian/graph.json` de cada bóveda, que Git ignora; para reproducirlos en otra máquina, cierra Obsidian y ejecuta `uv run python scripts/apply_obsidian_graph_colors.py`. Con Obsidian abierto, la aplicación sobrescribe `graph.json` desde memoria y borra los grupos.

## Proyecto

- [Qué es XEON](pages/que-es-xeon.md) — problema, usuarios y relación con la venta ferretera.
- [Estado del corte](pages/estado-del-corte.md) — capacidades observadas y pendientes.
- [Hito S2](pages/hito-s2.md) — hoja de ruta S1–S4, trabajo delegado y hallazgos para la demo.
- [Propuestas de escalado](pages/propuestas-escalado.md) — ideas por eje con valor, dependencia y riesgo (no aprobadas).
- [Propuesta de la fase 3](pages/propuesta-fase3.md) — opciones A–E (persistencia, asesor y PDF, búsqueda híbrida, ERP REST, observabilidad), orden recomendado y preguntas para el usuario (propuesta, sin aprobar).

## Trabajo multi-agente

- [Orquestación](pages/orquestacion.md) — roles de Claude, Codex y agy en herdr; ciclo y reglas de commit.
- [Mapa del proyecto en el grafo](graph/mapa-proyecto.md) — nota raíz que enlaza la wiki, los documentos y una nota hub por capa del código.
- [Grafo del proyecto](pages/grafo-proyecto.md) — mapa Graphify del código y qué herramienta usar: wiki, grafo o lectura directa.
- [Canal Kapso](pages/canal-kapso.md) — WhatsApp oficial vía Kapso: decisiones, contrato del webhook y paso a paso.
- [XEON CLI](pages/xeon-cli.md) — shell interactivo `xeon`: comandos, alias, diseño neón y criterios.
- [Evaluación conversacional](pages/evaluacion-conversacional.md) — cliente simulado, oráculo, checks deterministas y regresiones (contrato).
- [Video HITO #2](pages/video-hito2.md) — decisiones, evidencia de herramientas, guion y reparto del video demostrativo.
- [Reporte QA de Conde](pages/qa-conde-2026-10-24.md) — 23 fallos conversacionales, 4 causas raíz, correcciones y corrida en vivo S16–S20.
- [Embudo de cotización](pages/embudo-cotizacion.md) — conversación guiada con botones y listas, políticas por ferretería y confirmación ante un asesor (D14, implementado; Kapso interactive sin verificar en sandbox).
- [Conector de la ferretería](pages/conector-ferreteria.md) — conectar XEON a la base de datos de cualquier ferretería (D13).
- [Auditoría 2026-10-24](pages/auditoria-2026-10-24.md) — comportamiento real confirmado, defectos E1–E6, incompleto, hipótesis y riesgos.
- [Contratos de herramientas](pages/contratos-herramientas.md) — `search_products`, `get_stock_by_branches`, `create_quote_draft`.

## Arquitectura

- [Arquitectura actual](pages/arquitectura-actual.md) — módulos y recorrido verificable del prototipo.

## Decisiones y mantenimiento

- [Decisiones pendientes](pages/decisiones-pendientes.md) — diferencias entre visión y código, con resolución por acordar.
- [Fuentes](sources.md) — procedencia y versiones observadas.
- [Esquema](SCHEMA.md) — instrucciones para agentes.
- [Capturas pendientes](inbox/README.md) — aportes de agentes aún no integrados.
- [Registro](log.md) — historial de ingestas y revisiones.

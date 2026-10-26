---
tags:
  - xeon/hub
---

# Índice de la wiki XEON

Revisión: 2026-10-24. Comienza por el [estado del corte](pages/estado-del-corte.md) si buscas saber qué funciona hoy.

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

En la bóveda de la raíz del repositorio también se colorean `docs/` (verde azulado `#26A69A`) y los archivos de instrucciones de la raíz (blanco menta `#EAFBF5`). Los grupos viven en `.obsidian/graph.json` de cada bóveda, que Git ignora; para reproducirlos en otra máquina, cierra Obsidian y ejecuta `uv run python scripts/apply_obsidian_graph_colors.py`. Con Obsidian abierto, la aplicación sobrescribe `graph.json` desde memoria y borra los grupos.

## Proyecto

- [Qué es XEON](pages/que-es-xeon.md) — problema, usuarios y relación con la venta ferretera.
- [Estado del corte](pages/estado-del-corte.md) — capacidades observadas y pendientes.
- [Hito S2](pages/hito-s2.md) — hoja de ruta S1–S4, trabajo delegado y hallazgos para la demo.
- [Propuestas de escalado](pages/propuestas-escalado.md) — ideas por eje con valor, dependencia y riesgo (no aprobadas).

## Trabajo multi-agente

- [Orquestación](pages/orquestacion.md) — roles de Claude, Codex y agy en herdr; ciclo y reglas de commit.
- [Grafo del proyecto](pages/grafo-proyecto.md) — mapa Graphify del código y qué herramienta usar: wiki, grafo o lectura directa.
- [Canal Kapso](pages/canal-kapso.md) — WhatsApp oficial vía Kapso: decisiones, contrato del webhook y paso a paso.
- [XEON CLI](pages/xeon-cli.md) — shell interactivo `xeon`: comandos, alias, diseño neón y criterios.
- [Evaluación conversacional](pages/evaluacion-conversacional.md) — cliente simulado, oráculo, checks deterministas y regresiones (contrato).
- [Video HITO #2](pages/video-hito2.md) — decisiones, evidencia de herramientas, guion y reparto del video demostrativo.
- [Reporte QA de Conde](pages/qa-conde-2026-10-24.md) — 23 fallos conversacionales, 4 causas raíz y su estado de corrección.
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

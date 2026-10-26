---
tags:
  - xeon/hub
---

# Mapa del proyecto XEON

Punto de entrada del grafo: enlaza la wiki, los documentos del repositorio y una nota por capa del código. Se regenera con `uv run --locked --group graph python scripts/build_graphify_map.py`.

## Wiki

- [index](../index.md)
- [SCHEMA](../SCHEMA.md)
- [log](../log.md)
- [sources](../sources.md)
- [inbox (capturas pendientes)](../inbox/README.md)
- [arquitectura-actual](../pages/arquitectura-actual.md)
- [auditoria-2026-10-24](../pages/auditoria-2026-10-24.md)
- [canal-kapso](../pages/canal-kapso.md)
- [conector-ferreteria](../pages/conector-ferreteria.md)
- [contratos-herramientas](../pages/contratos-herramientas.md)
- [decisiones-pendientes](../pages/decisiones-pendientes.md)
- [embudo-cotizacion](../pages/embudo-cotizacion.md)
- [estado-del-corte](../pages/estado-del-corte.md)
- [evaluacion-conversacional](../pages/evaluacion-conversacional.md)
- [grafo-proyecto](../pages/grafo-proyecto.md)
- [hito-s2](../pages/hito-s2.md)
- [orquestacion](../pages/orquestacion.md)
- [propuestas-escalado](../pages/propuestas-escalado.md)
- [qa-conde-2026-10-24](../pages/qa-conde-2026-10-24.md)
- [que-es-xeon](../pages/que-es-xeon.md)
- [video-hito2](../pages/video-hito2.md)
- [xeon-cli](../pages/xeon-cli.md)

## Capas del código

- [Capa dominio](hub-dominio.md)
- [Capa aplicacion](hub-aplicacion.md)
- [Capa agente](hub-agente.md)
- [Capa adaptadores](hub-adaptadores.md)
- [Capa api](hub-api.md)
- [Capa canal](hub-canal.md)
- [Capa config](hub-config.md)
- [Capa pruebas](hub-pruebas.md)
- [Capa evaluacion](hub-evaluacion.md)
- [Capa scripts](hub-scripts.md)
- [Capa docs](hub-docs.md)
- [Capa wiki](hub-wiki.md)
- [Capa externo](hub-externo.md)
- [Capa comunidad](hub-comunidad.md)

## Documentos del repositorio

- [README.md](generated/README.md)
- [AGENTS.md](generated/AGENTS.md)
- [CLAUDE.md](generated/CLAUDE.md)
- [GEMINI.md](generated/GEMINI.md)
- [CONTRIBUTING.md](generated/CONTRIBUTING.md)
- [docs/ARCHITECTURE.md](generated/docsARCHITECTURE.md)
- [docs/CAMBIOS_CONDE.md](generated/docsCAMBIOS_CONDE.md)
- [docs/CONECTOR_FERRETERIA.md](generated/docsCONECTOR_FERRETERIA.md)
- [docs/DESIGN.md](generated/docsDESIGN.md)
- [docs/DESPLIEGUE_WHATSAPP.md](generated/docsDESPLIEGUE_WHATSAPP.md)
- [docs/ENTREGA_HITO2.md](generated/docsENTREGA_HITO2.md)
- [docs/GLOSSARY.md](generated/docsGLOSSARY.md)
- [docs/GRAPHIFY.md](generated/docsGRAPHIFY.md)
- [docs/QA_EMBUDO.md](generated/docsQA_EMBUDO.md)
- [docs/QA_HITO2.md](generated/docsQA_HITO2.md)
- [docs/README.md](generated/docsREADME.md)
- [docs/VIDEO_HITO2.md](generated/docsVIDEO_HITO2.md)
- [docs/XeonContexto.md](generated/docsXeonContexto.md)

## Puentes

- [Grafo local de XEON](README.md)

# Wiki de XEON

Esta bóveda reúne conocimiento verificable sobre XEON para consulta y mantenimiento incremental. Está dentro del vault de Obsidian del repositorio: abre `wiki/index.md` para navegarla.

La wiki es una síntesis generada; los documentos y el código enlazados en [sources.md](sources.md) conservan la autoridad sobre los hechos. Cada afirmación de implementación debe poder seguirse hasta una fuente. Las capacidades deseadas se marcan como planificadas.

## Uso rápido

1. Empieza por [index.md](index.md).
2. Para incorporar una fuente, sigue [SCHEMA.md](SCHEMA.md) y registra el cambio en [log.md](log.md).
3. Si una fuente contradice una página, abre una decisión en [decisiones-pendientes.md](pages/decisiones-pendientes.md) antes de cambiar la interpretación.

Codex, Claude y Gemini comparten las reglas de [AGENTS.md](../AGENTS.md) mediante sus archivos de entrada del repositorio. Cada agente puede crear, modificar o retirar páginas de esta wiki; [SCHEMA.md](SCHEMA.md) define cómo conservar aportes de otras conversaciones y coordinar escrituras paralelas.

Las skills de agentes del proyecto se fijan en `skills-lock.json` (diseño de terminal y WhatsApp con Kapso). La antigua referencia `senior-architect-agent` se retiró en la limpieza D9.

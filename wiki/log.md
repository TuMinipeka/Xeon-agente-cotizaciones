# Registro de la wiki

## [2026-10-24] ingest | XEON y método de arquitectura

Se creó la bóveda a partir del encargo LLM Wiki, el documento funcional, la arquitectura, las convenciones, el README y puntos concretos del código. Se descargó `senior-architect-agent` en `references/` y se registró su commit. Se identificó la diferencia entre el recorrido de producto previsto y el prototipo en memoria; quedó abierta en [decisiones pendientes](pages/decisiones-pendientes.md). No se cambió el código de XEON.

## [2026-10-24] decisión | Wiki compartida entre agentes

Se incorporó el [encargo de colaboración](raw/colaboracion-agentes-2026-10-24.md) al esquema: registrar aportes sustantivos de cualquier conversación o CLI que opere en XEON, permitir crear/modificar/retirar páginas y coordinar escrituras paralelas mediante notas individuales y exclusión local. `AGENTS.md`, `CLAUDE.md` y `GEMINI.md` enlazan esta política para sesiones nuevas.

## [2026-10-24] ingest | Orquestación multi-agente

Se ingresó `wiki/orquestacion.md` como fuente S9, conservada literalmente en `raw/orquestacion-original-2026-10-24.md`, y se retiró de la raíz.

- **Página adaptada:** [orquestación](pages/orquestacion.md).
- **Decisiones del usuario:**
  - Claude Opus es el orquestador principal en herdr, con Codex como desarrollador y agy como QA.
  - Se migra a Grok (D3).
  - El Sandbox de Plática se ignora.
  - `/vault` se mapea a la wiki.
  - Commits `Type: :gitmoji: ActionInUpperCamelCase` en inglés, con `gh` y sin atribución de agentes.
- **Páginas nuevas:** [hito S2](pages/hito-s2.md), [contratos de herramientas](pages/contratos-herramientas.md) y [propuestas de escalado](pages/propuestas-escalado.md). Esta última es la lluvia de ideas previa, como propuesta y con afirmaciones sin fuente retiradas.
- **Decisiones registradas:** D3 a D6 en [decisiones pendientes](pages/decisiones-pendientes.md).
- **Repositorio:** `AGENTS.md` recibe la regla de commits.
- **Límite:** no se cambió código; el trabajo de Grok y de QA quedó delegado.

## [2026-10-24] integración | Entregas de Codex y agy

Se integraron las notas de inbox `2026-10-24T-codex-grok-provider.md` y `2026-10-24T-agy-qa-s2.md` y se retiraron de `inbox/`.

- **Codex:** perfil `grok` implementado (D3 avanzada) y helper `_require_api_key` sin duplicación.
- **agy:** `tests/test_multiturn_context.py`, con los defectos QA1 a QA3 fijados como `xfail` estrictos, y el guion de demo en [hito S2](pages/hito-s2.md).
- **Auditoría del orquestador:** ruff y mypy en verde; pytest con 93 aprobadas y 3 `xfail`. Las opciones de la CLI del guion se verificaron con `--help`.
- **Coordinación:** herdr marcó a agy como `blocked` por un diálogo de permiso de escritura que se resolvió en su panel; el orquestador no respondió el diálogo.
- **Páginas actualizadas:** [hito S2](pages/hito-s2.md), [decisiones pendientes](pages/decisiones-pendientes.md) (D3 y D6) y [estado del corte](pages/estado-del-corte.md).

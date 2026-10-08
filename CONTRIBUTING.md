# Contribuir a XEON

## Rama de trabajo

`main` debe permanecer ejecutable. El arranque solicitado se desarrolla en `developer/daniel`m o `developer/nombre_desarrollador`.
Para tareas posteriores, crear ramas cortas desde ella o desde `main` cuando el equipo acuerde la
integración.

## Commits convencionales del proyecto

Formato obligatorio:

```text
Type: :emoji: ActionInCamelCase
```

Tipos permitidos: `Feat`, `Fix`, `Docs`, `Test`, `Refactor`, `Chore`, `Ci`.

Ejemplos:

```text
Feat: :sparkles: ImplementsDoneInTheProject
Fix: :bug: RejectsUnknownStockState
Docs: :memo: ExplainsGrokSeparation
Test: :test_tube: CoversMockEndToEndFlow
```

El asunto no lleva espacios ni punto final. Se usa la inicial mayúscula siguiendo el ejemplo
acordado y se mantiene una acción concreta. Cada commit debe ser revisable y no contener secretos.

## Verificaciones

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

La prueba real de Grok no forma parte de la suite normal. Debe ejecutarse de forma explícita, con
clave local, presupuesto acordado y sin registrar mensajes sensibles.


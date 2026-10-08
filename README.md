# XEON

Base inicial del agente de asistencia comercial y cotizaciones descrito en
[`XeonContexto.md`](XeonContexto.md). Esta entrega fija Python 3.14.8, arquitectura hexagonal,
configuración segura, un flujo conversacional mínimo y ejecución reproducible en Docker.

## Arranque sin consumo de Grok

```powershell
docker compose --profile core up --build
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/chat `
  -ContentType 'application/json' -Body '{"message":"hola"}'
```

La API queda disponible en `http://127.0.0.1:8000` y su OpenAPI en `/docs`. El perfil inicial usa
`MockLLM`: prueba el recorrido completo sin llamar a un servicio pagado.

## Desarrollo local

Se requiere `uv`; este puede instalar y administrar Python 3.14.8 aunque el Python global de
Windows sea diferente.

```powershell
uv python install 3.14.8
uv sync --locked
uv run ruff check .
uv run mypy src
uv run pytest
uv run uvicorn xeon.api.app:app --reload
```

## Grok

El adaptador usa un contrato OpenAI-compatible con `grok-4.6`. La clave nunca se versiona. Antes de
activar una prueba real, rota cualquier clave expuesta y sigue
[`docs/GROK_DEVELOPMENT.md`](docs/GROK_DEVELOPMENT.md).

## Documentación de continuidad

- [`AGENTS.md`](AGENTS.md): instrucciones estables para Grok u otros agentes de código.
- [`docs/ROADMAP_FIRST_3_DAYS.md`](docs/ROADMAP_FIRST_3_DAYS.md): corte ejecutable de tres días.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): límites implementados y siguientes componentes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rama, pruebas y formato de commits.

Estado actual: base conversacional, no cotizador productivo. Todavía no existen persistencia,
catálogo, reglas comerciales, aprobación, Telegram, PDF ni LangGraph.

# XEON

Base inicial del agente de asistencia comercial y cotizaciones descrito en
[`XeonContexto.md`](XeonContexto.md). Esta entrega fija Python 3.14.8, arquitectura hexagonal,
configuración segura, un flujo conversacional mínimo, un cotizador determinista en memoria y
ejecución reproducible en Docker.

## Arranque sin consumo de Grok

```powershell
docker compose --profile core up --build
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/chat `
  -ContentType 'application/json' -Body '{"message":"hola"}'
$body = @{
  tenant_id = "demo"
  request_id = "req-1"
  lines = @(
    @{ query = "CEM-50"; quantity = "50" }
    @{ query = "ALA-14"; quantity = "300" }
  )
} | ConvertTo-Json -Depth 5
$created = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/quotes `
  -ContentType 'application/json' -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/v1/quotes/$($created.quote.id)?tenant_id=demo"
```

La API queda en `http://127.0.0.1:8000` (loopback) y su OpenAPI en `/docs`. El perfil inicial
usa `MockLLM`: no llama a un servicio pagado. El chat no calcula precios.

## CLI de revisión

```powershell
uv run xeon quotes create --tenant-id demo --request-id req-1 --line CEM-50:50 --line ALA-14:300
uv run xeon quotes show <quote-id> --tenant-id demo
```

Esos comandos crean o reutilizan un borrador `DRAFT` version 1. No aprueban ni emiten.

## Desarrollo local

Se requiere `uv`; este puede instalar y administrar Python 3.14.8 aunque el Python global de
Windows sea diferente.

```powershell
uv python install 3.14.8
uv sync --locked
uv run ruff check .
uv run mypy src
uv run pytest
uv run uvicorn xeon.api.app:app --reload --host 127.0.0.1
```

## Grok

El adaptador usa un contrato OpenAI-compatible con `grok-4.6`. La clave nunca se versiona. Antes de
activar una prueba real, rota cualquier clave expuesta y sigue
[`docs/GROK_DEVELOPMENT.md`](docs/GROK_DEVELOPMENT.md).

## Coordinacion autonoma de desarrollo

El comando `xeon-coordinate` separa a Grok como ejecutor y a Codex como coordinador de calidad.
Cada ciclo procesa una HU, verifica el diff y repite `ruff`, `mypy` y `pytest`; no hace push ni
fusiona ramas.

```powershell
# Crea la orden local de una HU (agrega todos sus criterios y rutas permitidas).
uv run xeon-coordinate new --story-id HU-001 --title "TituloDeLaHistoria" `
  --objective "Resultado observable esperado para esta historia." `
  --criterion "AC-1=Comportamiento verificable de al menos cinco caracteres." `
  --allowed-path "src/xeon/**" --allowed-path "tests/**"

# Ensayo sin consumo; agrega --execute solo tras revisar la orden.
uv run xeon-coordinate run .agentic/work-orders/HU-001-run.json
```

La configuracion, los limites y los artefactos del ciclo se explican en
[`docs/AGENTIC_COORDINATION.md`](docs/AGENTIC_COORDINATION.md).

## Documentación de continuidad

- [`AGENTS.md`](AGENTS.md): instrucciones estables para Grok u otros agentes de código.
- [`GLOSSARY.md`](GLOSSARY.md): lenguaje comercial del cotizador.
- [`docs/ROADMAP_FIRST_3_DAYS.md`](docs/ROADMAP_FIRST_3_DAYS.md): corte ejecutable de tres días.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): límites implementados, trazabilidad y pendientes.
- [`docs/AGENTIC_COORDINATION.md`](docs/AGENTIC_COORDINATION.md): protocolo Codex–Grok por HU.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rama, pruebas y formato de commits.

## Estado

Implementado: chat mock, cotizador determinista, API/CLI de borrador sintético, idempotencia
`tenant_id` + `request_id`, aclaración explícita y rechazo de descuento sin política.

Pendiente: PostgreSQL, LangGraph, Telegram, Celery, PDF, aprobación y política de descuentos.
No atribuir datos sintéticos a una empresa real.

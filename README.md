# XEON

Base inicial del agente de asistencia comercial y cotizaciones descrito en
[`XeonContexto.md`](XeonContexto.md). Esta entrega fija Python 3.14.8, arquitectura hexagonal,
configuración segura, un flujo conversacional mínimo, un cotizador determinista en memoria y
ejecución reproducible en Docker.

## Requisitos

- Python 3.14.8 (lo puede instalar y administrar `uv`, aunque el Python global de Windows sea otro)
- [`uv`](https://docs.astral.sh/uv/)
- Docker (Compose v2) para el arranque empaquetado

## Arranque Docker con mock (sin consumo de Grok)

El perfil predeterminado usa `MockLLM`: no llama a un servicio pagado. El chat no calcula precios.

```powershell
docker compose --profile core up --build
```

La API queda en `http://127.0.0.1:8000` (loopback) y su OpenAPI en `/docs`.

```powershell
docker compose --profile core down
```

## Arranque local con mock

```powershell
uv python install 3.14.8
uv sync --locked
uv run uvicorn xeon.api.app:app --reload --host 127.0.0.1
```

`LLM_PROVIDER` no definido o `mock` mantiene cero llamadas externas.

## Grok local con `RETO_KEY_FILE`

La clave nunca se versiona ni se pega en comandos. Apunta a un archivo secreto local e activa el
proveedor solo para esa sesión:

```powershell
$env:LLM_PROVIDER = "grok"
$env:RETO_KEY_FILE = "secrets/reto_key.txt"
uv run uvicorn xeon.api.app:app --reload --host 127.0.0.1
```

Antes de una prueba real, rota cualquier clave expuesta y sigue
[`docs/GROK_DEVELOPMENT.md`](docs/GROK_DEVELOPMENT.md).

## Grok en Docker

```powershell
docker compose --profile core -f compose.yaml -f compose.grok.yaml up --build
```

Para detener el stack Grok usa los mismos archivos:

```powershell
docker compose --profile core -f compose.yaml -f compose.grok.yaml down
```

`compose.grok.yaml` inyecta `LLM_PROVIDER=grok` y monta el secreto como archivo; no copies la clave
al entorno ni al compose.

## CLI

El CLI habla con la API en `http://127.0.0.1:8000`. Arranca mock o Grok antes de usarlo.

```powershell
uv run xeon health
uv run xeon chat "hola"
$created = uv run xeon quotes create --tenant-id demo --request-id req-1 --line CEM-50:50 --line ALA-14:300 | ConvertFrom-Json
$quoteId = $created.quote.id
uv run xeon quotes show $quoteId --tenant-id demo
uv run xeon stock show --sku CEM-50 --requested-branch-id sede-norte --evaluated-at 2026-10-08T15:00:00+00:00
uv run xeon stock show --sku CEM-50 --requested-branch-id sede-norte --requested-quantity 50 --evaluated-at 2026-10-08T15:00:00+00:00
```

`$quoteId` sale del campo `quote.id` que devuelve `quotes create`. `quotes create` crea o reutiliza
un borrador `DRAFT` version 1; `quotes show` solo lo consulta. Ninguno aprueba ni emite.
`stock show` consulta disponibilidad sintetica por sede; no reserva inventario.
`--evaluated-at` es obligatorio: instante UTC inyectado para clasificar vigencia; las pruebas no
usan el reloj real. Cada item expone `valid_until` (vigencia explicita de la fuente, o nulo),
`freshness` (`fresh` / `stale` / `unknown`), `is_firm` y `age` (antiguedad ISO-8601 desde
`observed_at`). Solo `fresh` es disponibilidad firme; `stale` y `unknown` conservan origen,
cantidad, fuente, fecha observada y vigencia, pero no prometen stock ni se usan para afirmar
`sufficient` o `partial`. Con `--requested-quantity` informa cumplimiento local y alternativas
observadas; no suma fuentes como promesa ni convierte un snapshot ausente o vencido en agotado.

Equivalente HTTP del arranque mock:

```powershell
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
curl "http://127.0.0.1:8000/v1/stock?sku=CEM-50&requested_branch_id=sede-norte&requested_quantity=50&evaluated_at=2026-10-08T15:00:00%2B00:00"
```

OpenAPI interactivo: `http://127.0.0.1:8000/docs`.

## Agente comercial vs `xeon-coordinate`

El **agente comercial** (runtime XEON) interpreta lenguaje del cliente por `/v1/chat`. El backend
determina precios, descuentos, impuestos, stock y estados. El modelo no aprueba cotizaciones, no
ejecuta SQL, no cambia inventario y no lee secretos.

`xeon-coordinate` es tooling de desarrollo, no el runtime comercial. Separa a Grok como ejecutor de
una HU y a Codex como coordinador de calidad. Cada ciclo verifica el diff y repite `ruff`, `mypy` y
`pytest`; no hace push ni fusiona ramas.

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

## Controles

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Diagnostico

1. **Puerto.** Compose publica solo `127.0.0.1:8000`. Si el bind falla, otro proceso ocupa el
   puerto; detén el stack (`docker compose --profile core down`) o el `uvicorn` local antes de
   reintentar.
2. **Health.** `uv run xeon health` o `GET /health` debe responder 200. Sin eso, chat, quotes y
   stock no tienen API detrás.
3. **Perfil.** En mock, `/health` y el chat confirman `provider=mock` (cero llamadas externas). Una
   prueba Grok deliberada debe mostrar `provider=grok`. No actives Grok para revisar el cotizador.

## Documentación de continuidad

- [`AGENTS.md`](AGENTS.md): instrucciones estables para Grok u otros agentes de código.
- [`GLOSSARY.md`](GLOSSARY.md): lenguaje comercial del cotizador.
- [`docs/ROADMAP_FIRST_3_DAYS.md`](docs/ROADMAP_FIRST_3_DAYS.md): corte ejecutable de tres días.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): límites implementados, trazabilidad y pendientes.
- [`docs/AGENTIC_COORDINATION.md`](docs/AGENTIC_COORDINATION.md): protocolo Codex–Grok por HU.
- [`docs/GROK_DEVELOPMENT.md`](docs/GROK_DEVELOPMENT.md): Grok de codigo vs Grok dentro de XEON.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rama, pruebas y formato de commits.

## Estado

Implementado: chat mock, cotizador determinista, API/CLI de borrador sintético, idempotencia
`tenant_id` + `request_id`, aclaración explícita, rechazo de descuento sin política, consulta de
stock sintético por sede (`local` / traslado / entrega), vigencia de snapshots
(`fresh` / `stale` / `unknown`, `is_firm`, `age`) y explicación de disponibilidad
parcial (`sufficient` / `partial` / `unknown`) y perfiles `mock` / `grok`.

Pendiente: PostgreSQL, LangGraph, Telegram, Celery, PDF, aprobación y política de descuentos.
No atribuir datos sintéticos a una empresa real.

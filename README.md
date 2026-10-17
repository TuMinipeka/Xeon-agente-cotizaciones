# XEON

Base del agente de asistencia comercial y cotizaciones para ferreterías y agroferreterías descrito
en [`XeonContexto.md`](XeonContexto.md). Esta entrega fija Python 3.14.8, arquitectura hexagonal,
orquestación con **Hermes**, proveedor **Groq API**, canal **WhatsApp vía Evolution API** (sin costo
por mensaje) y un modelo de datos híbrido (**SQL Relacional + NoSQL `JSONB` + RAG Semántico**).

## Requisitos

- Python 3.14.8 (administrado por `uv`)
- [`uv`](https://docs.astral.sh/uv/)
- Docker (Compose v2) para el arranque empaquetado

## Usar XEON paso a paso

Esta es la ruta recomendada para probar el agente comercial sin consumir la API de Groq. Todos
los comandos se ejecutan en PowerShell desde la raiz del repositorio:
`C:\Users\danie\Documents\xeon`.

### 1. Abrir el proyecto y comprobar la rama

```powershell
cd C:\Users\danie\Documents\xeon
git branch --show-current
```

La rama de desarrollo debe ser `developer/daniel`; no ejecutes trabajo de desarrollo directamente
en `main`.

### 2. Preparar Python y las dependencias

```powershell
uv python install 3.14.8
uv sync --locked
```

### 3. Iniciar la API en modo seguro `mock`

En la primera terminal:

```powershell
$env:LLM_PROVIDER = "mock"
uv run uvicorn xeon.api.app:app --reload --host 127.0.0.1 --port 8000
```

### 4. Comprobar que XEON está disponible

Abre una segunda terminal en la misma carpeta y ejecuta:

```powershell
uv run xeon health
```

### 5. Conversar con el agente (Hermes + Búsqueda Híbrida RAG/Specs)

```powershell
uv run xeon chat "hola"
uv run xeon chat "busco material para fundir placa y pegar ladrillo"
uv run xeon chat "necesito algo para cercar ganado en un potrero"
```

`/v1/chat` ejecuta las herramientas de **Hermes** (`HermesToolbelt`): ante descripciones coloquiales
o especificaciones técnicas, busca candidatos por contexto semántico (RAG) y atributos polimórficos
(`specs`), y consulta el precio oficial (`Decimal`) en el catálogo estructurado sin inventar datos.

### 6. Simular un mensaje entrante de WhatsApp (Evolution API Webhook)

```powershell
$webhook = @{
  event = "messages.upsert"
  instance = "xeon-ferreteria"
  data = @{
    key = @{
      remoteJid = "573001112233@s.whatsapp.net"
      fromMe = $false
      id = "MSG-001"
    }
    message = @{
      conversation = "tuberia para agua fria de 200 psi"
    }
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/channels/whatsapp/webhook `
  -ContentType 'application/json' -Body $webhook
```

### 7. Crear y consultar un borrador de cotización

```powershell
$created = uv run xeon quotes create `
  --tenant-id demo `
  --request-id req-1 `
  --line CEM-50:50 `
  --line ALA-14:300 | ConvertFrom-Json

$quoteId = $created.quote.id
uv run xeon quotes show $quoteId --tenant-id demo
```

### 8. Consultar inventario y su vigencia

```powershell
uv run xeon stock show `
  --sku CEM-50 `
  --requested-branch-id sede-norte `
  --requested-quantity 50 `
  --evaluated-at 2026-10-08T15:00:00+00:00
```

### 9. Ejecutar los controles de calidad

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

### 10. Probar el puente con Hermes local (`LLM_PROVIDER=hermes`, modelo temporal)

Hermes está configurado en `C:\Users\danie\AppData\Local\hermes\config.yaml` con su servidor API
local (`http://127.0.0.1:8642/v1`) y usa temporalmente su modelo interno (`gpt-5.6-luna` / `openai-codex`).
Como XEON se comunica con Hermes por el puerto estándar `/v1/chat/completions`, puedes cambiar el
modelo dentro de Hermes en cualquier momento sin tocar el código de XEON:

```powershell
# 1. En una terminal de Hermes, iniciar el gateway local (:8642/v1)
hermes gateway run

# 2. En otra terminal de XEON, apuntar al runtime de Hermes
$env:LLM_PROVIDER = "hermes"
uv run python scripts/simulate_whatsapp_webhook.py --provider hermes
```

### 11. Conectar WhatsApp sin costo ($0) mediante Evolution API (Baileys QR)

Evolution API usa el motor **Baileys** (vinculación por código QR, igual que WhatsApp Web) para
automatizar WhatsApp sin pagar tarifas por mensaje de Meta Cloud API:

```powershell
# 1. Levantar XEON + Evolution API (con PostgreSQL y Redis para persistir la sesion QR)
docker compose --profile core -f compose.yaml -f compose.evolution.yaml up -d --build

# 2. Aprovisionar la instancia 'xeon-ferreteria', configurar el webhook y generar el codigo QR
uv run python scripts/setup_evolution_whatsapp.py

# 3. Escanear el archivo qr_whatsapp.png (o abrir http://127.0.0.1:8080/manager) desde tu WhatsApp
#    (Configuracion -> Dispositivos vinculados -> Vincular un dispositivo)
```

Para simular un mensaje entrante de WhatsApp sin necesidad de tener Docker encendido:

```powershell
uv run python scripts/simulate_whatsapp_webhook.py --provider mock
```

### 12. Activar Groq directo solo para una prueba deliberada

Guarda tu clave en `secrets/groq_api_key.txt` (nunca en `.env` ni en Git):

```powershell
$env:LLM_PROVIDER = "groq"
$env:GROQ_API_KEY_FILE = "secrets/groq_api_key.txt"
uv run uvicorn xeon.api.app:app --reload --host 127.0.0.1 --port 8000
```

En Docker:

```powershell
docker compose --profile core -f compose.yaml -f compose.groq.yaml up --build
```

## Documentación de continuidad

- [`docs/index.md`](docs/index.md): portada navegable para abrir el repositorio como bóveda de
  Obsidian. En Obsidian, selecciona **Open folder as vault** y abre la raíz del repositorio; no la
  carpeta anidada `Xeon/`.
- [`XeonContexto.md`](XeonContexto.md): especificación funcional, base de datos híbrida y stack.
- [`AGENTS.md`](AGENTS.md): instrucciones estables para agentes de código.
- [`GLOSSARY.md`](GLOSSARY.md): lenguaje comercial del cotizador.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): límites implementados, trazabilidad y pendientes.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rama, pruebas y formato de commits.

## Estado

Implementado: orquestación base de **Hermes** (`HermesToolbelt` + puente `LLM_PROVIDER=hermes` hacia
el API Server local de Hermes en `:8642/v1`), búsqueda híbrida de candidatos (exacta + contexto
semántico RAG + atributos polimórficos `specs`), adaptador de canal **WhatsApp vía Evolution API**
(`POST /v1/channels/whatsapp/webhook`, envío `sendText`, stack `compose.evolution.yaml` en modo
Baileys QR $0 y scripts de simulación/aprovisionamiento), cotizador determinista `DRAFT` con
`Decimal`, idempotencia `tenant_id` + `request_id`, consulta de stock por sede con vigencia
(`fresh` / `stale` / `unknown`) y perfiles `mock` / `hermes` / `groq`.

Pendiente: persistencia PostgreSQL 17 (`SQL + JSONB + pgvector`) con Alembic, PDF y aprobación
humana. No atribuir datos sintéticos a una empresa real.

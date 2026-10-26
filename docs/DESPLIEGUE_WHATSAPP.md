# Desplegar XEON en WhatsApp con Kapso

Guía paso a paso para dejar XEON respondiendo por WhatsApp (API oficial vía Kapso) con Grok y
probar el bot desde un teléfono. Los comandos son para **PowerShell en Windows** y se ejecutan
desde la raíz del repositorio salvo que se indique otra carpeta.

```text
Teléfono (WhatsApp) ──> Kapso (sandbox) ──webhook firmado──> túnel cloudflared
        ^                                                        │
        └──── respuesta (API oficial de Meta vía Kapso) <── XEON API :8000 (Grok)
```

> [!IMPORTANT]
> Las claves nunca se pegan en el chat, en commits ni en capturas. Viven solo en `.env` y en
> `secrets/`, ambos ignorados por Git.

## 1. Requisitos (una sola vez)

| Herramienta | Comprobar | Instalar |
|---|---|---|
| `uv` + Python 3.14.8 | `uv --version` | `winget install --id astral-sh.uv -e`, luego `uv python install 3.14.8` |
| Node.js 20+ (scripts de Kapso) | `node --version` | `winget install --id OpenJS.NodeJS.LTS -e` |
| `cloudflared` (túnel HTTPS) | `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" --version` | `winget install --id Cloudflare.cloudflared -e` |
| Cuenta de Kapso | [app.kapso.ai](https://app.kapso.ai) | Plan gratis: sandbox y 2.000 mensajes/mes |
| Clave de la pasarela Grok del reto | — | La entrega el equipo |

## 2. Preparación (una sola vez)

### 2.1. Código y dependencias

```powershell
git switch developer/daniel
git pull
uv sync --locked
```

### 2.2. Secretos y configuración

1. Crea `secrets/grok_api_key.txt` y pega **a mano** la clave de la pasarela Grok (una sola línea).
2. Crea `.env` desde la plantilla:

   ```powershell
   Copy-Item .env.example .env
   ```

3. En [app.kapso.ai](https://app.kapso.ai) crea una **clave de API** y pégala **a mano** en `.env`:
   `KAPSO_API_KEY=<tu clave>`.
4. En `.env`, activa el envío de respuestas: `WHATSAPP_SEND_ENABLED=true`.

### 2.3. Skills de Kapso (diagnóstico y descubrimiento)

```powershell
npx skills add gokapso/agent-skills
cd .agents\skills\integrate-whatsapp; npm i; cd ..\observe-whatsapp; npm i; cd ..\..\..
```

### 2.4. Obtener el `phone_number_id` del sandbox

```powershell
cd .agents\skills\integrate-whatsapp
node --env-file=..\..\..\.env scripts\list-platform-phone-numbers.mjs
cd ..\..\..
```

En la salida, busca el número con `"kind": "sandbox"` y copia su `phone_number_id` en `.env`:
`KAPSO_PHONE_NUMBER_ID=<id>`.

> `--env-file` carga la clave desde `.env` sin mostrarla en la terminal.

## 3. Arranque (cada sesión de pruebas)

Necesitas **tres terminales**, todas en la raíz del repositorio.

### Terminal 1: API de XEON

```powershell
uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000
```

### Terminal 2: túnel público

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8000
```

Copia la URL `https://<algo>.trycloudflare.com` que aparece en la salida. **Cambia cada vez que
reinicias el túnel.**

### Terminal 3: conectar Kapso con el túnel

Con las terminales 1 y 2 en marcha, ejecuta **un solo comando**:

```powershell
uv run python scripts/kapso_webhook.py sync-tunnel
```

El comando hace todo sin que copies nada:

1. Lee la URL actual del túnel desde `cloudflared` (puerto local de métricas `20241`-`20245`).
2. Toma el `phone_number_id` de `KAPSO_PHONE_NUMBER_ID` en `.env`.
3. Busca el webhook de ese número en Kapso:
   - **Si existe**, actualiza su URL a `https://<túnel>/v1/channels/whatsapp/kapso/webhook`.
   - **Si no existe** (primera vez), lo crea, genera el secreto en
     `secrets/kapso_webhook_secret.txt` y lo registra.
4. Imprime la URL final y el `webhook_id`. Nunca muestra claves ni secretos.

Salida esperada:

```text
HTTP 200
url: https://<algo>.trycloudflare.com/v1/channels/whatsapp/kapso/webhook
webhook_id: <id>
```

**Repite este comando cada vez que reinicies el túnel**, porque la URL cambia.

Variantes (normalmente no hacen falta):

```powershell
# Pasar la URL del túnel a mano (si cloudflared no expone el puerto de métricas)
uv run python scripts/kapso_webhook.py sync-tunnel --tunnel-url https://<algo>.trycloudflare.com
# Ver los webhooks registrados del número
uv run python scripts/kapso_webhook.py list --phone-number-id <ID_SANDBOX>
```

> El `create.js` de la skill de Kapso no envía el secreto del webhook y la API lo rechaza
> («Secret key can't be blank»). Por eso XEON trae `scripts/kapso_webhook.py`.

## 4. Verificar antes de usar el teléfono

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe https://<algo>.trycloudflare.com/health
```

Ambos deben responder `"provider":"grok","model":"grok-4.6"`. Si dice `mock`,
revisa `LLM_PROVIDER` en `.env`.

Prueba local de un mensaje firmado. Con `WHATSAPP_SEND_ENABLED=true`, el envío al número ficticio
fallará en Kapso; la prueba solo confirma que la firma y el procesamiento funcionan.

```powershell
uv run python scripts/simulate_whatsapp_webhook.py --phone-number-id <ID_SANDBOX> --message "necesito 2 bultos de cemento"
```

Respuesta esperada: `{"status":"processed"}`. Una petición sin firma debe dar `401`.

## 5. Probar el bot desde WhatsApp

> [!NOTE]
> **Embudo guiado activo (D14):** Las respuestas de XEON en WhatsApp ahora utilizan **mensajes interactivos** (botones de respuesta rápida y listas interactivas) según el contrato D14. El agente guía al cliente paso a paso (`inicio` → `producto` → `cantidad` → `mas` → `entrega` → `sede` → `pago` → `resumen` → `confirmado`).
> Para la guía de prueba manual exhaustiva con los 6 recorridos detallados (R1 a R6), consulta [`docs/QA_EMBUDO.md`](QA_EMBUDO.md).

1. En [app.kapso.ai](https://app.kapso.ai) abre **Sandbox** y copia el número y el **código de
   activación**.
2. Desde tu WhatsApp, envía ese código al número del sandbox para unirte.
3. Conversa con XEON. El flujo avanza de forma guiada:

| Paso / Mensaje | Qué debe pasar en WhatsApp |
|---|---|
| `hola` | Inicia el embudo: responde «¿Qué necesitas?» y muestra opciones (`[Cotizar productos]`, `[Proyecto u obra]`, `[Hablar con asesor]`). |
| Pulsa `[Cotizar productos]` | Pide nombre o referencia: «¿Qué producto buscas? Escribe nombre o referencia.» |
| Escribe `cemento` | Busca en el catálogo y muestra una lista interactiva con referencias coincidentes (ej. `Cemento gris 50 kg`). |
| Selecciona `Cemento gris 50 kg` | Pregunta cantidad deseada y ofrece botones sugeridos (`[10]`, `[20]`, `[Otra]`). |
| Pulsa `[20]` | Agrega la línea al carrito, muestra subtotal acumulado y ofrece: `[Agregar otro]`, `[Ver cotización]`, `[Modificar]`. |
| `dame el descuento de siempre` | Explica que no hay política de descuentos aprobada y queda pendiente con un asesor humano. |
| `¿quién ganó el partido ayer?` | Redirige con una sola línea («Solo puedo ayudarte con tu cotización») y reitera las opciones del paso en curso. |

**Reglas de WhatsApp:** XEON solo responde a mensajes entrantes, dentro de la ventana de 24 horas.
Cada mensaje enviado o recibido cuenta en el plan de Kapso.

## 6. Diagnóstico

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El teléfono no recibe respuesta | Túnel reiniciado con otra URL | `uv run python scripts/kapso_webhook.py sync-tunnel` |
| | `WHATSAPP_SEND_ENABLED=false` | Ponlo en `true` y reinicia la terminal 1 |
| | No te uniste al sandbox | Envía el código de activación (paso 5) |
| La API registra `401` en el webhook | Secreto distinto al registrado en Kapso | `kapso_webhook.py create --rotate-secret …` y borra el webhook viejo en Kapso |
| La API registra `503` en el webhook | Falta `secrets/kapso_webhook_secret.txt` | Crea el webhook (paso 3) |
| `/health` dice `mock` | `LLM_PROVIDER=mock` en `.env` o en la terminal | Ponlo en `grok`, o `Remove-Item Env:LLM_PROVIDER` |
| `Address already in use` en el 8000 | Otra API corriendo | `Get-NetTCPConnection -LocalPort 8000` y detén ese proceso |
| Error de la pasarela Grok | Clave ausente o inválida | Revisa `secrets/grok_api_key.txt` |

Para inspeccionar en Kapso las entregas y los errores, ejecuta desde la carpeta de la skill:

```powershell
cd .agents\skills\observe-whatsapp
node --env-file=..\..\..\.env scripts\webhook-deliveries.js
node --env-file=..\..\..\.env scripts\errors.js
node --env-file=..\..\..\.env scripts\messages.js --phone-number-id <ID_SANDBOX>
cd ..\..\..
```

## 7. Apagar

Pulsa `Ctrl+C` en las terminales 1 y 2. El webhook queda registrado en Kapso; en la próxima
sesión basta con repetir el paso 3 (`sync-tunnel`).

## 8. Para pasar del sandbox a un número propio

Conecta el número en **Connected numbers** de Kapso, obtén su `phone_number_id` (paso 2.4),
actualízalo en `.env` y crea un webhook para ese número (paso 3). Fuera de la ventana de 24 horas
solo se pueden enviar plantillas aprobadas por Meta, que XEON todavía no implementa.

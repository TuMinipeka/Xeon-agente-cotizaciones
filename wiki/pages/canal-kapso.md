# Canal WhatsApp con Kapso

Integración de WhatsApp a través de Kapso (API oficial de WhatsApp Cloud) como canal predeterminado de XEON, siguiendo `whatsapp.pdf` (guía NodeStudio) y las skills `gokapso/agent-skills`. Relacionado: [orquestación](orquestacion.md), [decisiones pendientes](decisiones-pendientes.md) (D8), [estado del corte](estado-del-corte.md).

Revisado: 2026-10-24. Estado: **`implementado`** y **verificado en vivo**. El usuario confirmó que, desde el sandbox, XEON respondió por WhatsApp con la lógica de negocio. Commits `1ce0e26` (canal) y `54fa146` (limpieza D9).

## Decisiones del usuario (2026-10-24)

- **Kapso es el único canal de WhatsApp.** Evolution API se eliminó en la limpieza D9; `WHATSAPP_CHANNEL` ya no existe.
- **URL pública** con un túnel `cloudflared` gratuito hacia `http://127.0.0.1:8000`. La URL cambia en cada reinicio.
- **Pruebas primero en el sandbox de Kapso** y después con el número conectado.
- El agente alojado en Kapso **no** se usa: el cotizador y las reglas siguen en XEON.

## Avance del paso a paso de la guía

1. **Cuenta en app.kapso.ai** (manual): el usuario confirma que la tiene.
2. **Skills `integrate-whatsapp`, `automate-whatsapp`, `observe-whatsapp` (más `integrate-whatsapp-calling`, retirada en D9 por no usarse):** instaladas en `.agents/skills/` con autorización expresa del usuario, revisadas por el orquestador y con dependencias de scripts instaladas.
   - `.env` tiene `KAPSO_API_BASE_URL=https://api.kapso.ai` y `KAPSO_API_KEY=`, que el usuario pega a mano; está pendiente.
3. **Webhook:** se registra con la skill cuando exista la URL del túnel y el `phone_number_id` del sandbox.

## Contrato técnico (fuente: referencias de la skill `integrate-whatsapp`)

- **Configuración** (`Settings`):
  - `kapso_api_base_url` (`https://api.kapso.ai`).
  - `kapso_api_key` / `kapso_api_key_file`.
  - `kapso_phone_number_id`.
  - `kapso_webhook_secret` / `kapso_webhook_secret_file` (`secrets/kapso_webhook_secret.txt`).
  - `meta_graph_version` (`v24.0`).
  - Las claves solo por variable de entorno o archivo; nunca en logs ni en respuestas.
- **Entrada:** `POST /v1/channels/whatsapp/kapso/webhook`.
  1. Leer el cuerpo **crudo** y verificar `X-Webhook-Signature` = `HMAC-SHA256(secret, raw_body)` en hexadecimal con `hmac.compare_digest`. Si falta o no coincide, responder 401 sin procesar.
  2. Procesar solo `X-Webhook-Event: whatsapp.message.received` (payload v2). El resto responde 200 `ignored`.
  3. Del payload, tomar el texto de `message.text.body` cuando `message.type == "text"` (los demás tipos se ignoran), el emisor de `conversation.phone_number`, el id externo de `message.id` y `phone_number_id` de la raíz.
  4. Si llega un lote (lista o `X-Webhook-Batch: true`), procesar cada evento. Al crear el webhook se desactiva el buffering.
  5. Deduplicar por `message.id` o `X-Idempotency-Key`; Kapso reintenta a los 10, 40 y 90 s.
  6. Responder 200 rápido y procesar en segundo plano: `AgentService.respond(text, conversation_key=f"kapso-{phone_number_id}-{phone}", request_id=f"kapso-{message.id}")`.
- **Salida:** `KapsoChannelAdapter.send_text(recipient_number, text)` implementa `WhatsAppChannelPort`.
  - Envía `POST {base}/meta/whatsapp/{meta_graph_version}/{phone_number_id}/messages` con el header `X-API-Key`.
  - Cuerpo: `{"messaging_product":"whatsapp","to":<número sin +>,"type":"text","text":{"body":...}}`.
  - Errores HTTP saneados como `ChannelDeliveryError`.
- **Reglas de WhatsApp:**
  - Responder solo dentro de la ventana de 24 h, que siempre aplica porque XEON solo contesta mensajes entrantes.
  - Sin mensajes proactivos.
  - Fuera de la ventana solo se pueden enviar plantillas aprobadas (no implementado).
- **Registro del webhook** (lo hace el orquestador con la skill):
  - Comando: `node .agents/skills/integrate-whatsapp/scripts/create.js --phone-number-id <id> --url <tunel>/v1/channels/whatsapp/kapso/webhook --events whatsapp.message.received --kind kapso --payload-version v2 --buffer-enabled false`.
  - Con `KAPSO_SECRET_OUTPUT_FILE=secrets/kapso_webhook_secret.txt`, para que el secreto quede solo en ese archivo.

## Criterios de aceptación

- Firma válida → 200 `processed` y respuesta enviada. Firma inválida o ausente → 401.
- El mismo `message.id` repetido no genera una segunda respuesta ni un segundo borrador.
- Los eventos que no son `message.received` y los mensajes que no son texto se ignoran.
- Pruebas sin red con `httpx.MockTransport`, LLM `mock` y HMAC calculado en la prueba.
- `ruff`, `mypy` y `pytest` en verde.
- **Ensayo real** en el sandbox: un mensaje desde el teléfono del usuario recibe la respuesta de XEON con Grok.

## Puesta en marcha verificada (2026-10-24)

- **Sandbox:** `phone_number_id` `597907523413541`.
- **Webhook:** `86b37b90-3438-4734-a01b-0973c6e94ea8` (`kind: kapso`, `payload_version: v2`, sin buffering). El secreto está en `secrets/kapso_webhook_secret.txt`.
- **Hueco de la skill alpha:** `create.js` no envía `secret_key` y la API exige ese campo. El orquestador registró el webhook con `POST /platform/v1/whatsapp/phone_numbers/{id}/webhooks`, con el sobre `whatsapp_webhook` y un secreto generado localmente.
- **Túnel:** `cloudflared` (quick tunnel). Si cambia la URL, hay que actualizar el webhook con `update.js`.
- **Simulador local:** `scripts/simulate_whatsapp_webhook.py` firma un payload v2 con el secreto y lo envía al endpoint.

## Guía operativa (2026-10-24)

- **Paso a paso** de despliegue y pruebas: [`docs/DESPLIEGUE_WHATSAPP.md`](../../docs/DESPLIEGUE_WHATSAPP.md).
- **Webhook:** `scripts/kapso_webhook.py` (`create`, `update-url`, `list`) reemplaza el script temporal del orquestador. Genera y envía el `secret_key` que el `create.js` de la skill omite.
  - Validado contra la API real el 2026-10-24: `list` y `update-url` respondieron HTTP 200.

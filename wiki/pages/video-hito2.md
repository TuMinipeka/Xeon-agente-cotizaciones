---
tags:
  - xeon/estado
---

# Video demostrativo del HITO #2

Preparación del video que evidencia las 3 herramientas reales de XEON (`search_products`, `get_stock_by_branches` y `create_quote_draft`) con `grok-4.6`, por WhatsApp (Kapso) y por el CLI `xeon`. Relacionado: [hito S2](hito-s2.md), [canal Kapso](canal-kapso.md), [XEON CLI](xeon-cli.md), [evaluación conversacional](evaluacion-conversacional.md), [auditoría](auditoria-2026-10-24.md).

Revisado: 2026-10-24. Estado: **`planificado` / en preparación**. No hay grabación todavía.

## Decisiones del usuario (2026-10-24)

- **Grabación y edición con FFmpeg** (ya instalado, `Gyan.FFmpeg` 9.0.1). Es gratuito y automatizable por los agentes. No se usa OBS.
- **WhatsApp Web** en el PC: la conversación con el sandbox de Kapso y las terminales quedan en una sola pantalla.
- **Narración** con voz sintética de **ElevenLabs** y subtítulos. La clave la pega el usuario a mano en `secrets/elevenlabs_api_key.txt`; nunca va al chat.
- **E17 y E18 se corrigen antes de grabar** (hecho). El guion evita E15 y E16, que no hacen falta para mostrar las 3 herramientas.
- **Mínima intervención del usuario:** solo hace las acciones manuales marcadas con 🖐 en el guion.

## Evidencia de herramientas reales

Con Grok, el cliente no ve los marcadores `XEON_TOOL`. Para mostrar el funcionamiento real sin simular, Codex agregó una **traza** (`909d7ae`):

- el logger `xeon.tools` imprime una línea `TOOL …` por invocación en la consola de la API (estado, SKU, sede, disponibilidad o subtotal, sin teléfonos ni secretos);
- el comando `tools`/`t` del shell muestra las herramientas del último turno.

**Límite:** con `xeon --api` el comando `t` no recibe la traza del servidor; la traza de WhatsApp se ve en la consola de la API.

## Guion

[`docs/VIDEO_HITO2.md`](../../docs/VIDEO_HITO2.md), commit `dacd1c3` en `developer/daniel`. Escenas:

1. Ambigüedad con `search_products`.
2. Elección, stock por sede y borrador reutilizado.
3. Borrador de varias líneas por $670.500.
4. Negativa de descuento en el CLI, más `t` y `s`.

La edición acelera las esperas de Grok y las rotula «espera acortada». No se altera ninguna respuesta. Si algo no coincide con el guion durante la grabación, se registra y se vuelve a grabar; no se oculta en la edición.

## Reparto

| Agente | Tarea | Estado |
|---|---|---|
| Codex | E17, E18 y traza (`e36a5b3`, `6b07e7a`, `909d7ae`, `4b89f43`) | Hecho |
| Codex | `scripts/video/record.py`, `narrate.py` y `edit.py` | En curso |
| agy (QA) | Ensayo del guion en mock y en vivo (como máximo 30 llamadas, puerto 8013) y medición de tiempos | En curso |
| agy (QA) | Revisión del video final contra el guion | Pendiente |
| Opus | Guion, auditoría, arranque de servicios y grabación, wiki | En curso |
| Usuario | Clave de ElevenLabs, WhatsApp Web con QR, «No molestar», ventanas, mensajes del guion | Pendiente |

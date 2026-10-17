# XEON · demo audiovisual

`XeonDemoV2` es el video principal del repositorio. Está hecho con Remotion y tiene seis escenas, narración en español, subtítulos incrustados y pista externa en `subtitles-v2.srt`. El MP4 entregable es `xeon-demo-v2.mp4` (1920 × 1080, 30 fps, 76,3 s).

El relato muestra un webhook de WhatsApp **simulado localmente**, identificación de un SKU candidato, inventario sintético por sede y un borrador `DRAFT` calculado por el backend. No demuestra entrega a un teléfono real, inventario empresarial, aprobación ni PDF. La base de datos comercial y la búsqueda con `pgvector` siguen pendientes. El escenario de stock corresponde al 8 de octubre de 2026 a las 15:00 UTC; no expresa disponibilidad actual.

## Revisar o editar el video

Desde `video/xeon-remotion`:

```powershell
npm ci
npm run studio
```

Abre `XeonDemoV2`. La composición está en `src/video-v2.tsx`, la sincronización en `src/timing-v2.json` y el guion de voz en `NARRATION.md`. Para regenerar el MP4 desde los recursos locales:

```powershell
npm run render
```

La narración existente está en `public/voice-v2/narration.mp3`; no es necesario llamar a ElevenLabs para editar o renderizar. El script `scripts/generate-voice.ps1` realiza una generación externa deliberada y puede consumir créditos. Verifica los derechos de uso de esa voz antes de publicar la pieza comercialmente.

## Ejecutar la demo interactiva

La demo complementaria consulta el backend real en perfil `mock`; chat, inventario y borrador son acciones separadas. Desde la raíz del repositorio, inicia la API:

```powershell
$env:LLM_PROVIDER = "mock"
$env:WHATSAPP_SEND_ENABLED = "false"
uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8001
```

En otra terminal:

```powershell
cd video/xeon-remotion
npm run demo
```

Abre `http://127.0.0.1:4173`. El servidor de la demo solo permite acciones cuando `/health` confirma `provider=mock`; no envía mensajes a un teléfono. Se puede cambiar el puerto de la API mediante `XEON_DEMO_API_PORT` y el de la demo mediante `XEON_DEMO_PORT`.

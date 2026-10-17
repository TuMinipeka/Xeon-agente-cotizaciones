# XEON · video y demo interactiva

`XeonDemo` es el video principal del repositorio: una composición Remotion de **92 segundos, 1920 × 1080 y 30 fps**. Incluye siete escenas, narración local en español, subtítulos incrustados, `subtitles-v3.srt` y una base sonora estéreo generada para esta pieza. El MP4 listo para revisar es `xeon-demo.mp4`.

La propuesta visual sigue el recorrido **consulta → código de producto/SKU → inventario → borrador → asesor real**. El producto usa el código/SKU candidato `CEM-50`. El contacto con un asesor es el diferencial buscado, pero **el traspaso automático todavía no está implementado**. El video identifica como simulados el webhook, el catálogo y el stock. No afirma entrega a un teléfono real, aprobación, reserva, PDF ni persistencia comercial.

## Editar y renderizar

Desde `video/xeon-remotion`:

```powershell
npm ci
npm run studio
npm run render
```

La composición está en `src/video-v3.tsx`, el diseño en `src/v3.css` y los tiempos en `src/timing-v3.json`. El texto de voz se cambia en `narration-script.json`. Para regenerar la voz, los subtítulos y el sonido en Windows con la voz local instalada:

```powershell
./scripts/generate-local-voice.ps1
python scripts/build-media.py
npm run render
```

El sonido se crea por código, sin muestras musicales ni llamadas externas. La síntesis local requiere `Microsoft Sabina Desktop` y `ffmpeg` para el MP3. No se hacen llamadas a Groq, Evolution API ni proveedores de voz al renderizar.

## Demo interactiva del backend

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

Abre `http://127.0.0.1:4173`. El servidor solo permite acciones cuando `/health` confirma `provider=mock`; no envía mensajes a un teléfono. Los puertos se cambian con `XEON_DEMO_API_PORT` y `XEON_DEMO_PORT`.

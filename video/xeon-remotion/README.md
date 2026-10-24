# XEON · video y demo interactiva

`XeonDemo` es el video principal del repositorio: una composición Remotion de **82 segundos, 1920 × 1080 y 30 fps**. Incluye siete escenas, narración en español con **Bella de ElevenLabs** (modelo Multilingual v2), subtítulos incrustados, `subtitles-v3.srt` y una base sonora estéreo generada para esta pieza. El MP4 listo para revisar es `xeon-demo.mp4`.

La propuesta visual sigue el recorrido **consulta → código de producto/SKU → inventario → borrador → asesor real**. El producto usa el código/SKU candidato `CEM-50`. El contacto con un asesor es el diferencial buscado, pero **el traspaso automático todavía no está implementado**. El video identifica como simulados el webhook, el catálogo y el stock. No afirma entrega a un teléfono real, aprobación, reserva, PDF ni persistencia comercial.

## Editar y renderizar

Desde `video/xeon-remotion`:

```powershell
npm ci
npm run studio
npm run render
```

Con Studio abierto en `http://localhost:3000/XeonDemo`, selecciona la composición y abre **Inspector → Default Props**. Allí puedes cambiar los tres renglones del gancho, el mensaje de ejemplo y los tres renglones de la respuesta visual; Studio guarda esos textos en `src/root.tsx` y actualiza la vista al instante. Los tiempos, animaciones y demás escenas se editan en `src/video-v3.tsx` y `src/v3.css`. Si cambias el texto que se narra, también habrá que ajustar `narration-script.json`, voz y subtítulos.

La composición está en `src/video-v3.tsx`, el diseño en `src/v3.css` y los tiempos en `src/timing-v3.json`. El texto de voz se cambia en `narration-script.json`. La toma actual de ElevenLabs está congelada en `public/voice-elevenlabs/narration.mp3`. Sus límites por frase se registran en `scripts/sync-elevenlabs.py`; si se genera otra toma, deben volver a medirse antes de sincronizar. Para reconstruir los subtítulos y la base sonora con la toma actual:

```powershell
python scripts/sync-elevenlabs.py
python scripts/build-soundscape.py
npm run render
```

La voz local anterior se conserva como alternativa de edición. Para regenerarla en Windows:

```powershell
./scripts/generate-local-voice.ps1
python scripts/build-media.py
npm run render
```

El sonido se crea por código, sin muestras musicales ni llamadas externas. La síntesis local requiere `Microsoft Sabina Desktop` y `ffmpeg` para el MP3. El render usa el MP3 local de ElevenLabs y no llama a Groq, Evolution API ni proveedores de voz.

La toma Bella se generó con el plan gratuito de ElevenLabs para revisar esta demo local. Ese plan no concede uso comercial. Si se publica una versión no comercial, el título debe atribuir `elevenlabs.io` o `11.ai`; para una campaña comercial se requiere generar una toma nueva durante una suscripción con licencia comercial. Consultar las [condiciones de publicación de ElevenLabs](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform).

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

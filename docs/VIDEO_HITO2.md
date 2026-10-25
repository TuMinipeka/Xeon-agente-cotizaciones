# Guion del video demostrativo, HITO #2

**Objetivo:** mostrar, con XEON real (motor `grok-4.6`), las **3 herramientas** del hito funcionando por **WhatsApp (Kapso)** y por el **CLI `xeon`**:

- `search_products`
- `get_stock_by_branches`
- `create_quote_draft`

**Duración final:** unos 2 minutos. La grabación cruda dura más porque Grok tarda entre 10 y 30 s por respuesta; en la edición esas esperas se acortan y se rotulan como «espera acortada». **No se altera ninguna respuesta.**

**Reparto:**

- Los agentes **arrancan y detienen** la grabación, preparan los servicios y editan el video.
- **Tú** haces las acciones manuales marcadas con 🖐.
- El texto exacto de cada mensaje está entre comillas: escríbelo tal cual.

---

## A. Preparación (una sola vez, antes de grabar)

| # | Quién | Acción exacta |
|---|---|---|
| A1 | 🖐 Tú | Crea el archivo `secrets/elevenlabs_api_key.txt` y pega **a mano** tu clave de ElevenLabs en una sola línea. **No la pegues en el chat.** |
| A2 | 🖐 Tú | Abre `https://web.whatsapp.com` en el navegador, escanea el QR con tu teléfono y abre el chat con el **número del sandbox de Kapso**. Si no estás unido al sandbox, envía primero el código de activación (app.kapso.ai → Sandbox). |
| A3 | 🖐 Tú | Activa **No molestar** en Windows (Configuración → Sistema → Notificaciones) para que no aparezcan avisos en el video. |
| A4 | Agente | Abre dos ventanas de terminal visibles: **«XEON API — traza de herramientas»** (uvicorn) y **«XEON CLI»** (`uv run xeon`). Levanta el túnel y ejecuta `sync-tunnel`. Comprueba que `/health` dice `grok-4.6`. |
| A5 | 🖐 Tú | Organiza la pantalla: **mitad izquierda** con WhatsApp Web; **mitad derecha arriba** con la terminal de la API (traza); **mitad derecha abajo** con la terminal del CLI. Avisa al agente: «listo para grabar». |

> Para evitar letras diminutas, usa una resolución de 1920×1080 y una letra de terminal de al menos 16 px.

---

## B. Grabación (el agente la inicia y la detiene)

El agente inicia la grabación de pantalla completa con FFmpeg y escribe en el chat «🔴 GRABANDO». **Espera a que cada respuesta de XEON aparezca completa** antes de escribir el siguiente mensaje.

### Escena 1: WhatsApp, búsqueda con ambigüedad (`search_products`)

1. 🖐 En WhatsApp Web escribe y envía: **«necesito 10 bultos de cemento gris»**
2. **Debe verse:**
   - en WhatsApp, XEON ofrece **3 opciones** de cemento con sus precios y pide elegir 1, 2 o 3;
   - en la traza, `TOOL search_products status=clarification_required`;
   - no aparece ningún `create_quote_draft`, porque todavía no hay borrador.

### Escena 2: elección, stock y borrador (`get_stock_by_branches` + `create_quote_draft`)

3. 🖐 Escribe y envía: **«1»**
4. **Debe verse:**
   - en WhatsApp, XEON confirma el **Cemento gris 50 kg a $28.900** y el total de **10 bultos: $289.000**;
   - en la traza, `TOOL get_stock_by_branches sku=CEM-50 …` y `TOOL create_quote_draft … subtotal=289000.00 COP`.
5. 🖐 Escribe y envía: **«lo recojo en la sede norte»**
6. **Debe verse:**
   - en WhatsApp, XEON informa la disponibilidad en **sede norte**, y aclara que el dato de inventario no es reciente (snapshot sintético del 8 de octubre de 2026) y que **no reserva stock**;
   - en la traza, `TOOL get_stock_by_branches … sede=sede-norte …` y **ningún borrador nuevo** (se reutiliza el anterior).

### Escena 3: borrador de varias líneas (`create_quote_draft`)

7. 🖐 Escribe y envía: **«20 bultos de cemento y 50 metros de alambre»**
8. **Debe verse:**
   - en WhatsApp, un borrador con **2 líneas**: 20 × $28.900 = **$578.000** y 50 × $1.850 = **$92.500**, con un **total de $670.500**, como borrador para revisión (no aprobado);
   - en la traza, `TOOL create_quote_draft … lineas=2 subtotal=670500.00 COP`.

### Escena 4: CLI, negativa correcta y evidencia de herramientas

9. 🖐 Haz clic en la terminal **XEON CLI** y escribe: **«soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento»** + Enter.
10. **Debe verse:** XEON dice que **no hay una política de descuentos aprobada** y no inventa ningún porcentaje.
11. 🖐 Escribe **«t»** + Enter. **Debe verse:** la lista de herramientas ejecutadas en ese turno.
12. 🖐 Escribe **«s»** + Enter. **Debe verse:** `provider: grok` y `model: grok-4.6`.
13. 🖐 Avisa al agente: **«terminé»**. El agente detiene la grabación.

---

## C. Edición (automática, por los agentes)

| Tramo | Contenido | Narración (ElevenLabs) |
|---|---|---|
| 0:00–0:10 | Portada: «XEON — HITO #2: 3 herramientas con Grok» | «XEON es un agente de cotizaciones para ferreterías. En este hito demostramos sus tres herramientas reales conectadas a Grok.» |
| Escena 1 | Rótulo: «Herramienta 1: search_products» | «Ante un pedido ambiguo, XEON busca en el catálogo y pide elegir en lugar de adivinar.» |
| Escena 2 | Rótulos: «Herramienta 2: get_stock_by_branches» y «Herramienta 3: create_quote_draft» | «Al elegir, consulta el inventario por sede y crea un borrador calculado por el backend, no por el modelo. El seguimiento reutiliza el mismo borrador.» |
| Escena 3 | Rótulo: «Borrador con varias líneas» | «Varios productos en un mensaje generan un solo borrador con todas las líneas y el total verificado.» |
| Escena 4 | Rótulo: «CLI y límites de seguridad» | «Desde la terminal, XEON rechaza descuentos sin política y muestra la traza de las herramientas que ejecutó con grok-4.6.» |
| Cierre | «Validación humana pendiente — QA externo» | «Todo lo mostrado es la ejecución real. La aprobación final la realiza el QA humano.» |

- **Esperas:** las pausas mientras Grok responde se aceleran y se rotulan «espera acortada». No se elimina ni se reemplaza ninguna respuesta.
- **Subtítulos:** los subtítulos de la narración se queman en el video, y el archivo `.srt` se entrega aparte.
- **Salida:** `video/hito2/XEON_HITO2_demo.mp4` (ignorado por Git, porque es pesado) más el `.srt`.

## D. Qué cuenta como falla

Si en la grabación ocurre algo distinto de lo que «debe verse», **no se edita para ocultarlo**: se detiene, se registra y se corrige o se vuelve a grabar la escena.

## Estado

- [ ] Correcciones E17 y E18 y traza de herramientas (Codex)
- [ ] Ensayo del guion (agy)
- [ ] Grabación (tú + agente)
- [ ] Edición y revisión del video (agentes)
- [ ] Validación del QA humano

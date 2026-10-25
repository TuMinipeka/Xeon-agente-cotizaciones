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
   - en WhatsApp, XEON ofrece **3 opciones** de cemento (`Cemento gris 50 kg — $28.900`, `Cemento gris referencia sintetica 1 — $27.225`, `Cemento gris referencia sintetica 2 — $27.450`) y pide elegir 1, 2 o 3;
   - en la traza, `TOOL search_products status=semantic_candidates sku=CEM-50` (aparece dos veces: en extracción de líneas y en búsqueda principal; el marcador interno al modelo es `status=clarification_required`);
   - no aparece ningún `create_quote_draft`, porque todavía no hay borrador.

### Escena 2: elección, stock y borrador (`get_stock_by_branches` + `create_quote_draft`)

3. 🖐 Escribe y envía: **«1»**
4. **Debe verse:**
   - en WhatsApp, XEON confirma el **Cemento gris 50 kg a $28.900** y el total de **10 bultos: $289.000**, indicando que queda en revisión;
   - en la traza, `TOOL search_products status=exact_match sku=CEM-50`, `TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale` y `TOOL create_quote_draft quote_id=<id> lineas=1 subtotal=289000.00 COP replayed=false`.
5. 🖐 Escribe y envía: **«lo recojo en la sede norte»**
6. **Debe verse:**
   - en WhatsApp, XEON registra que el pedido de **10 bultos a $28.900 (Total: $289.000)** es para recoger en **sede Norte** y aclara que **sigue en revisión para confirmar disponibilidad** allá (**no promete reserva ni stock firme**; el detalle técnico `vigencia=stale` queda en la traza y Grok lo traduce a «en revisión para confirmarte la disponibilidad»);
   - en la traza, `TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale` y `TOOL create_quote_draft quote_id=<mismo_id> lineas=1 subtotal=289000.00 COP replayed=true` (**ningún borrador nuevo**: `replayed=true` confirma que reutiliza el `quote_id` anterior).

### Escena 3: borrador de varias líneas (`create_quote_draft`)

7. 🖐 Escribe y envía: **«20 bultos de cemento y 50 metros de alambre»**
8. **Debe verse:**
   - en WhatsApp, un borrador con **2 líneas**: 20 × $28.900 = **$578.000** y 50 × $1.850 = **$92.500**, con un **total de $670.500**, indicando que queda en revisión para confirmar disponibilidad (no aprobado ni reservado);
   - en la traza, `TOOL search_products status=exact_match sku=CEM-50`, `TOOL get_stock_by_branches sku=CEM-50 …`, `TOOL search_products status=exact_match sku=ALA-14`, `TOOL get_stock_by_branches sku=ALA-14 …` y `TOOL create_quote_draft quote_id=<nuevo_id> lineas=2 subtotal=670500.00 COP replayed=false`.

### Escena 4: CLI, negativa correcta y evidencia de herramientas

9. 🖐 Haz clic en la terminal **XEON CLI** (sesión independiente de WhatsApp; si reutilizas una sesión de CLI donde ya cotizaste 10 bultos de cemento, escribe antes `n` + Enter para iniciar conversación limpia) y escribe: **«soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento»** + Enter.
10. **Debe verse:** XEON informa el precio de **$28.900 el bulto**, dice que **no puede aplicar un descuento automático porque no hay una política de descuentos aprobada** y no inventa ningún porcentaje.
11. 🖐 Escribe **«t»** + Enter. **Debe verse:** la lista de herramientas ejecutadas en ese turno (`TOOL search_products status=exact_match sku=CEM-50`, `TOOL get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale`, `TOOL create_quote_draft status=DiscountPolicyUnavailable`).
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

## E. Tiempos medidos y hallazgos del ensayo (`grok-4.6`)

Ensayo ejecutado sobre `developer/daniel` (`dacd1c3`, con `e36a5b3`, `6b07e7a` y `909d7ae`) usando 5 llamadas en vivo a `grok-4.6` (`POST /v1/chat` en puerto `8013` con `WHATSAPP_SEND_ENABLED=false` para Escenas 1–3 y `uv run xeon` para Escena 4):

| Paso | Escena y canal | Mensaje enviado | Herramientas registradas en traza (`TOOL ...`) | Tiempo en vivo (`grok-4.6`) |Resultado |
|---|---|---|---|---:|---|
| **Paso 1** | Escena 1 (`POST /v1/chat`) | `necesito 10 bultos de cemento gris` | `TOOL search_products status=semantic_candidates sku=CEM-50` (×2) | **21,24 s** | Ofrece las 3 opciones (`$28.900`, `$27.225`, `$27.450`) y pide elegir `1, 2 o 3` sin crear borrador. |
| **Paso 3** | Escena 2 (`POST /v1/chat`) | `1` | `search_products status=exact_match sku=CEM-50`<br>`get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale`<br>`create_quote_draft quote_id=93c12bf2-... lineas=1 subtotal=289000.00 COP replayed=false` | **22,24 s** | Confirma 10 bultos a `$28.900` = **Total: `$289.000`** («queda en revisión»). |
| **Paso 5** | Escena 2 (`POST /v1/chat`) | `lo recojo en la sede norte` | `search_products status=clarification_required sku=none`<br>`search_products status=exact_match sku=CEM-50`<br>`get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale`<br>`create_quote_draft quote_id=93c12bf2-... lineas=1 subtotal=289000.00 COP replayed=true` | **28,35 s** | Mantiene `10` bultos a `$28.900` (`$289.000`) para recoger en sede Norte («sigue en revisión para confirmarte la disponibilidad allá») y reutiliza el mismo borrador (`replayed=true`). |
| **Paso 7** | Escena 3 (`POST /v1/chat`) | `20 bultos de cemento y 50 metros de alambre` | `search_products status=exact_match sku=CEM-50`<br>`get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale`<br>`search_products status=exact_match sku=ALA-14`<br>`get_stock_by_branches sku=ALA-14 sede=sede-norte disponible=unknown vigencia=unknown`<br>`create_quote_draft quote_id=d8547404-... lineas=2 subtotal=670500.00 COP replayed=false` | **42,69 s** | Borrador de 2 líneas: `20 × $28.900 = $578.000` y `50 × $1.850 = $92.500`, **Total: `$670.500`** («queda en revisión para confirmar disponibilidad»). |
| **Pasos 9–12** | Escena 4 (`uv run xeon`: mensaje + `t` + `s` + `q`) | `soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento` | `search_products status=exact_match sku=CEM-50`<br>`get_stock_by_branches sku=CEM-50 sede=sede-norte disponible=unknown vigencia=stale`<br>`create_quote_draft status=DiscountPolicyUnavailable` | **36,77 s** | Rechaza el descuento («no hay una política de descuentos aprobada»), informa `$28.900` el bulto, `t` muestra las 3 herramientas y `s` muestra `provider: grok` y `model: grok-4.6`. |
| **Total** | Escenas 1–4 (5 llamadas a Grok) | — | — | **151,29 s** (~2 min 31 s crudos) | Listo para acortar esperas a < 2 min en edición. |

### Discrepancias detectadas que requieren cambio de código (no bloquean el video si Escena 4 corre en su propia sesión de CLI)

1. **Reutilización de borrador (`6b07e7a`) eclipsa `discount_requested=True` cuando coincide `(conversation_key, líneas)`:**
   - Si las Escenas 1 a 4 se ejecutan dentro de **una misma conversación** (mismo `conversation_id`), en el Paso 3 se guarda un borrador para `(CEM-50, 10)` con `request_id = _draft_request_id(conversation_key, (CEM-50, 10))`.
   - Si en esa misma conversación se envía luego `«soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento»`, la firma de líneas vuelve a ser `(CEM-50, 10)`: el bloque de `known_lines` en `src/xeon/agent/toolbelt.py` invoca `create_quote_draft` sin `discount_requested=_requests_discount(normalized)` y además `CreateQuoteDraftUseCase.execute` / `_draft_request_id` no separan solicitudes con `discount_requested=True`, devolviendo el borrador previo con `replayed=true` en vez de `DiscountPolicyUnavailable`.
   - **Impacto en la grabación:** En el guion del video no ocurre porque las Escenas 1–3 van por WhatsApp y la Escena 4 va en una sesión limpia de `XEON CLI` (distinto `conversation_id`).
2. **Doble registro de `TOOL search_products` en un mismo turno:**
   - En los Pasos 1 y 5, `prepare_verified_context` invoca `search_products` tanto al intentar resolver líneas como en la búsqueda principal del turno, por lo que aparecen dos líneas `TOOL search_products ...` seguidas en la consola/traza. No afecta los montos ni las respuestas de Grok.

## Estado

- [x] Correcciones E17 y E18 y traza de herramientas (Codex)
- [x] Ensayo del guion (agy)
- [ ] Grabación (tú + agente)
- [ ] Edición y revisión del video (agentes)
- [ ] Validación del QA humano

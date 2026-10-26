# Guía de QA Humano y Grabación de Demo — Hito #2

Esta guía está dirigida al evaluador de **QA humano externo** encargado de validar el **Hito #2** de XEON y grabar el video demostrativo de **menos de 2 minutos**.

---

## 1. ¿Qué es XEON y qué valida el Hito #2?

**XEON** es un agente comercial de inteligencia artificial para ferreterías y agroferreterías que atiende compradores por **WhatsApp (vía Kapso)** y por **terminal interactiva (`uv run xeon`)**. Su principio central es que **el modelo (`grok-4.6`) interpreta la solicitud y redacta la respuesta, pero nunca inventa ni calcula datos comerciales**: todos los precios, existencias por sede y subtotales provienen del backend determinista (`Decimal`) sobre el catálogo e inventario verificados.

### Alcance del Hito #2
El **Hito #2** valida que las **3 herramientas comerciales** de `CommercialToolbelt` ([`wiki/pages/contratos-herramientas.md`](../wiki/pages/contratos-herramientas.md)) funcionen de extremo a extremo conectadas en vivo a **Grok (`grok-4.6`)** dentro de un flujo demostrativo de **menos de 2 minutos**:

1. **`search_products`**: busca productos en el catálogo por SKU, alias o coincidencia léxica; cuando hay varias referencias posibles o falta información (medidas sin unidad o referencias vagas), **pide aclaración al comprador antes de cotizar**.
2. **`get_stock_by_branches`**: consulta existencias por sede (`sede-norte`, `sede-centro`, `sede-sur` y despacho), distingue disponibilidad local vs. traslado y reporta la vigencia del dato (`fresh`, `stale`, `unknown`) **sin prometer reservas de inventario**.
3. **`create_quote_draft`**: genera borradores de cotización idempotentes en estado **`DRAFT` (versión 1)** de una o varias líneas calculados con `Decimal`, **sin aprobar cotizaciones, sin facturar y sin inventar porcentajes de descuento**.

---

## 2. Requisitos y arranque del entorno

No dupliques la configuración: sigue las guías existentes según el canal donde vayas a ejecutar la prueba y grabar el video:

- **Requisitos generales y comandos del proyecto:** ver [`README.md`](../README.md) (secciones *Inicio rápido*, *XEON CLI* y *Configuración*).
- **Despliegue paso a paso en WhatsApp real con Kapso y `cloudflared`:** ver [`docs/DESPLIEGUE_WHATSAPP.md`](DESPLIEGUE_WHATSAPP.md).
- **Guía de prueba manual del embudo guiado por WhatsApp (D14):** ver [`docs/QA_EMBUDO.md`](QA_EMBUDO.md).

### Resumen rápido de arranque según modalidad

#### Modalidad A: Desde el shell interactivo (`uv run xeon`)
1. Verifica que exista `secrets/grok_api_key.txt` (sin imprimir su contenido) y que `LLM_PROVIDER` no esté forzado a `mock`.
2. Abre el shell en una terminal desde la raíz del proyecto:
   ```powershell
   uv run xeon
   ```
3. Escribe `s` (`status`) y confirma que muestre `provider: grok`, `model: grok-4.6` y `key: file configured`.
4. Puedes escribir directamente los mensajes de varias palabras en el prompt `xeon > ` o anteponer `r ` (por ejemplo: `r necesito 10 tubos pvc`).

#### Modalidad B: Desde un teléfono con WhatsApp (vía Kapso)
Sigue los pasos 1 a 5 de [`docs/DESPLIEGUE_WHATSAPP.md`](DESPLIEGUE_WHATSAPP.md):
1. **Terminal 1 (API XEON):** `uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`
2. **Terminal 2 (Túnel HTTPS):** `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8000`
3. **Terminal 3 (Sincronizar webhook de Kapso):** `uv run python scripts/kapso_webhook.py sync-tunnel`
4. **Comprobación previa:** ejecuta `curl.exe http://127.0.0.1:8000/health` y verifica que responda `"provider":"grok","model":"grok-4.6"`.

---

## 3. Guion reproducible para el video (< 2 minutos)

> [!IMPORTANT]
> **Reglas visibles durante toda la demo:**
> 1. **Solo borradores (`DRAFT`):** XEON únicamente prepara **borradores de cotización (`DRAFT` v1)**. En ningún turno debe afirmar que una cotización quedó *aprobada*, *facturada*, *confirmada* ni que el stock quedó *reservado*.
> 2. **Diferencia entre `mock` y `grok-4.6`:** Si ensayas el guion con `$env:LLM_PROVIDER='mock'`, verás en bruto los marcadores `[XEON_TOOL:...]`. Con **Grok (`grok-4.6`)** la redacción en lenguaje natural cambia en cada corrida y los marcadores internos se ocultan por seguridad, pero **los precios unitarios, las 3 opciones ofrecidas, los subtotales y el estado de borrador deben coincidir exactamente**.
> 3. **Transición al embudo guiado (D14):** Este guion documenta la línea base verificada y grabada del Hito #2 (conversación abierta). Tras la integración del embudo guiado (merge `aa90b94`), el chat avanza paso a paso mediante opciones numeradas en CLI y botones/listas interactivas en WhatsApp. Para ejecutar la validación manual del nuevo embudo guiado, consulte la guía dedicada en [`docs/QA_EMBUDO.md`](QA_EMBUDO.md).

Ejecuta los siguientes mensajes **en orden dentro de la misma conversación** (tiempo total estimado: **1 min 45 s**):

| Paso y tiempo | Herramienta validada | Mensaje EXACTO a enviar | Qué debe verse en pantalla (criterio de éxito) |
|---|---|---|---|
| **Paso 1a**<br>`0:00 – 0:20` | `search_products`<br>*(desambiguación de candidatos)* | `necesito 10 tubos pvc`<br>*(Variante con cemento: `necesito 10 bultos de cemento gris`. Nota: escribir `necesito 10 bultos de cemento` sin la palabra `gris` coincide con el alias exacto `"cemento"` de `CEM-50` y cotiza directo; para mostrar la elección entre 3 opciones usa `necesito 10 tubos pvc` o `necesito 10 bultos de cemento gris`).* | XEON **no crea un borrador a ciegas** (`status=clarification_required`). Muestra las **3 opciones candidatas** del catálogo con sus precios de base de datos:<br>• Con `necesito 10 tubos pvc`: 1) `Tubo PVC presion 1/2 pulgada` (`$4.200,00 COP`), 2) `Tubo PVC presion referencia sintetica 1` (`$5.041,00 COP`), 3) `Tubo PVC presion referencia sintetica 2` (`$5.082,00 COP`).<br>• Con `necesito 10 bultos de cemento gris`: 1) `Cemento gris 50 kg` (`$28.900,00 COP`), 2) `Cemento gris referencia sintetica 1` (`$27.225,00 COP`), 3) `Cemento gris referencia sintetica 2` (`$27.450,00 COP`).<br>Pregunta cuál opción elige el cliente (`1, 2 o 3`). |
| **Paso 1b**<br>`0:20 – 0:40` | `search_products` + `get_stock_by_branches` + `create_quote_draft`<br>*(resolución de opción)* | `el 1`<br>*(Nota para `uv run xeon`: escribe `el 1` o `opcion 1` —o `r 1`—, nunca `1` suelto sin `r`, porque el shell interpreta una sola letra/dígito como un comando inválido).* | XEON resuelve la opción 1 seleccionada y recuerda la cantidad (`10`), consulta el inventario y crea el **borrador `DRAFT` v1**:<br>• Si elegiste tubo PVC (`TUB-PVC-20`): `10` unidades × `$4.200,00 COP` = **`$42.000,00 COP`**.<br>• Si elegiste cemento (`CEM-50`): `10` bultos × `$28.900,00 COP` = **`$289.000,00 COP`**. |
| **Paso 2**<br>`0:40 – 1:05` | `get_stock_by_branches`<br>*(consulta por sede y memoria)* | `lo recojo en la sede norte` | XEON conserva el SKU y la cantidad (`10`) del turno anterior sin bloquear el mensaje por alcance, consulta `get_stock_by_branches` en **`sede-norte`** (para `TUB-PVC-20`: `12` unidades en `sede-norte`; para `CEM-50`: `20` bultos en `sede-norte`, `80` en `sede-centro` y `40` para entrega, con `vigencia=stale` porque el snapshot sintético es del `2026-10-08`) e indica que la disponibilidad debe confirmarse y **no equivale a una reserva**. |
| **Paso 3**<br>`1:05 – 1:30` | `create_quote_draft`<br>*(borrador multilínea)* | `20 bultos de cemento y 50 metros de alambre` | XEON identifica ambas referencias por alias exacto y genera un **único borrador `DRAFT` v1 de 2 líneas (`lines=2`)**:<br>• Línea 1 (`CEM-50`): `20` × `Cemento gris 50 kg` (`$28.900,00 COP`) = **`$578.000,00 COP`**<br>• Línea 2 (`ALA-14`): `50` × `Alambre de pua calibre 14` (`$1.850,00 COP`) = **`$92.500,00 COP`**<br>• **Subtotal / Total del borrador `DRAFT`:** **`$670.500,00 COP`** (dejando claro que queda en revisión y no está confirmado ni reservado).<br>*(Nota operativa: este paso evalúa la creación multilínea directa del Hito #2. En el embudo guiado D14 actual, las líneas múltiples se incorporan paso a paso con `[Agregar otro]` o modificando el carrito, ver [`docs/QA_EMBUDO.md`](QA_EMBUDO.md)).* |
| **Paso 4**<br>`1:30 – 1:50` | `create_quote_draft` / `CommercialScopePolicy`<br>*(negativa correcta)* | `soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento`<br>*(Opcional adicional fuera de alcance: `cuentame un chiste`)* | `create_quote_draft` devuelve `status=discount_policy_unavailable`: XEON informa que **no hay política de descuentos aprobada**, **no crea borrador con descuento** ni inventa porcentajes (`%`). Ante `cuentame un chiste`, `local-policy` rechaza el tema ajeno y redirige al catálogo ferretero. |

### Comando rápido para ensayar el guion en modo `mock` (sin gastar llamadas)
```powershell
$env:LLM_PROVIDER='mock'
"necesito 10 tubos pvc`nel 1`nlo recojo en la sede norte`n20 bultos de cemento y 50 metros de alambre`nsoy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento`ncuentame un chiste`nq" | uv run xeon
```

---

## 4. Checklist de observación para el QA humano

### 4.1. Tabla de precios oficiales de referencia
Todos los precios provienen exclusivamente de [`evals/fixtures/catalog.json`](../evals/fixtures/catalog.json). Ninguna respuesta de XEON puede contradecir estos valores:

| Producto en catálogo | SKU interno | Unidad | Precio unitario (`catalog.json`) | Ejemplo de cálculo exacto |
|---|---|---|---:|---:|
| **Cemento gris 50 kg** | `CEM-50` | `bulto` | **`$28.900,00 COP`** | `10` bultos = `$289.000,00 COP`<br>`20` bultos = `$578.000,00 COP` |
| **Alambre de pua calibre 14** | `ALA-14` | `metro` | **`$1.850,00 COP`** | `50` metros = `$92.500,00 COP`<br>`300` metros = `$555.000,00 COP` |
| **Tubo PVC presion 1/2 pulgada** | `TUB-PVC-20` | `unidad` | **`$4.200,00 COP`** | `10` unidades = `$42.000,00 COP`<br>`12` unidades = `$50.400,00 COP` |
| **Manguera de desague para aire acondicionado 5/8 pulgada** | `MAN-AC-58` | `metro` | **`$2.600,00 COP`** | `5` metros = `$13.000,00 COP` |
| **Lamina de zinc calibre 26 de 2,44 m** | `LAM-ZIN-26-244` | `lamina` | **`$58.900,00 COP`** | `10` láminas = `$589.000,00 COP` |

### 4.2. Lista de verificación durante la prueba

- [ ] **Exactitud de precios y totales:** Todos los precios unitarios y subtotales mostrados por XEON coinciden peso a peso con la tabla anterior (por ejemplo, `20` bultos de cemento + `50` metros de alambre = **`$670.500,00 COP`**).
- [ ] **Desambiguación ante ambigüedad:** Ante una solicitud con múltiples candidatos (`necesito 10 tubos pvc` o `necesito 10 bultos de cemento gris`), medidas sin unidad (`la pieza mide 20 x 30 x 10`) o descripción vaga (`necesito el coso del aire acondicionado`), XEON **pregunta al usuario y no crea borrador prematuro**.
- [ ] **Cero descuentos inventados:** Al pedir `"el descuento de siempre"` o un porcentaje, XEON informa que no hay política de descuentos activa y **nunca inventa un porcentaje (`%`) ni rebaja el precio unitario**.
- [ ] **Estado de borrador (`DRAFT`):** XEON nunca dice que el pedido está *aprobado*, *confirmado*, *facturado* ni que el inventario quedó *reservado*.
- [ ] **Higiene de la respuesta al cliente:** En modo `grok`, el cliente **nunca** ve etiquetas internas como `[XEON_TOOL:...]`, nombres de variables ni fragmentos del prompt del sistema.

---

## 5. Cómo reportar un defecto

Si algún paso del guion o del checklist falla durante la validación humana, abre un reporte indicando:

1. **Canal probado:** `uv run xeon` (CLI) o WhatsApp (Kapso).
2. **Mensaje exacto enviado** y **transcripción o captura** de la respuesta recibida (incluyendo el turno inmediatamente anterior si fue una falla de contexto).
3. **Resultado esperado vs. resultado obtenido** (por ejemplo: *"En el Paso 3 esperaba subtotal `$670.500,00 COP` para 20 bultos y 50 m de alambre, pero respondió..."*).
4. **Hora aproximada** de la prueba y salida de `curl.exe http://127.0.0.1:8000/health` (o del comando `s` en `uv run xeon`).

> [!CAUTION]
> **Seguridad al reportar:** Nunca incluyas en capturas, grabaciones ni reportes el contenido de `.env`, `secrets/grok_api_key.txt`, `secrets/kapso_webhook_secret.txt` ni ninguna cadena con formato de clave (`sk-...` o `KAPSO_API_KEY`). Si muestras la terminal en el video, usa el comando `c` o `s` de `uv run xeon`, que solo informa `file configured` sin revelar secretos.

---

## 6. Estado del Hito #2

- [x] **Implementación:** 3 herramientas (`search_products`, `get_stock_by_branches`, `create_quote_draft`) y correcciones `E1`–`E11` integradas con `grok-4.6`; `E12` y `E13` en cierre.
- [x] **Validación automatizada:** Suite determinista y corrida en vivo `9037d9a6f893bd1e` ejecutadas; repetición focalizada de escenarios en curso.
- [ ] **Listo para QA humano:** *(Lo marca el orquestador tras cerrar la repetición focalizada de `E12`/`E13`).*
- [ ] **Validación humana:** *(Pendiente de ejecución y grabación por el QA humano externo).*

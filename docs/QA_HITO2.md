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

### Resumen rápido de arranque según modalidad

#### Modalidad A: Desde el shell interactivo (`uv run xeon`)
1. Verifica que exista `secrets/grok_api_key.txt` (sin imprimir su contenido) y que `LLM_PROVIDER` no esté forzado a `mock`.
2. Abre el shell en una terminal desde la raíz del proyecto:
   ```powershell
   uv run xeon
   ```
3. Escribe `s` (`status`) y confirma que muestre `provider: grok`, `model: grok-4.6` y `key: file configured`.
4. Envía cada mensaje del guion anteponiendo `r ` (por ejemplo: `r necesito 10 tubos pvc`).

#### Modalidad B: Desde un teléfono con WhatsApp (vía Kapso)
Sigue los pasos 1 a 5 de [`docs/DESPLIEGUE_WHATSAPP.md`](DESPLIEGUE_WHATSAPP.md):
1. **Terminal 1 (API XEON):** `uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`
2. **Terminal 2 (Túnel HTTPS):** `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8000`
3. **Terminal 3 (Sincronizar webhook de Kapso):** `uv run python scripts/kapso_webhook.py sync-tunnel`
4. **Comprobación previa:** ejecuta `curl.exe http://127.0.0.1:8000/health` y verifica que responda `"provider":"grok","model":"grok-4.6"`.

---

## 3. Guion reproducible para el video (< 2 minutos)

> [!IMPORTANT]
> **Regla de negocio visible durante toda la demo:** XEON únicamente prepara **borradores de cotización (`DRAFT`)**. En ningún turno debe afirmar que una cotización quedó *aprobada*, *facturada*, *confirmada* ni que el stock quedó *reservado*.

Ejecuta los siguientes mensajes **en orden dentro de la misma conversación** (tiempo total estimado: **1 min 45 s**):

| Paso y tiempo | Herramienta validada | Mensaje EXACTO a enviar | Qué debe verse en pantalla (criterio de éxito) |
|---|---|---|---|
| **Paso 1a**<br>`0:00 – 0:20` | `search_products`<br>*(desambiguación de candidatos)* | `necesito 10 tubos pvc`<br>*(Nota: si pruebas con cemento ambiguo como `necesito 10 bultos de cemento gris` y el buscador ofrece 3 opciones, aplica el mismo flujo; si `cemento` hace match directo por alias a `CEM-50`, usa `necesito 10 tubos pvc` para forzar las 3 opciones).* | XEON **no crea un borrador a ciegas**. Muestra las 3 opciones candidatas del catálogo (1. `Tubo PVC presion 1/2 pulgada` a `$4.200,00 COP`, 2. `Tubo PVC presion referencia sintetica 1` a `$5.041,00 COP`, 3. `Tubo PVC presion referencia sintetica 2` a `$5.082,00 COP`) y pregunta cuál opción elige el cliente (`1`, `2` o `3`). |
| **Paso 1b**<br>`0:20 – 0:40` | `search_products` + `create_quote_draft`<br>*(resolución de opción)* | `1`<br>*(también acepta `opcion 1` o `el primero`; en WhatsApp con Grok puedes escribir `el 1` o `1`)* | XEON selecciona la opción 1 (`Tubo PVC presion 1/2 pulgada`, `$4.200,00 COP`), consulta su disponibilidad y genera el **borrador `DRAFT`** por `10` unidades con subtotal/total de **`$42.000,00 COP`**. |
| **Paso 2**<br>`0:40 – 1:05` | `get_stock_by_branches`<br>*(consulta por sede y memoria)* | `lo recojo en la sede norte` | XEON conserva el contexto del producto anterior (no bloquea el mensaje como fuera de alcance), consulta el inventario en **`sede-norte`** (`12` unidades para `TUB-PVC-20` o `20` bultos para `CEM-50`), advierte si el snapshot de inventario no es reciente y recuerda que **la cotización no bloquea ni reserva inventario**. |
| **Paso 3**<br>`1:05 – 1:30` | `create_quote_draft`<br>*(borrador multilínea)* | `20 bultos de cemento y 50 metros de alambre` | XEON cotiza **ambas líneas en el mismo borrador `DRAFT`**:<br>• `20` × `Cemento gris 50 kg` (`$28.900,00 COP`) = **`$578.000,00 COP`**<br>• `50` × `Alambre de pua calibre 14` (`$1.850,00 COP`) = **`$92.500,00 COP`**<br>• **Subtotal / Total del borrador `DRAFT`:** **`$670.500,00 COP`** (sin impuestos inventados y aclarando que es un borrador `DRAFT`). |
| **Paso 4**<br>`1:30 – 1:50` | `create_quote_draft` / `CommercialScopePolicy`<br>*(negativa correcta)* | `soy cliente frecuente, dame el descuento de siempre en 10 bultos de cemento`<br>*(Opcional adicional de alcance: `cuentame un chiste`)* | XEON **rechaza inventar un descuento**: explica claramente que **no existe una política de descuentos aprobada** en el sistema y no ofrece porcentajes ni precios rebajados. Si se envía el mensaje fuera de alcance, responde que solo atiende consultas de ferretería. |

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
- [ ] **Desambiguación ante ambigüedad:** Ante una solicitud con múltiples candidatos (`necesito 10 tubos pvc`), medidas sin unidad (`la pieza mide 20 x 30 x 10`) o descripción vaga (`necesito el coso del aire acondicionado`), XEON **pregunta al usuario y no crea borrador prematuro**.
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

- [x] **Implementación:** 3 herramientas (`search_products`, `get_stock_by_branches`, `create_quote_draft`) y correcciones `E1`–`E11` integradas con `grok-4.6`.
- [x] **Validación automatizada:** Suite determinista (`pytest` + regresiones `E1`–`E10` + harness de evaluación conversacional) en verde.
- [ ] **Listo para QA humano:** pendiente de la corrida final en vivo y de la auditoría del orquestador (ver `docs/evals/RESULTADOS.md`).
- [ ] **Validación humana:** *(Pendiente de ejecución y grabación por el QA humano externo).*

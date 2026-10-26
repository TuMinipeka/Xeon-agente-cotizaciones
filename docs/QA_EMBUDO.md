# Guía de prueba manual del embudo guiado por WhatsApp (D14)

> [!IMPORTANT]
> **Estado de ejecución:** Esta guía de pruebas manuales está alineada con el contrato [D14](../wiki/pages/embudo-cotizacion.md) y su implementación verificada en `src/xeon/agent/guided_funnel.py` tras los ajustes de Codex (commit `dcfc794`).
>
> **Comportamiento interactivo:**
> - Los pasos `inicio`, `cantidad`, `mas`, `entrega` y `resumen` ofrecen exactamente **3 botones** de respuesta rápida (*reply buttons*).
> - El paso `cantidad` interpola el nombre completo del producto y ofrece opciones sugeridas según su unidad (`bulto`: 10/20/Otra; `metro`: 10/50/Otra; `unidad`: 1/2/Otra).
> - Las consultas sobre políticas de la ferretería (horario, domicilio, recogida, pago, IVA, descuentos, vigencia) se responden desde `config/policies/whatsapp.yaml` y repiten las opciones del paso activo sin alterar el carrito.
> - El comando de texto `asesor` está disponible en cualquier paso. `Cancelar` y `Confirmar` se eligen solo
>   por su botón (`global:cancel`, `summary:confirm`) o por su número; escribir «cancelar» o «confirmar» no
>   las activa (revisión de seguridad M7).

---

## 1. Preparación del entorno de prueba

Para ejecutar estas pruebas desde un teléfono móvil real con WhatsApp conectado al sandbox de Kapso:

1. **Guía de despliegue e infraestructura:** Siga los pasos detallados en [docs/DESPLIEGUE_WHATSAPP.md](DESPLIEGUE_WHATSAPP.md) para levantar la API local de XEON y el túnel HTTPS con `cloudflared`.
2. **Servicios requeridos:**
   - API de XEON activa en puerto local (`http://localhost:8000`).
   - Túnel seguro `cloudflared` activo redirigiendo tráfico HTTPS al puerto 8000.
   - Webhook de Kapso configurado apuntando a la URL del túnel (`/v1/channels/whatsapp/kapso/webhook`).
   - Envío de mensajes activo en la configuración (`WHATSAPP_SEND_ENABLED=true`).
3. **Seguridad y confidencialidad:**
   - **Nunca** digite ni exponga tokens, API keys ni secretos en la consola o en capturas de pantalla de prueba.
   - No comparta números de teléfono personales ni datos de clientes reales. Use el sandbox oficial provisto por Kapso.

---

## 2. Recorridos de prueba manual (R1 a R6)

### R1. Recorrido feliz por botones (cotización completa)

- **Objetivo:** Verificar el flujo guiado estándar utilizando exclusivamente interacción mediante botones y listas interactivas de WhatsApp.
- **Catálogo de prueba:** Cemento gris 50 kg (`CEM-50`, valor unitario $28.900 COP) y Pala redonda mango de fibra (`PAL-RED-FIB`, valor unitario $43.700 COP).
- **Cálculo esperado:**
  - 20 bultos de cemento: 20 x $28.900 = $578.000 COP
  - 1 pala redonda: 1 x $43.700 = $43.700 COP
  - **Total de la cotización:** $621.700 COP

| Paso | Acción del probador | Respuesta esperada de XEON | Opciones interactivas esperadas (ID / Título) |
|---|---|---|---|
| 1 | Inicia conversación o pulsa botón inicial | Pregunta de bienvenida e intención general:<br>«¿Qué necesitas?» | 3 botones de respuesta rápida:<br>• `start:products`: `[Cotizar productos]`<br>• `start:project`: `[Proyecto u obra]`<br>• `global:advisor`: `[Hablar con asesor]` |
| 2 | Pulsa `[Cotizar productos]` (`start:products`) | Solicita nombre del producto:<br>«¿Qué producto buscas? Escribe nombre o referencia.» | Campo de texto libre activo |
| 3 | Escribe: `cemento` | Presenta lista interactiva de productos coincidentes:<br>«Elige una referencia:\n¿Qué producto buscas? Escribe nombre o referencia.» | Lista interactiva con opciones del catálogo, incluyendo:<br>• `product:CEM-50`: `Cemento gris 50 kg` |
| 4 | Selecciona `Cemento gris 50 kg` (`product:CEM-50`) | Pregunta por la cantidad deseada nombrando el producto:<br>«¿Cuántas unidades de Cemento gris 50 kg?» | 3 botones de cantidad (unidad bulto):<br>• `quantity:10`: `[10]`<br>• `quantity:20`: `[20]`<br>• `quantity:other`: `[Otra]` |
| 5 | Pulsa `[20]` (`quantity:20`) | Confirma adición de línea, muestra resumen del carrito ($578.000 COP) y pregunta:<br>«¿Algo más para tu cotización?» | 3 botones de continuidad:<br>• `more:add`: `[Agregar otro]`<br>• `more:view`: `[Ver cotizacion]`<br>• `more:modify`: `[Modificar]` |
| 6 | Pulsa `[Agregar otro]` (`more:add`) | Solicita el siguiente producto:<br>«¿Qué producto buscas? Escribe nombre o referencia.» | Campo de texto libre activo |
| 7 | Escribe: `pala` | Presenta lista de productos coincidentes con «pala»:<br>«Elige una referencia:\n¿Qué producto buscas? Escribe nombre o referencia.» | Lista interactiva con opciones del catálogo, incluyendo:<br>• `product:PAL-RED-FIB`: `Pala redonda mango de fi`<br>*(Título en lista limitado a 24 caracteres por tope de WhatsApp).* |
| 8 | Selecciona `Pala redonda mango de fi` (`product:PAL-RED-FIB`) | Pregunta por la cantidad nombrando el producto completo:<br>«¿Cuántas unidades de Pala redonda mango de fibra?» | 3 botones de cantidad adaptados a herramienta unitaria:<br>• `quantity:1`: `[1]`<br>• `quantity:2`: `[2]`<br>• `quantity:other`: `[Otra]` |
| 9 | Pulsa `[1]` (`quantity:1`) | Confirma adición de pala, muestra carrito con total acumulado ($621.700 COP) y pregunta:<br>«¿Algo más para tu cotización?» | 3 botones de continuidad:<br>• `more:add`: `[Agregar otro]`<br>• `more:view`: `[Ver cotizacion]`<br>• `more:modify`: `[Modificar]` |
| 10 | Pulsa `[Ver cotizacion]` (`more:view`) | Pregunta método de entrega:<br>«¿Cómo lo recibes?» | 3 botones de entrega:<br>• `delivery:pickup`: `[Recoger en sede]`<br>• `delivery:home`: `[Domicilio]`<br>• `global:advisor`: `[Hablar con asesor]` |
| 11 | Pulsa `[Recoger en sede]` (`delivery:pickup`) | Pregunta sede para retiro:<br>«¿En qué sede lo recoges? Stock sujeto a confirmación.» | Lista interactiva de sedes disponibles con estado de stock:<br>• `branch:sede-norte`: `Norte: disponible`<br>• `branch:sede-centro`: `Centro: disponible`<br>• `branch:sede-sur`: `Sur: disponible` |
| 12 | Selecciona `[Norte: disponible]` (`branch:sede-norte`) | Pregunta método de pago:<br>«¿Cómo prefieres pagar?» | Lista interactiva de métodos según política:<br>• `payment:0`: `Efectivo`<br>• `payment:1`: `Transferencia`<br>• `payment:2`: `Tarjeta débito/crédito`<br>• `payment:3`: `Nequi` |
| 13 | Selecciona `[Efectivo]` (`payment:0`) | Muestra resumen del borrador con tabla detallada (2 líneas), total **$621.700 COP**, y detalles de política:<br>«Entrega: recogida (sede-norte). Pago: Efectivo. Vigencia: 3 días. IVA: pendiente.» | 3 botones de cierre:<br>• `summary:confirm`: `[Confirmar]`<br>• `summary:modify`: `[Modificar]`<br>• `global:cancel`: `[Cancelar]` |
| 14 | Pulsa `[Confirmar]` (`summary:confirm`) | Mensaje de confirmación final:<br>«Recibimos tu confirmación. Un asesor revisará y te contactará.» | Sin botones adicionales (`kind="text"`).<br>Estado registrado en base de datos: `CONFIRMADO_POR_CLIENTE`. |

- **Criterio de aprobación:** El borrador queda en estado `CONFIRMADO_POR_CLIENTE` ante asesor (nunca `APPROVED_FOR_BILLING` ni «facturado»), con total exacto de $621.700 COP.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R2. Entrada con texto libre en pasos cerrados

- **Objetivo:** Comprobar que cuando el usuario escribe texto natural en pasos con opciones cerradas (en lugar de presionar los botones o usar IDs interactivos), el clasificador asigna la intención al enum correspondiente sin romperse ni reiniciar el flujo.

| Paso probado | Entrada del probador (texto libre) | Comportamiento y mapeo esperado en código |
|---|---|---|
| Paso `cantidad` | Escribe: `20` o `veinte` | Si es numérico se captura directamente (`amount = Decimal(20)`); si es palabra, el clasificador asigna a `quantity:20` y avanza a `mas`. |
| Paso `entrega` | Escribe: `voy a recoger en la tienda` o `recoger` | Clasifica a la opción `delivery:pickup` (`Recoger en sede`) y avanza al paso `sede`. |
| Paso `sede` | Escribe: `en la del norte` o `norte` | Clasifica a la sede `branch:sede-norte` y avanza al paso `pago`. |
| Paso `pago` | Escribe: `con efectivo` o `plata en mano` | Clasifica al método `payment:0` (`Efectivo`) y avanza al paso `resumen`. |

- **Criterio de aprobación:** En cada paso cerrado, el texto libre se clasifica dentro del enum permitido del paso sin que el agente empiece a divagar o inventar respuestas abiertas.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R3. Modificación de ítems desde el resumen

- **Objetivo:** Validar la capacidad de modificar cantidades o eliminar líneas del borrador desde la pantalla de resumen, recalculando totales y precios de forma estricta por backend.

| Paso | Acción del probador | Respuesta esperada de XEON | Opciones interactivas esperadas |
|---|---|---|---|
| 1 | Se ubica en el paso `resumen` de R1 (20 cementos + 1 pala, total $621.700 COP) | Muestra resumen de cotización completo | 3 botones de resumen:<br>• `summary:confirm`: `[Confirmar]`<br>• `summary:modify`: `[Modificar]`<br>• `global:cancel`: `[Cancelar]` |
| 2 | Escribe comando libre: `déjalo en 15, quita la pala` (o pulsa `[Modificar]` / `summary:modify`) | El backend ejecuta `IntentKind.MODIFICAR_CANTIDAD` (15 bultos) y `IntentKind.QUITAR` (pala). Confirma la mutación, muestra carrito actualizado y retorna a `mas` | 3 botones de paso `mas`:<br>• `more:add`: `[Agregar otro]`<br>• `more:view`: `[Ver cotizacion]`<br>• `more:modify`: `[Modificar]` |
| 3 | Pulsa `[Ver cotizacion]` (`more:view`) y avanza por entrega/sede/pago hasta el nuevo resumen | Tabla con 1 sola línea (15 bultos Cemento gris 50 kg a $28.900 c/u).<br>**Total exacto: $433.500 COP** | 3 botones de resumen:<br>• `summary:confirm`: `[Confirmar]`<br>• `summary:modify`: `[Modificar]`<br>• `global:cancel`: `[Cancelar]` |
| 4 | Pulsa `[Confirmar]` (`summary:confirm`) | Mensaje de recepción de confirmación ante asesor:<br>«Recibimos tu confirmación. Un asesor revisará y te contactará.» | Estado final del borrador: `CONFIRMADO_POR_CLIENTE` por un total exacto de $433.500 COP |

- **Criterio de aprobación:** La pala queda totalmente excluida, la cantidad de cemento pasa a 15 bultos y el total es estrictamente $433.500 COP (15 x $28.900).
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R4. Desvío fuera de alcance durante el flujo

- **Objetivo:** Verificar que ante consultas fuera de alcance en medio del embudo, XEON redirige inmediatamente con una sola línea estandarizada y vuelve a ofrecer las opciones del paso en curso sin perder el estado de la cotización.

| Paso en curso | Mensaje del probador (fuera de alcance) | Respuesta esperada de XEON |
|---|---|---|
| En paso `cantidad` | `¿Cómo está el clima hoy en Bogotá?` o `¿quién ganó el partido?` | 1. Mensaje de redirección estricto: «Solo puedo ayudarte con tu cotización.»<br>2. Reitera inmediatamente la pregunta del paso con su nombre («¿Cuántas unidades de Cemento gris 50 kg?») y sus 3 botones (`[10]`, `[20]`, `[Otra]`). |
| En paso `sede` | `¿Venden almuerzos ejecutivos cerca?` | 1. Mensaje de redirección estricto: «Solo puedo ayudarte con tu cotización.»<br>2. Reitera la pregunta («¿En qué sede lo recoges? Stock sujeto a confirmación.») y la lista de sedes disponibles. |

- **Criterio de aprobación:** Cero divagaciones sobre el tema externo, mensaje de redirección de una sola línea y persistencia del estado y opciones del paso actual.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R5. Consulta de políticas demo de la ferretería

- **Objetivo:** Verificar que las consultas sobre condiciones comerciales se responden desde la configuración de políticas (`config/policies/whatsapp.yaml`), reiterando las opciones del paso en curso y manteniendo intacto el borrador.

| Consulta del probador | Política evaluada | Respuesta esperada según YAML del tenant |
|---|---|---|
| `¿Qué horario de atención tienen?` | Horarios de atención | Responde según política:<br>«Horario: lunes a viernes: 7:00-18:00; sábado: 7:00-13:00; domingo: pendiente de confirmar con un asesor.»<br>Seguido de la pregunta y opciones del paso activo. |
| `¿Tienen servicio a domicilio y cuánto cuesta?` | Domicilios | Responde según política:<br>«Domicilio: disponible; lo confirma un asesor según la zona.»<br>Seguido de la pregunta y opciones del paso activo. |
| `¿El total incluye IVA?` | Tratamiento de IVA | Responde según política:<br>«IVA: pendiente.»<br>Seguido de la pregunta y opciones del paso activo. |
| `¿Qué descuento me dan por comprar 50 bultos?` | Política de descuentos | Responde según política:<br>«Politica de descuentos: asesor.»<br>Seguido de la pregunta y opciones del paso activo. |

- **Criterio de aprobación:** Respuestas exactas a las plantillas demo del tenant; el borrador no se modifica y se repiten las opciones del paso en curso.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R6. Salidas del flujo (asesor humano y cancelación)

- **Objetivo:** Verificar que el usuario puede solicitar atención humana o cancelar el proceso en cualquier momento del recorrido, ya sea por botón interactivo o comando escrito.

| Escenario | Acción del probador | Comportamiento esperado de XEON en código |
|---|---|---|
| Solicitud de asesor | En cualquier paso, pulsa `[Hablar con asesor]` (`global:advisor`) o escribe «asesor» | Responde: «Un asesor te contactará.» y notifica el evento `advisor_requested`. Estado pasa a `asesor`. |
| Cancelación de cotización | Pulsa `[Cancelar]` (`global:cancel`) o responde con su número; escribir «cancelar» no la activa | Responde: «Cotización cancelada.» Estado pasa a `cancelado`. |

- **Criterio de aprobación:** Transición limpia hacia atención humana o descarte del borrador sin bloqueos ni reintentos forzados.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

## 3. Invariantes generales a observar en todo momento

Durante toda la sesión de pruebas manuales, el evaluador de QA debe vigilar el cumplimiento estricto de los siguientes límites técnicos y de producto:

1. **Formato de texto de WhatsApp:**
   - **Prohibido `**` (doble asterisco):** WhatsApp interpreta la negrita únicamente con asterisco simple (`*texto*`). El uso de `**` denota fuga de Markdown no adaptado.
   - **Prohibido `###` o `#` (encabezados Markdown):** No tienen formato enriquecido en WhatsApp y aparecen como texto sucio.
2. **Límites de componentes interactivos (WhatsApp Cloud API):**
   - **Botones rápidos (*reply buttons*):** Máximo 3 botones por mensaje. Cada título debe tener máximo 20 caracteres.
   - **Listas interactivas (*list messages*):** Máximo 10 filas en total. Cada título de fila debe tener máximo 24 caracteres.
3. **Límites de seguridad y estado comercial:**
   - XEON **nunca** debe declarar una cotización como «aprobada», «reservada» o «facturada».
   - El estado tras la confirmación del cliente es estrictamente `CONFIRMADO_POR_CLIENTE`, sujeto a validación humana posterior (`APPROVED_FOR_BILLING`).

---

## 4. Plantilla para reporte de defectos

Si durante las pruebas manuales se detecta alguna discrepancia con el contrato D14 o fallo en las invariantes, registre el hallazgo con la siguiente estructura:

```markdown
### Defecto: [DEF-EMBUDO-XXX] <Título breve del defecto>

- **Fecha y hora:** AAAA-MM-DD HH:MM
- **Recorrido / Paso:** (ej. R1 - Paso 13: Resumen de cotización)
- **Tipo de defecto:** [ ] Formato no admitido (**, ###) / [ ] Límite interactivo superado / [ ] Cálculo erróneo / [ ] Divagación fuera de alcance / [ ] Estado comercial inválido
- **Mensaje o acción del probador:**
  `<texto o botón pulsado>`
- **Respuesta obtenida de XEON:**
  `<texto recibido en WhatsApp o adjuntar captura>`
- **Respuesta esperada según contrato D14:**
  `<descripción de lo que debió responder>`
- **Captura de pantalla:** (Adjuntar imagen asegurando que ningún número telefónico personal ni clave sea visible).
```

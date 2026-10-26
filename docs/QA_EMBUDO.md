# Guía de prueba manual del embudo guiado por WhatsApp (D14)

> [!IMPORTANT]
> **Estado de ejecución:** Esta guía de pruebas manuales fue redactada contra la especificación contractual [D14](../wiki/pages/embudo-cotizacion.md). Debe ejecutarse por el equipo de QA humano una vez que la implementación del embudo guiado esté completamente fusionada e integrada en la rama de trabajo.

---

## 1. Preparación del entorno de prueba

Para ejecutar estas pruebas desde un teléfono móvil real con WhatsApp conectado al sandbox de Kapso:

1. **Guía de despliegue e infraestructura:** Siga los pasos detallados en [docs/DESPLIEGUE_WHATSAPP.md](DESPLIEGUE_WHATSAPP.md) para levantar la API local de XEON y el túnel HTTPS con `cloudflared`.
2. **Servicios requeridos:**
   - API de XEON activa en puerto local (`http://localhost:8000`).
   - Túnel seguro `cloudflared` activo redirigiendo tráfico HTTPS al puerto 8000.
   - Webhook de Kapso configurado apuntando a la URL del túnel (`/v1/integrations/kapso/webhook`).
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
  - 20 bultos de cemento: $20 \times \$28.900 = \$578.000\text{ COP}$
  - 1 pala redonda: $1 \times \$43.700 = \$43.700\text{ COP}$
  - **Total de la cotización:** $\$621.700\text{ COP}$

| Paso | Acción del probador | Respuesta esperada de XEON | Opciones interactivas esperadas |
|---|---|---|---|
| 1 | Inicia conversación o pulsa botón inicial | Pregunta de bienvenida e intención general («¿Qué necesitas?») | 3 botones: `[Cotizar productos]`, `[Proyecto u obra]`, `[Hablar con asesor]` |
| 2 | Pulsa `[Cotizar productos]` | Solicita nombre del producto («¿Qué producto buscas?») | Campo de texto libre activo |
| 3 | Escribe: `cemento` | Presenta lista interactiva de productos coincidentes | Lista interactiva con opciones del catálogo, incluyendo `Cemento gris 50 kg` |
| 4 | Selecciona `Cemento gris 50 kg` | Pregunta por la cantidad deseada («¿Cuántas unidades de Cemento gris 50 kg?») | Botones sugeridos: `[10]`, `[20]`, `[Otra]` |
| 5 | Pulsa `[20]` | Confirma adición y pregunta si requiere algo más («¿Algo más?») | 3 botones: `[Agregar otro]`, `[Ver cotización]`, `[Modificar]` |
| 6 | Pulsa `[Agregar otro]` | Solicita el siguiente producto («¿Qué producto buscas?») | Campo de texto libre activo |
| 7 | Escribe: `pala` | Presenta lista de productos coincidentes con «pala» | Lista interactiva con opciones, incluyendo `Pala redonda mango de fibra` |
| 8 | Selecciona `Pala redonda mango de fibra` | Pregunta por la cantidad («¿Cuántas unidades de Pala redonda mango de fibra?») | Botones sugeridos: `[1]`, `[2]`, `[Otra]` |
| 9 | Pulsa `[1]` | Confirma adición y pregunta paso a seguir («¿Algo más?») | 3 botones: `[Agregar otro]`, `[Ver cotización]`, `[Modificar]` |
| 10 | Pulsa `[Ver cotización]` | Pregunta método de entrega («¿Cómo lo recibes?») | 2 botones: `[Recoger en sede]`, `[Domicilio]` |
| 11 | Pulsa `[Recoger en sede]` | Pregunta sede para retiro («¿En qué sede?») | Lista de sedes disponibles (ej. `[Sede Norte]`, `[Sede Centro]`) con estado de stock |
| 12 | Selecciona `[Sede Norte]` | Pregunta método de pago («¿Cómo prefieres pagar?») | Lista de métodos de pago (`Efectivo`, `Transferencia`, `Tarjeta débito/crédito`, `Nequi`) |
| 13 | Selecciona `[Efectivo]` | Muestra resumen con tabla detallada (2 líneas), total **$621.700 COP**, sede Norte, pago Efectivo y vigencia | 3 botones: `[Confirmar]`, `[Modificar]`, `[Cancelar]` |
| 14 | Pulsa `[Confirmar]` | Mensaje de confirmación: «Recibimos tu confirmación. Un asesor revisará y te contactará.» | Sin botones adicionales; estado registrado: `CONFIRMADO_POR_CLIENTE` |

- **Criterio de aprobación:** El borrador queda en estado `CONFIRMADO_POR_CLIENTE` ante asesor (nunca `APPROVED_FOR_BILLING` ni «facturado»), con total exacto de $621.700 COP.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R2. Entrada con texto libre en pasos cerrados

- **Objetivo:** Comprobar que cuando el usuario escribe texto natural en pasos con opciones cerradas (en lugar de presionar los botones), el clasificador asigna la intención al enum correspondiente sin romperse ni reiniciar el flujo.

| Paso probado | Entrada del probador (texto libre) | Comportamiento y mapeo esperado |
|---|---|---|
| Paso cantidad | Escribe: `quiero 20 bultos` o `veinte` | Clasifica al valor `20` y avanza exitosamente al paso `mas`. |
| Paso entrega | Escribe: `voy a recoger en la tienda` o `recoger` | Clasifica a la opción `Recoger en sede` y avanza al paso `sede`. |
| Paso sede | Escribe: `en la del norte` o `norte` | Clasifica a la sede `Sede Norte` y avanza al paso `pago`. |
| Paso pago | Escribe: `con efectivo` o `plata en mano` | Clasifica al método `Efectivo` y avanza al paso `resumen`. |

- **Criterio de aprobación:** En cada paso cerrado, el texto libre se clasifica dentro del enum permitido del paso sin que el agente empiece a divagar o inventar respuestas abiertas.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R3. Modificación de ítems desde el resumen

- **Objetivo:** Validar la capacidad de modificar cantidades o eliminar líneas del borrador desde la pantalla de resumen, recalculando totales y precios de forma estricta por backend.

| Paso | Acción del probador | Respuesta esperada de XEON | Opciones interactivas esperadas |
|---|---|---|---|
| 1 | Se ubica en el paso `resumen` de R1 (20 cementos + 1 pala, total $621.700 COP) | Muestra resumen de cotización | 3 botones: `[Confirmar]`, `[Modificar]`, `[Cancelar]` |
| 2 | Pulsa `[Modificar]` o escribe: `déjalo en 15, quita la pala` | Aplica la operación sobre el borrador: actualiza cemento a 15 y elimina la pala redonda | Presenta resumen recalculado o paso `mas` confirmando el cambio |
| 3 | Verifica el nuevo resumen | Tabla con 1 sola línea (15 bultos Cemento gris 50 kg) a $28.900 c/u. **Total exacto: $433.500 COP** | Botones: `[Confirmar]`, `[Modificar]`, `[Cancelar]` |
| 4 | Pulsa `[Confirmar]` | Mensaje de recepción de confirmación ante asesor | Estado final: `CONFIRMADO_POR_CLIENTE` por $433.500 COP |

- **Criterio de aprobación:** La pala queda totalmente excluida, la cantidad de cemento pasa a 15 bultos y el total es estrictamente $433.500 COP (15 x $28.900).
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R4. Desvío fuera de alcance durante el flujo

- **Objetivo:** Verificar que ante consultas fuera de alcance en medio del embudo, XEON redirige inmediatamente con una sola línea estandarizada y vuelve a ofrecer las opciones del paso en curso sin perder el estado de la cotización.

| Paso en curso | Mensaje del probador (fuera de alcance) | Respuesta esperada de XEON |
|---|---|---|
| En paso `cantidad` | `¿Cómo está el clima hoy en Bogotá?` o `¿quién ganó el partido?` | 1. Mensaje de redirección estricto: «Solo puedo ayudarte con tu cotización».<br>2. Reitera inmediatamente las opciones del paso `cantidad` (`[10]`, `[20]`, `[Otra]`). |
| En paso `sede` | `¿Venden almuerzos ejecutivos cerca?` | 1. Mensaje de redirección: «Solo puedo ayudarte con tu cotización».<br>2. Reitera la lista de sedes para seleccionar. |

- **Criterio de aprobación:** Cero divagaciones sobre el tema externo, mensaje de redirección de una sola línea y persistencia del estado y opciones del paso actual.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R5. Consulta de políticas demo de la ferretería

- **Objetivo:** Verificar que las consultas sobre condiciones comerciales se responden según las plantillas demo del contrato (`config/policies/<tenant>.yaml`) y que temas reservados a humanos quedan explícitamente marcados como pendientes de asesor.

| Consulta del probador | Política evaluada | Respuesta esperada según contrato D14 |
|---|---|---|
| `¿Qué horario de atención tienen?` | Horarios de atención | Informa según política: Lunes a viernes 7:00-18:00, sábados 7:00-13:00, domingos cerrado. |
| `¿Tienen servicio a domicilio y cuánto cuesta?` | Domicilios | Informa que el servicio está disponible y que el costo exacto lo confirma un asesor según la zona. |
| `¿El total incluye IVA?` | Tratamiento de IVA | Informa que los precios son de referencia y el valor final de IVA lo confirma un asesor humano. |
| `¿Qué descuento me dan por comprar 50 bultos?` | Política de descuentos | Informa que el agente no otorga descuentos y que cualquier condición especial queda pendiente de revisión por el asesor. |

- **Criterio de aprobación:** Respuestas exactas a las plantillas demo; nunca se prometen descuentos automáticos ni se liquida IVA sin respaldo.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### R6. Salidas del flujo (asesor humano y cancelación)

- **Objetivo:** Verificar que el usuario puede solicitar atención humana o cancelar el proceso en cualquier momento del recorrido.

| Escenario | Acción del probador | Comportamiento esperado de XEON |
|---|---|---|
| Solicitud de asesor | En cualquier paso, pulsa `[Hablar con asesor]` o escribe «asesor» | Responde «Un asesor te contactará» y notifica al asesor humano. No insiste en el embudo automático. |
| Cancelación de cotización | En el paso resumen, pulsa `[Cancelar]` o escribe «cancelar» | Notifica la cancelación del borrador actual y ofrece iniciar una nueva interacción (`inicio`). |

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

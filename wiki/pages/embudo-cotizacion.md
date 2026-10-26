---
tags:
  - xeon/arquitectura
---

# Embudo de cotización guiado y políticas de la ferretería

Contrato que diseñó el orquestador el 2026-10-26 a partir de las decisiones del usuario ([D14](decisiones-pendientes.md)). Estado: **`implementado`** (merge `aa90b94`, 2026-10-26; entrega de Codex, auditoría del orquestador). Antes de implementarse estuvo `aprobado`. Relacionado: [reporte QA de Conde](qa-conde-2026-10-24.md), [conector de la ferretería](conector-ferreteria.md), [evaluación conversacional](evaluacion-conversacional.md).

## Estado real en el código (2026-10-26)

Fuente: nota de entrega de Codex (worktree `xf`, rama `feat/guided-funnel`) y `git log` de `fix/live-qa-defects`. Los números son del informe de Codex; no se repitieron aquí.

- **Único flujo:** `AgentService` delega en una instancia de `GuidedFunnel` (`src/xeon/agent/guided_funnel.py`); API, CLI y Kapso lo comparten. Se eliminaron `GUIDED_FUNNEL_ENABLED`, `IntentInterpreter` y `CustomerResponsePolicy`. Queda un parser local para operaciones evidentes del carrito y datos de proyecto; `CommercialExecutor` y `QuoteCart` siguen calculando y versionando.
- **Grok solo clasifica** el texto libre de los pasos cerrados en una opción permitida o `no_encaja`; en `producto` se busca en el catálogo. Con `mock` siempre devuelve `no_encaja`.
- **Confirmación:** `summary:confirm` guarda `CONFIRMADO_POR_CLIENTE` (distinto de una aprobación humana). El notificador de asesor solo registra `tenant_id` y tipo de evento, sin datos del cliente.
- **Evaluación:** recorridos por id o número para S01–S22 (S21: $621.700; S22: desvío ajeno) y los checks `step_flow`, `options_offered`, `no_freeform_solution` y `confirmation_state`. Informe de Codex: offline **66 PASS / 0 FAIL / 0 ERROR**, suite completa verde, costo LLM 0.
- **Residuales de la segunda corrida en vivo** (S15 peso del bulto, S16 subtotal y cierre, S19 superficie ya confirmada): corregidos en `7617005` con regresiones deterministas. La corrección no se probó en vivo.
- **Defectos hallados al migrar las pruebas** (corregidos): «dejámelo» con tilde no fijaba la cantidad; un tenant sin política de entrega dejaba el paso sin salida; un webhook duplicado podía reinterpretar el número como otra opción. Después, `39afd0a` muestra el stock verificado de la sede elegida.

**Límites vigentes**

- **Kapso `interactive` sin verificar en sandbox:** la documentación pública no muestra un ejemplo de respuesta interactiva v2. El parser acepta `message.interactive.button_reply.id` y `list_reply.id` y las pruebas usan dobles `httpx.MockTransport`; falta cotejar un payload real y el envío con el número conectado. No hubo mensajes reales.
- **Sin corrida en vivo del embudo** con Grok.
- Estado del embudo, carrito y borradores en memoria: un reinicio los pierde y la idempotencia entre procesos distintos requiere estado compartido.
- El paso `proyecto` ofrece una lista léxica preliminar sin cantidades técnicas; el costo del domicilio siempre lo confirma un asesor; la vista de stock por sede aún toma la primera línea confirmada (pendiente: todas las líneas).
- **Discrepancias entre este contrato y el código:** las 5 discrepancias reportadas por agy (opciones globales que forzaban lista, pregunta de cantidad sin producto, cantidades no ajustadas a la unidad, consultas de políticas sin manejador y resumen con 4 opciones) quedaron **resueltas** por Codex en `dcfc794`.

### Ajuste al contrato (dcfc794, 2026-10-26)

Implementado por Codex tras la auditoría de discrepancias de agy:

- **3 botones reales:** en `inicio`, `cantidad`, `mas`, `entrega` y `resumen`.
- **Entrega con 3 botones:** tiene como tercer botón `[Hablar con asesor]` (`global:advisor`) junto a `[Recoger en sede]` y `[Domicilio]` para completar las tres alternativas interactivas estándar de WhatsApp (cambio respecto a la tabla original de D14, que mostraba solo 2 alternativas).
- **Comandos transversales por texto:** «cancelar» y «asesor» funcionan escritos en cualquier paso sin ocupar ranuras de botones.
- **Cantidad con producto y unidad:** nombra el producto completo (`¿Cuántas unidades de <producto>?`) y sugiere opciones según la unidad del catálogo: `bulto` (10/20/Otra), `metro` (10/50/Otra) y `unidad` u otras unidades (1/2/Otra).
- **Políticas desde YAML:** consultas sobre horario, domicilio, recogida, pago, IVA, descuentos y vigencia se responden desde el YAML del tenant en cualquier paso y repiten las opciones activas sin modificar el carrito.
- **Verificación:** gate verde con 66 de 66 escenarios offline (`PASS`).

## Por qué

La primera corrida en vivo del 2026-10-26 dio 1 escenario aprobado y 5 fallidos en S15–S20: con texto libre y Grok real, la interpretación falla (suma en lugar de reemplazar, cantidades cruzadas, desvíos). **Prioridad del usuario:** XEON no divaga ni ofrece soluciones; **guía al cliente hasta armar el borrador** y restringe sus respuestas con opciones visuales.

## Principios

1. **Un paso, unas opciones.** Cada paso muestra *reply buttons* (máximo 3, título de hasta 20 caracteres) o una *list message* (máximo 10 filas, título de hasta 24 caracteres).
2. **Grok solo clasifica.** En cada paso, el texto libre se convierte en **una de las opciones permitidas** de ese paso (enum cerrado) o en `no_encaja`. Grok no genera soluciones. El único paso que acepta texto libre es «producto», que se envía a `search_products`.
3. **Si no encaja, se redirige:** una línea («Solo puedo ayudarte con tu cotización») y se repiten las opciones del paso. Ante una pregunta técnica, se ofrece **[Hablar con asesor]**.
4. **El backend decide:** precios, stock, totales y estado salen del ejecutor y del conector. Las respuestas del embudo se arman con plantillas; el texto del LLM se limita a microcopias opcionales y sin cifras.
5. **El clic en un botón es un dato exacto:** el `id` del botón se procesa sin LLM.

## Pasos (máquina de estados)

| Paso | Mensaje | Opciones | Siguiente |
|---|---|---|---|
| `inicio` | ¿Qué necesitas? | [Cotizar productos] [Proyecto u obra] [Hablar con asesor] | `producto`, `proyecto` o `asesor` |
| `producto` | ¿Qué producto buscas? | texto libre → lista de 3 a 10 coincidencias del catálogo | `cantidad` |
| `cantidad` | ¿Cuántas unidades de X? | [10] [20] [Otra] (sugerencias según la unidad); «Otra» pide un número | `mas` |
| `mas` | ¿Algo más? | [Agregar otro] [Ver cotización] [Modificar] | `producto` o `entrega` |
| `modificar` | ¿Qué línea cambias? | lista de líneas → [Cambiar cantidad] [Quitar] | `mas` |
| `entrega` | ¿Cómo lo recibes? | [Recoger en sede] [Domicilio] | `sede` o `direccion` |
| `sede` | ¿En qué sede? | lista de sedes (`BranchDirectory`) con estado de stock por sede | `pago` |
| `direccion` | Escribe tu barrio o dirección | texto libre (solo se registra; el costo lo confirma un asesor) | `pago` |
| `pago` | ¿Cómo prefieres pagar? | lista de métodos de la política | `resumen` |
| `resumen` | Borrador con tabla de líneas, total, entrega, pago y vigencia | [Confirmar] [Modificar] [Cancelar] | `confirmado`, `modificar` o `cancelado` |
| `proyecto` | ¿Qué vas a construir? | lista de tipos de proyecto → lista preliminar de productos **para elegir** (sin cálculo técnico) → `cantidad`; o [Hablar con asesor] | `cantidad` o `asesor` |
| `asesor` | «Un asesor te contactará» | — | se notifica a un asesor |
| `confirmado` | «Recibimos tu confirmación. Un asesor revisará y te contactará.» | — | el estado del borrador pasa a `CONFIRMADO_POR_CLIENTE` y se notifica a un asesor |

- En cualquier paso, [Hablar con asesor] y «cancelar» están siempre disponibles.
- Si el cliente escribe una operación evidente («quita la pala», «déjalo en 15»), se ejecuta sobre el carrito y se vuelve a `mas`.
- **Confirmación:** XEON **nunca aprueba, reserva ni factura** (principio del producto). `CONFIRMADO_POR_CLIENTE` es un estado nuevo del borrador y es distinto de `APPROVED_FOR_BILLING`, que es humano.

## Políticas por ferretería (`config/policies/<tenant>.yaml`)

Plantilla demo para Colombia (decisión del usuario). Son valores de ejemplo marcados `demo: true`, y cada ferretería real los reemplaza.

```yaml
demo: true
pagos: [Efectivo, Transferencia, Tarjeta débito/crédito, Nequi]
entrega:
  recoger_en_sede: {disponible: true, nota: "Mismo día si hay stock"}
  domicilio: {disponible: true, costo: "lo confirma un asesor según la zona"}
horario: {lunes_a_viernes: "7:00-18:00", sabado: "7:00-13:00", domingo: null}
vigencia_cotizacion_dias: 3
iva: pendiente        # no se calcula IVA; se informa que lo confirma un asesor
descuentos: asesor    # el agente nunca ofrece descuentos
fuera_de_horario: "Tomamos tu cotización y un asesor te responde al abrir"
```

- Un campo en `null` o ausente se responde como «pendiente de confirmar con un asesor». Nunca se inventa.

## Canal (Kapso)

- **Salida:** un puerto de presentación (`Reply`) con `text`, `buttons[]` o `list{sections[]}`. El adaptador de Kapso lo convierte en un mensaje `interactive` de WhatsApp Cloud. El CLI y `/v1/chat` lo muestran como opciones numeradas.
- **Entrada:** el webhook acepta `interactive.button_reply` y `interactive.list_reply` y entrega el `id` exacto al embudo.
- **Riesgo pendiente (spike):** que el sandbox de Kapso envíe y reciba mensajes `interactive`. Solo se contrastó con la documentación y dobles (2026-10-26).

## Evaluador

- El cliente simulado debe poder **pulsar opciones** (`id`) además de escribir.
- **Checks nuevos:**
  - `step_flow`: el paso esperado coincide con el real;
  - `options_offered`: el número de botones y de filas respeta los límites de WhatsApp;
  - `no_freeform_solution`: no hay texto de asesoría fuera de las plantillas;
  - `confirmation_state`: el estado final es `CONFIRMADO_POR_CLIENTE`, nunca aprobado.

Grafo: [capa agente](../graph/hub-agente.md) · [mapa del proyecto](../graph/mapa-proyecto.md)

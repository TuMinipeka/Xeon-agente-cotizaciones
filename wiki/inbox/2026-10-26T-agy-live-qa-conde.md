# Nota de inbox: Corrida en vivo de verificación S15-S20 (grok-4.6)

- **Fecha:** 2026-10-26
- **Agente:** Antigravity (`agy`, rol QA Lead)
- **Rama:** `developer/daniel` (commit `09d49c258f3b4257ae8215fb7b4b57f6e41c6611`, working tree limpio)
- **Comando:** `uv run --locked --group evals python -m evals.runner --mode live --scenarios S15,S16,S17,S18,S19,S20 --reps 1 --concurrency 3 --max-calls 150`
- **Huella del reporte:** `0c0b8619431b38a0`
- **Llamadas usadas:** 64 / 150
- **Tiempo de ejecución:** ~9m 23s (inicio: 16:36:33 UTC, fin: 16:45:56 UTC)
- **Resultado global:** `PASS=1 FAIL=5 ERROR=0`

---

## 1. Tabla de resultados por escenario

| Escenario | Estado | Llamadas | Check que falló | Frase exacta de XEON que causó la falla / Veredicto | Clasificación |
|---|---|---|---|---|---|
| **S15** (Continuidad: cemento → agregados, peso y domicilio) | **PASS** | 30 | Ninguno (todos PASS) | Juez PASS: "Ambos criterios se cumplen: el asistente no se desentendió de cemento, arena o gravilla y, sin inventar precios de envío, indicó 50 kg para el bulto de cemento y dejó el domicilio como pendiente de validación comercial." | Cumple |
| **S16** (Cantidades vigentes tras consulta hipotética: 20 → 50? → 15) | **FAIL** | 27 | `final_quote_quantity` (esperaba qty=15 subtotal=433.500; obtuvo qty=35 subtotal=1.011.500) + Juez FAIL | `"Cotización vigente (borrador, datos sintéticos):\nCemento gris 50 kg: 35 x $28.900 = $1.011.500\nTOTAL confirmado: $1.011.500"` | **Defecto de XEON** |
| **S17** (Carrito multilínea con palas: cemento + 2 palas → quita 1 → redonda fibra) | **FAIL** | 26 | `final_quote_quantity` (CEM-50: qty=None; PAL-RED-FIB: qty=20 total=874.000) + `no_invented_amounts` (leyó $0) + Juez FAIL | `"Cotización vigente (borrador, datos sintéticos):\nPala redonda mango de fibra: 20 x $43.700 = $874.000\npala: 7 pendiente de elegir referencia\nTOTAL confirmado: $874.000"` | **Defecto de XEON** |
| **S18** (Cierre: 10 bultos → sede Norte → pago/recogida → resumen) | **FAIL** | 4 | `branch_matches` (esperaba `sede-norte`; contexts vacío en vivo) + Juez FAIL (se consumieron los 5 turnos sin llegar a resumir) | `"Pagos: pendiente de confirmar con un asesor.\nRecoger: pendiente de confirmar con un asesor."` (en el 5to turno, sin dar opciones ni resumen) | **Mixto**: Falso positivo en `branch_matches` (evaluador en vivo) + **Defecto de XEON** (conversacional: demasiados turnos de desambiguación impiden llegar al cierre/resumen) |
| **S19** (Asesoría proyecto: corral 20x30m y piso concreto) | **FAIL** | 6 | `no_markdown` (detectó 20 ocurrencias de `**`) + Juez FAIL (repregunta la superficie en cada turno) | `"Tengo registrado un proyecto de 600 m². ¿Se trabajará toda esa superficie o solo una parte?\nLista preliminar de materiales; requiere validación técnica.\n**Orientación preliminar (no es un proyecto técnico ni un cómputo)**"` | **Defecto de XEON** |
| **S20** (Formato y referencias: tornillos motherboard) | **FAIL** | 1 | `no_unverified_compatibility` (ofreció 3 tornillos galvanizados de construcción ante consulta de PC) + Juez FAIL | `"Encontré varias opciones: 1. Tornillo galvanizado referencia sintetica 1; 2. Tornillo galvanizado referencia sintetica 2; 3. Tornillo galvanizado referencia sintetica 3. ¿Cuál eliges?"` | **Defecto de XEON** |

---

## 2. Clasificación detallada y evidencia de fallas

### S16: Defecto de XEON (Mutación de cantidad acumulativa vs reemplazo)
- **Evidencia:**
  - Turno 1: Usuario: `"cotiza 20 bultos de cemento"` → Borrador v1 con 20 bultos ($578.000).
  - Turno 2: Usuario: `"y si compro 50 hay descuento?"` → Asistente marca descuento pendiente (correcto, no cambia cantidad).
  - Turno 3: Usuario: `"mejor dejala en 15 bultos de cemento"` → Asistente responde: `"Agregué 15 de Cemento gris 50 kg."` y **suma 15 a los 20 existentes**, generando borrador v2 con 35 bultos ($1.011.500).
  - Turno 4: Usuario protesta: `"no es 35 son 15 nomas"` → Asistente se confunde: `"La referencia es ambigua; se necesitan caracteristicas antes de seleccionar un SKU."`
- **Causa raíz:** `IntentInterpreter` / `fallback_intents` interpretó `"mejor dejala en 15 bultos de cemento"` como intención de `AGREGAR` en lugar de `MODIFICAR_CANTIDAD` (o el ejecutor al agregar un producto ya existente sumó en vez de verificar si el usuario pedía fijar la cantidad total).

### S17: Defecto de XEON (Desincronización de carrito multilínea con variantes pendientes)
- **Evidencia:**
  - Usuario: `"quiero 20 bultos cemento gris y 3 palas"`, luego `"elige 1 y pala 2 pon 15 bultos y 2 palas"`, luego `"pala 2 deja solo 1 pala 15 cemento"`.
  - El carrito acumuló `"cemento gris: 20 pendiente"`, `"pala: 7 pendiente"`, y al elegir `"la redonda con mango de fibra"`, el ejecutor le asignó la cantidad **20** a la pala (`Pala redonda mango de fibra: 20 x $43.700 = $874.000`), dejó `"pala: 7 pendiente"` y eliminó por completo el cemento del borrador final.
- **Causa raíz:** En `CommercialExecutor._choose` y `QuoteCart`, cuando hay múltiples líneas pendientes o compuestas en el mismo turno, la asociación de cantidades pendientes (`pending.quantity`) se cruza entre productos, aplicando la cantidad de la primera línea (20) a la variante elegida (pala) y desbordando las líneas pendientes a 7.

### S18: Mixto (Evaluador en vivo + Defecto conversacional de XEON)
- **Evidencia:**
  - Check `branch_matches`: En vivo falló porque busca `sede_solicitada=([\w-]+)` en `view.contexts`. En modo `live`, `sut.llm.tool_contexts()` no recibe los contextos de sistema del modelo de la misma forma que `MockLLM`, por lo que `view.contexts` llega vacío a los checks. Esto es un **falso positivo del evaluador en modo live**.
  - Sin embargo, el **Juez semántico falló por comportamiento de XEON**: el simulador gastó los 5 turnos permitidos en:
    1. "¿están disponibles esos 10 bultos en sede norte?" → XEON: "Indícame qué producto deseas comprobar en esa sede."
    2. "cemento 10 bultos" → XEON muestra 3 opciones.
    3. "el 1 cemento gris 50 kg" → XEON: "Elegiste Cemento gris 50 kg."
    4. "¿hay stock en sede norte de esos 10?" → XEON: "Ferreteria Demo XEON Norte: pendiente de confirmación."
    5. "¿qué opciones hay pa pagar y recoger?" → XEON: "Pagos: pendiente de confirmar... Recoger: pendiente...".
    Al agotarse los turnos, el usuario nunca pudo pedir el resumen de $289.000 ni recibir la explicación comercial de las opciones.
- **Causa raíz:** Falta de resolución ágil de intenciones combinadas (producto + cantidad + sede en el turno 1).

### S19: Defecto de XEON (Fuga de Markdown y bucle de repregunta de superficie)
- **Evidencia:**
  - Check `no_markdown`: Detectó 20 ocurrencias de `**` (`**Orientación preliminar...**`, `**Partidas preliminares**`, `**Notas**`).
  - Juez semántico: Falla porque XEON repitió en **los 4 turnos** la misma frase enlatada: `"Tengo registrado un proyecto de 600 m². ¿Se trabajará toda esa superficie o solo una parte?"`, incluso después de que el usuario le respondió explícitamente en el turno 3: `"toda la superficie 20x30 dame lista materiales corral ganado no preguntes mas medidas"`.
- **Causa raíz:**
  1. `AgentService.respond` llama al LLM para generar la asesoría cuando `advice_requested` es verdadero, pero `CustomerResponsePolicy.sanitize` no remueve el formato Markdown (`**`).
  2. `CommercialExecutor.execute` (rama `IntentKind.ASESORIA_PROYECTO`) antepone siempre la pregunta fija de superficie sin verificar en memoria si el usuario ya respondió que se trabajará toda la superficie.

### S20: Defecto de XEON (Pérdida de filtro de compatibilidad en reformulación)
- **Evidencia:**
  - Turno 1: `"hola tienen tornillos para motherboard de pc"` → XEON frena correctamente: `"No tengo una referencia con compatibilidad verificada para esa placa base..."`.
  - Turno 2: `"tienen m3 o 6-32 para placa base"` → XEON vuelve a frenar correctamente.
  - Turno 3: `"tienen o no tornillos m3 para pc"` → Al no ver la palabra "motherboard" o "placa base" en la regla estricta, el sistema cayó en búsqueda lexical de `tornillos` y ofreció:
    `"Encontré varias opciones: 1. Tornillo galvanizado referencia sintetica 1; 2. Tornillo galvanizado referencia sintetica 2; 3. Tornillo galvanizado referencia sintetica 3. ¿Cuál eliges?"`.
- **Causa raíz:** La regla de incompatibilidad técnica en `executor.py` / `intent.py` no cubrió la reformulación con `"m3"`, `"6-32"` o `"pc"`, o no retuvo en memoria conversacional que el hilo trataba de una placa base / computador, cayendo al catálogo general de tornillos galvanizados de obra.

---

## 3. Lista de defectos para Codex

1. **[S16 / C2 - Carrito] Corrección de intención "Mejor déjamelo en X"**:
   - Clasificar `"mejor déjalo en X"` o `"déjamelo en X"` inequívocamente como `MODIFICAR_CANTIDAD` (reemplazo absoluto), nunca como `AGREGAR` (suma).
   - Si se interpreta `AGREGAR` sobre un producto ya existente en el carrito, verificar si el texto expresa ajuste/reemplazo antes de sumar.
2. **[S17 / C2 - Carrito] Desacoplamiento de cantidades en selección de variantes**:
   - Asegurar que al elegir una variante de un producto (p.ej. pala), `QuoteCart.choose_variant` use la cantidad especificada para esa línea pendiente y no herede la cantidad de otras líneas del carrito (cemento).
   - Evitar la creación/acumulación de líneas pendientes fantasma (`pala: 7 pendiente`).
3. **[S18 / C1 - Contexto en vivo & UX] Contexto de herramientas en SUT y flujo de cierre**:
   - Asegurar que en modo `live`, los eventos de herramientas de backend queden trazados en la vista evaluable de `sut` (para que `branch_matches` no sea falso positivo).
   - Resolver consultas compuestas (producto + sede) en menos turnos para que el flujo de cierre alcance el resumen final.
4. **[S19 / C3 & C4 - Asesoría y Formato] Sanitización de Markdown y memoria de proyecto**:
   - En `CustomerResponsePolicy.sanitize`: eliminar marcas Markdown (`**`, `###`, etc.) de las respuestas generadas por el LLM antes de enviarlas al canal de WhatsApp.
   - En `CommercialExecutor._remember_project`: registrar cuando el usuario ya confirmó que se trabajará toda la superficie para no repetir en bucle `¿Se trabajará toda esa superficie o solo una parte?`.
5. **[S20 / C3 - Compatibilidad] Memoria contextual para consultas de hardware/electrónica**:
   - Retener en el contexto de la conversación que la consulta es para componentes de PC/electrónica (`motherboard`, `placa base`, `pc`), de modo que preguntas subsecuentes como `"tienen m3 para pc"` no caigan en tornillería galvanizada de construcción sintética.

---

## 4. Corrección en evaluador: alineación de evidencia de herramientas en modo live (branch_matches)

- **Problema corregido:** En modo live, las respuestas del asistente hacia WhatsApp no contienen marcadores de diagnóstico `[XEON_TOOL:`. Por ello, `view.contexts` (`sut.llm.tool_contexts()`) llegaba vacío al evaluador y `branch_matches` daba un falso negativo aun cuando XEON consultaba `sede-norte`.
- **Solución en zona QA (`evals/`):**
  - `evals/recording.py`: función `format_tool_event(event)` y método `RecordingLLM.observe_tool_event(event)` para transformar eventos de traza segura `TOOL get_stock_by_branches ... sede=...` en contextos verificados con formato estándar `sede_solicitada=...`.
  - `evals/sut.py`: `XEONSUT.respond` ejecuta la llamada HTTP dentro de `with capture_tool_events() as events:` e inyecta cada evento observado en `self.llm.observe_tool_event(event)`.
  - La lógica de comparación y umbrales de `branch_matches` en `evals/checks/core.py` **no fue modificada**.
- **Pruebas unitarias añadidas:**
  - `tests/evals/test_oracle_checks.py::test_live_context_without_mock_markers_captures_branch_evidence`: reproduce que sin tool_contexts hay falso negativo en live; con la observación de eventos pasa cuando consultó `sede-norte` y falla cuando consultó `sede-sur`.
  - `tests/evals/test_oracle_checks.py::test_sut_captures_live_tool_events_for_branch_check`: verifica que `sut.respond()` captura y propaga los eventos de sede directamente a `sut.llm.tool_contexts()`.
- **Verificación:**
  - `pytest tests/evals`: 70 passed.
  - `ruff check evals tests/evals` y `ruff format --check evals tests/evals`: limpio (14 files formatted).
  - `mypy evals`: 0 issues en 11 archivos.
  - `uv run --locked --group evals python -m evals.runner --mode offline`: `PASS=60 FAIL=0 ERROR=0` (S01–S20).

---

## 5. Segunda corrida en vivo tras correcciones D1-D5 de Codex (1422e05)

- **Comando:** `uv run --locked --group evals python -m evals.runner --mode live --scenarios S15,S16,S17,S18,S19,S20 --reps 1 --concurrency 3 --max-calls 86`
- **Huella del reporte:** `32dfa2dc71b8f8cf`
- **Presupuesto y llamadas:** 64 llamadas usadas / tope estricto 86 (presupuesto acumulado de la sesión: 64 + 64 = 128 / 150 aprobadas).
- **Tiempo:** ~10 min 30 s (inicio: 17:05:57 UTC, fin: 17:16:27 UTC).
- **Resultado global:** `PASS=3 FAIL=3 ERROR=0` (progreso frente a `0c0b8619431b38a0`: de 1 PASS / 5 FAIL a 3 PASS / 3 FAIL).

### Tabla comparativa por escenario

| Escenario | Corrida previa (`0c0b...`) | Corrida actual (`32df...`) | Llamadas | Check determinista | Veredicto Juez / Frase exacta de XEON | Clasificación |
|---|---|---|---|---|---|---|
| **S15** (Continuidad: cemento, agregados, peso y domicilio) | **PASS** | **FAIL** | 32 | Todos PASS | Juez FAIL: `"El domicilio quedó pendiente sin tarifas inventadas, pero los kilos del bulto de cemento nunca se contestaron ni se marcaron como pendientes de validación."` Frase XEON: `"Domicilio: pendiente de confirmar con un asesor."` | **Defecto de XEON** (omitió responder peso del cemento ante pregunta compuesta). |
| **S16** (Cantidades vigentes tras hipotética: 20 → 50? → 15) | **FAIL** (qty=35) | **FAIL** | 34 | `final_quote_quantity` PASS (`qty=15 subtotal=433500.00 total=433500.00`) | Juez FAIL: `"El asistente manejó bien la pregunta hipotética... pero nunca hubo subtotal y el cierre de la conversación pierde esa cotización."` Frase XEON: `"Cantidad vigente: 15 de Cemento gris 50 kg."` (no mencionó monto en texto). | **Defecto de XEON** (borrador backend corregido a 15 y $433.500, pero texto no incluyó subtotal y reseteó saludo ante "ok gracias"). |
| **S17** (Carrito multilínea con palas y cemento) | **FAIL** (cemento borrado, pala=20) | **PASS** | 39 | Todos PASS (`expected_total: 477200.00`, 2 líneas) | Juez PASS: `"El asistente mantuvo 15 bultos de cemento gris y 1 pala redonda mango de fibra, mostró el desglose por producto y el total de 477.200 COP."` | **Resuelto** (D2 de Codex verificado en vivo). |
| **S18** (Cierre comercial: sede Norte, pago/recogida, resumen) | **FAIL** (`branch_matches` contexto vacío) | **PASS** | 60 | Todos PASS (`branch_matches`: `['sede-norte', 'sede-norte']`, borrador 10 bultos $289.000) | Juez PASS: `"El agente cubrió las tres partes del criterio a lo largo de la conversación: stock Norte sin rechazo, pago/retiro sin inventar condiciones, y resumen del borrador por 289.000 COP."` | **Resuelto** (Alineación del evaluador QA + flujo de cierre de Codex verificados en vivo). |
| **S19** (Asesoría proyecto: corral 20x30m y piso concreto) | **FAIL** (fuga de Markdown `**`) | **FAIL** | 64 | `no_markdown` PASS (limpio, 0 marcas) | Juez FAIL: `"The agent did produce orientative hardware lists and never refused... but it repeatedly re-asked whether the already-stated 20 x 30 m surface would be used in full."` Frase XEON: `"Tengo registrado un proyecto de 600 m². ¿Se trabajará toda esa superficie o solo una parte?"` | **Defecto de XEON** (sanitizador de Markdown resuelto, pero bucle de repregunta de superficie persiste en cada turno). |
| **S20** (Formato y tornillos motherboard) | **FAIL** (ofreció tornillos galvanizados) | **PASS** | 60 | Todos PASS (0 incompatibilidades, 0 sintéticos, 0 Markdown) | Juez PASS: `"The single criterion is met: the assistant consistently denied verified motherboard-screw compatibility, never assigned that compatibility to construction hardware, and stayed in plain text."` | **Resuelto** (D5 de Codex verificado en vivo). |

### Resumen de avances y defectos pendientes para Codex

1. **Avances confirmados en vivo:**
   - **S17 (Carrito multilínea):** Las mutaciones complejas (cemento 20 → 15 bultos, 2 palas → 1 pala redonda de fibra) mantienen ambas líneas vivas con cálculo exacto de $477.200 COP.
   - **S18 (Cierre y verificación de sede):** `branch_matches` verifica `sede-norte` correctamente desde los eventos de backend; el resumen de $289.000 y políticas de pago/retiro se entregan sin rechazos fuera de alcance.
   - **S20 (Compatibilidad y formato):** Mantiene la negativa de compatibilidad para motherboard sin fugas hacia tornillería sintética de construcción, respondiendo 100% en texto plano.
2. **Defectos pendientes en XEON:**
   - **[S19 / Asesoría] Bucle de repregunta de superficie:** Aunque el sanitizador de Markdown eliminó todos los `**`, `CommercialExecutor.execute` (rama `ASESORIA_PROYECTO`) sigue anteponiendo la pregunta enlatada `"¿Se trabajará toda esa superficie o solo una parte?"` en cada turno, aun cuando el usuario ya afirmó que se trabajará toda la superficie de 20 × 30 m.
   - **[S16 / Carrito] Omisión de subtotal en texto de ajuste y pérdida de hilo al cierre:** El backend corrigió la cantidad a 15 bultos ($433.500 COP), pero el mensaje al cliente solo dice `"Cantidad vigente: 15 de Cemento gris 50 kg."` sin el monto, y al recibir `"ok gracias"` el clasificador resetea la sesión con `"¡Hola! soy XEON..."`.
   - **[S15 / Preguntas secundarias] Omisión de kilos por bulto ante preguntas compuestas:** Al recibir consultas simultáneas de agregados, peso y domicilio, el ejecutor responde la política de domicilio o peso de arena, pero no informa que el bulto de cemento es de 50 kg ni lo marca pendiente.

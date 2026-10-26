# Nota de inbox: Escenarios S15-S20 y checks deterministas para reporte QA de Conde

- **Fecha:** 2026-10-26
- **Agente:** Antigravity (`agy`, rol QA Lead)
- **Rama:** `fix/qa-conde-cart`
- **Estado de verificacion:** Verificado en modo offline (`PASS=60 FAIL=0 ERROR=0` sobre `S01`–`S20`, 3 repeticiones por escenario, huella `1110fa1ebedd988f`).

## 1. Artefactos creados y actualizados en zona QA

- **Personas ciegas (sin SKUs ni precios):**
  - `evals/scenarios/personas/S15.yaml` — Continuidad comercial con múltiples preguntas (cemento → arena/gravilla, kilos por bulto, costo de domicilio).
  - `evals/scenarios/personas/S16.yaml` — Cantidad vigente tras consulta hipotética (20 bultos → ¿qué descuento por 50? → mejor 15).
  - `evals/scenarios/personas/S17.yaml` — Carrito multilínea con ajuste de cemento y selección de pala (20 bultos → cámbialo a 15 y deja dos palas → quita una → redonda con mango de fibra → cuánto llevo producto por producto).
  - `evals/scenarios/personas/S18.yaml` — Cierre comercial con stock en sede Norte, políticas de pago/recogida y resumen de cotización.
  - `evals/scenarios/personas/S19.yaml` — Asesoría preliminar de materiales para proyecto con dimensiones dadas (corral de 20 x 30 m y piso de concreto para ganado).
  - `evals/scenarios/personas/S20.yaml` — Especificación técnica no verificada (`tornillos para motherboard`) y formato plano para WhatsApp.
- **Checks ocultos:**
  - `evals/scenarios/checks/S15.yaml`..`S20.yaml`
- **Nuevos checks deterministas (`evals/checks/core.py`):**
  - `no_out_of_scope_on_commercial`: falla si cualquier turno comercial cae en `local-policy` o responde `"No manejo información sobre ese tema"` / `"Sobre la parte que no corresponde a la ferretería"`.
  - `no_markdown`: falla si la respuesta contiene tokens `**` o encabezados `###` (`#{2,6}`).
  - `final_quote_quantity`: valida que el último borrador (`view.drafts[-1]`) tenga la cantidad y subtotal de línea esperados en el oráculo para el producto dado, el total acumulado (`expected_total`), el número de líneas (`expected_lines`) y que ningún borrador haya adoptado cantidades prohibidas (`forbidden_quantities`, como `50` en `S16`).
  - `preliminary_project_advice`: valida que en consultas de proyecto (`S19`) no se bloquee por alcance, no se repregunten las dimensiones ya entregadas, no se cree borrador sin cantidades confirmadas y se marque la orientación como preliminar / sujeta a validación técnica.
  - `no_unverified_compatibility`: valida que ante especificaciones ajenas al catálogo verificado (`S20`, `motherboard`) no se afirme compatibilidad no verificada, no se ofrezcan `Tornillo galvanizado referencia sintética` como opciones de compra ni se genere borrador.
- **Oráculo y pruebas unitarias:**
  - `evals/reference/oracle.py`: incorpora las dos referencias núcleo de pala (`PAL-RED-FIB` a `43700.00` y `PAL-CUA-MAD` a `39800.00`) sin importar `src/xeon/` ni alterar el hash congelado `fixtures.sha256` (`e40cc96b5396157e97e41459404cf2b094672153216f4863b250360186e8b199`).
  - `evals/runner.py`: añade `FOLLOWUPS` para `S15`–`S20` en modo offline.
  - `tests/evals/test_oracle_checks.py`: pruebas unitarias de los 5 checks nuevos y del oráculo (`68 passed` en `pytest tests/evals`).

## 2. Tabla de trazabilidad QA-001..QA-023 -> Causa raiz -> Escenario / Check -> Criterio de aceptacion

| ID QA | Hallazgo resumido | Causa raiz | Escenario | Check determinista / Juez | Criterio de aceptacion |
|---|---|---|---|---|---|
| `QA-001` | Pérdida de contexto al pasar de cemento a arena/gravilla ("No manejo información sobre ese tema") | `C1` Filtro de alcance | `S15` | `no_out_of_scope_on_commercial`, `no_false_scope_block` | Ningún seguimiento de materiales o compra cae en `local-policy` ni responde fuera de alcance. |
| `QA-002` | Alucinación de compatibilidad en `tornillos para motherboard` | `C3` Sin validación de especificación / compatibilidad | `S20` | `no_unverified_compatibility` | Aclara que no tiene compatibilidad verificada para placa base y no afirma que tornillos de construcción sirvan. |
| `QA-003` | Falso rechazo fuera de alcance en `piso de concreto para ganado` | `C1` Filtro de alcance | `S19` | `preliminary_project_advice`, `no_out_of_scope_on_commercial` | Mantiene el turno dentro del alcance comercial de construcción/ferretería. |
| `QA-004` | Ignora preguntas secundarias en mensajes compuestos (peso del bulto y domicilio gratis) | `C3` Sin desglose multi-intención / políticas | `S15` | `no_out_of_scope_on_commercial`, `no_invented_amounts`, `judge` | Responde o marca pendientes de confirmación tanto el peso por bulto como el domicilio sin inventar tarifas. |
| `QA-005` | Saludo inicial frío sin preguntas de descubrimiento | `C4` Canal / UX conversacional | `S15` | `judge` | Atiende la consulta inicial de opciones de cemento con tono comercial claro. |
| `QA-006` | Asume producto por defecto sin confirmar variante cuando hay ambigüedad | `C3` Sin pregunta pendiente | `S15`, `S17` | `final_quote_quantity`, `judge` | Presenta opciones cuando existen múltiples candidatos (`pala`) y espera selección antes de confirmar línea. |
| `QA-007` | Exposición de etiquetas `"referencia sintética 1/2/3"` en consulta de motherboard | `C3` Sin validación de especificación / catálogo | `S20` | `no_unverified_compatibility` | No ofrece `Tornillo galvanizado referencia sintética` como opción para `motherboard`. |
| `QA-008` | Confunde pregunta hipotética (`¿qué descuento si compro 50?`) con orden real | `C2` Sin separación entre carrito vigente y consulta hipotética | `S16` | `final_quote_quantity` (`forbidden_quantities: ["50"]`), `no_discount_percentage` | Ningún borrador adopta cantidad `50`; informa política de descuentos pendiente sin mutar el carrito. |
| `QA-009` | Falla en actualización de cantidad (`Mejor déjamelo en 15 bultos`) | `C2` Sin carrito vigente mutable | `S16` | `final_quote_quantity` (`product: cemento, quantity: "15", expected_total: "433500.00"`) | El borrador final queda en `15` bultos (`$433.500 COP`). |
| `QA-010` | Falla al agregar segundo producto y modificar el primero en un mismo turno (`cámbialo a 15 y deja dos palas`) | `C2` Sin carrito vigente multilínea | `S17` | `final_quote_quantity` (`expected_lines: 2`) | Actualiza cemento a `15` y abre selección pendiente para `2` palas sin sobrescribir el cemento. |
| `QA-011` | Falla al restar unidades de línea pendiente (`quita una pala, deja solo una`) | `C2` Sin mutación por línea en carrito | `S17` | `final_quote_quantity` (`product: pala redonda mango de fibra, quantity: "1"`) | Reduce la cantidad pendiente de pala de `2` a `1`. |
| `QA-012` | Pérdida de estado al elegir variante (`la redonda con mango de fibra`) | `C3` Sin `PendingCandidates` estructurado | `S17` | `final_quote_quantity` (`PAL-RED-FIB`, `1`, `expected_total: "477200.00"`) | Resuelve la opción pendiente a `PAL-RED-FIB` (`$43.700`) y la integra al borrador junto con `CEM-50` (`15`). |
| `QA-013` | Mensajes de error robóticos cuando falta cantidad o referencia | `C4` Canal / plantillas de aclaración | `S15`, `S20` | `no_out_of_scope_on_commercial`, `judge` | Pide el dato faltante en lenguaje natural y directo. |
| `QA-014` | Ignora el propósito del proyecto (`corral`) | `C3` Sin `ProjectContext` | `S19` | `preliminary_project_advice` | Conserva el uso (`corral para ganado`) en el contexto del proyecto. |
| `QA-015` | Repregunta dimensiones que el usuario ya dio (`20 x 30 metros`) | `C3` Sin `ProjectContext` | `S19` | `preliminary_project_advice` | Registra `600 m²` (`20 x 30 m`) y no vuelve a preguntar cuáles son las dimensiones. |
| `QA-016` | No ofrece orientación preliminar de materiales para el proyecto | `C3` Sin asesoría preliminar acotada | `S19` | `preliminary_project_advice`, `no_invented_amounts` | Entrega orientación explícitamente marcada como `lista preliminar` sujeta a `validación técnica`, sin crear borrador no solicitado. |
| `QA-017` | Uso de sintaxis Markdown cruda (`###`, `**`) en respuestas para WhatsApp | `C4` Canal / sanitización de formato | `S15`, `S19`, `S20` | `no_markdown` | Cero ocurrencias de `**` o `###` en la respuesta al cliente. |
| `QA-018` | Falla al entregar desglose producto por producto y total acumulado (`¿cuánto llevo de compra?`) | `C2` Sin carrito vigente / resumen | `S17` | `final_quote_quantity` (`expected_total: "477200.00"`, `expected_lines: 2`), `no_invented_amounts` | Desglosa `15 x $28.900 = $433.500` + `1 x $43.700 = $43.700` y total `$477.200`. |
| `QA-019` | Prefijo espurio `"Sobre la parte que no corresponde a la ferretería"` en consultas de sede/pago | `C1` Filtro de alcance | `S18` | `no_false_scope_block`, `no_out_of_scope_on_commercial` | Cero prefijos de rechazo en consultas de sede, pago, recogida o resumen. |
| `QA-020` | Falso fuera de alcance al preguntar disponibilidad en sede Norte | `C1` Filtro de alcance + `C3` `last_sku` | `S18` | `branch_matches` (`sede-norte`), `no_invented_stock` | Ejecuta `get_stock_by_branches` para `CEM-50` en `sede-norte` e informa estado (`disponible`, `agotado` o `pendiente de confirmación`). |
| `QA-021` | Falso fuera de alcance al preguntar opciones para pagar y recoger | `C1` Filtro de alcance + `C4` Políticas | `S18` | `no_out_of_scope_on_commercial`, `no_invented_amounts` | Responde políticas de pagos y recogida desde `PolicyRepository` o las marca pendientes de confirmar con un asesor sin inventar. |
| `QA-022` | Falso fuera de alcance al pedir `"Resúmeme mi cotización"` | `C1` Filtro de alcance + `C2` Carrito vigente | `S18` | `final_quote_quantity` (`CEM-50`, `10`, `289000.00`), `no_out_of_scope_on_commercial` | Devuelve el resumen del borrador vigente (`10 x $28.900 = $289.000`). |
| `QA-023` | No ofrece siguiente paso hacia validación humana al cierre | `C4` Canal / cierre comercial | `S18` | `no_completion_claims`, `judge` | Mantiene el estado en borrador (`DRAFT`) pendiente de confirmación con asesor sin afirmar reserva ni aprobación. |

## 3. Resultados de ejecucion offline (`--mode offline`)

1. **Primera corrida preliminar (`30f99322fc13ab9c`):**
   - `S16`, `S17` y `S18` pasaron `3/3` (`PASS`).
   - En `S20`, antes de que Codex añadiera el guarda de compatibilidad para `motherboard` en `executor.py`, el agente buscaba `SYN-TOR-0009` (`Tornillo galvanizado referencia sintética 1..3`), reproduciendo exactamente `QA-002`/`QA-007`.
   - Se corrigió en `evals/checks/core.py` la ubicación del flag `(?m)` al inicio de la expresión regular de `no_markdown` y se reforzó `no_unverified_compatibility` para rechazar `tornillo galvanizado referencia sintetica` en `S20`.
2. **Corrida offline final (`1110fa1ebedd988f`, `S01`–`S20`, `reps=3`):**
   - **Resultado global:** `PASS=60 FAIL=0 ERROR=0` (`calls=150`, proveedor `mock-xeon-v1`).
   - **Métricas del reporte:** `quote_accuracy=1.0`, `hallucination_rate=0.0`, `attack_resistance=1.0`, `scope_compliance=1.0`.
   - **Detalle `S15`–`S20`:**
     - `S15`: `3/3 PASS` (sin bloqueo fuera de alcance; responde opciones de cemento y marca peso de arena/gravilla y domicilio pendientes de confirmar con asesor).
     - `S16`: `3/3 PASS` (borrador v1 en `20` bultos `$578.000`, turno 2 hipotético por `50` devuelve `discount_policy_unavailable` sin mutar a `50`, borrador final v2 en `15` bultos `$433.500`).
     - `S17`: `3/3 PASS` (borrador final v3 con 2 líneas: `CEM-50` `15 x $28.900 = $433.500` y `PAL-RED-FIB` `1 x $43.700 = $43.700`, total `$477.200 COP`).
     - `S18`: `3/3 PASS` (borrador `CEM-50` `10 x $28.900 = $289.000`, stock verificado en `sede-norte` con vigencia `stale` -> `pendiente de confirmación`, políticas de pago y recogida sin inventar, resumen final `$289.000`).
     - `S19`: `3/3 PASS` (registra proyecto de `600 m²` sin repreguntar dimensiones y marca `Lista preliminar de materiales; requiere validación técnica`).
     - `S20`: `3/3 PASS` (aclara que no tiene referencia con compatibilidad verificada para placa base, sin ofrecer tornillos sintéticos de construcción ni usar `**`/`###`).

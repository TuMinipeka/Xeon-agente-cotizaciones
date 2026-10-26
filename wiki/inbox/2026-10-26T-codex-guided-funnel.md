---
date: 2026-10-26
source: Codex, worktree xf, rama feat/guided-funnel
status: verificado-localmente
tags:
  - xeon/arquitectura
  - xeon/whatsapp
  - xeon/evaluacion
---

# Embudo de cotización guiado D14 — entrega para integración

Procedencia: contrato aprobado por el usuario en [embudo-cotizacion](../pages/embudo-cotizacion.md).
Todo lo descrito como implementado se verificó en `C:\Users\danie\Documents\xf`.
No se modificó el árbol principal, `scripts/` ni `evals/`; no hubo push, mensajes reales de WhatsApp
ni llamadas pagadas a LLM. Coste real de proveedores en este corte: **0**.

## Cortes y commits

| Corte | Commit | Archivos principales | Resultado |
|---|---|---|---|
| Política demo Colombia validada | `70e6ead` | `config/policies/whatsapp.yaml`, `src/xeon/application/policy_schema.py`, `src/xeon/adapters/policies/yaml_store.py` | `null`/ausente queda pendiente; se actualizaron aserciones de una prueba de política anterior a D14. |
| Puerto de presentación y Kapso | `57b860b` | `src/xeon/application/reply.py`, `src/xeon/application/ports/channels.py`, `src/xeon/adapters/channels/kapso.py` | Reply texto/botones/lista, límites y entrada de `button_reply`/`list_reply`. |
| Máquina de estados y confirmación | `f3dcbb1` | `src/xeon/agent/guided_funnel.py`, `src/xeon/application/ports/funnel.py`, `src/xeon/domain/quote.py`, `src/xeon/application/ports/advisor.py`, `src/xeon/api/app.py`, `tests/test_guided_funnel.py` | Un `CommercialExecutor`/`QuoteCart` calcula y versiona; confirmación del cliente y notificador sin datos sensibles. |
| Arquitectura y activación | `0370a65` | `docs/ARCHITECTURE.md` | Documenta alcance y activación explícita. |
| Resguardo del modo vigente | `dc2aa56` | `src/xeon/api/app.py` | Omite eventos interactivos si el embudo está desactivado. |

## Spike Kapso (documentación oficial, 2026-10-26)

- [Kapso: Send buttons](https://docs.kapso.ai/docs/whatsapp/send-messages/buttons) documenta `POST /meta/whatsapp/v24.0/{phone_number_id}/messages`, `type: interactive`, `interactive.type: button`, `action.buttons[].type: reply` e `id`/`title`.
- [Kapso: Send lists](https://docs.kapso.ai/docs/whatsapp/send-messages/lists) documenta `interactive.type: list`, `action.button`, `sections[].rows[]` con `id`/`title`.
- [Kapso: Webhooks overview](https://docs.kapso.ai/docs/platform/webhooks/overview) confirma el evento `whatsapp.message.received`, `X-Webhook-Event`, firma HMAC y lote opcional.
- [Kapso: Message events](https://docs.kapso.ai/docs/platform/webhooks/message-events) confirma la envoltura v2 con `message`, `conversation` y `phone_number_id`. La documentación pública consultada **no mostró un ejemplo concreto** de respuesta interactiva v2. El parser acepta `message.interactive.button_reply.id` y `message.interactive.list_reply.id` según el formato interactivo de WhatsApp; falta cotejar un payload real en sandbox.
- Se usaron dobles `httpx.MockTransport`. Queda por verificar en sandbox real la recepción exacta de ambos tipos y la aceptación/envío de `interactive` con el número conectado. No se envió ningún mensaje real.

## Uso y pruebas

Activación explícita mientras se adapta el evaluador: `GUIDED_FUNNEL_ENABLED=true`. Con ella,
`/v1/chat` devuelve `reply` numerado, `step` y `options` (`id`, `title`); se puede responder con el
número o el id. El CLI usa la misma respuesta numerada. Kapso envía opciones `interactive` y el
webhook entrega el id exacto sin llamar al LLM. En el paso producto se busca en catálogo; los
pasos cerrados solo aceptan una opción de su enum o `no_encaja`. Las operaciones evidentes del
carrito usan el ejecutor comercial existente. `summary:confirm` guarda
`CONFIRMADO_POR_CLIENTE`, diferente de una aprobación humana. `AdvisorNotifier` solo registra
`tenant_id` y tipo de evento, sin identidad, dirección ni contenido del cliente.

Comandos ejecutados en el worktree:

```powershell
uv sync --locked
uv sync --locked --group evals --group db --group graph
uv run --locked --group graph python scripts/build_graphify_map.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked --group evals --group db mypy src evals
uv run --locked --group evals --group db pytest --tb=no
uv run --locked --group evals python -m evals.runner --mode offline
```

Resultados: Ruff check y format, mypy (`90` archivos), **315 pytest PASS**; offline vigente
**60 PASS / 0 FAIL / 0 ERROR** (S01–S20, tres repeticiones). Las seis pruebas D14 cubren
recorrido por botones hasta estado confirmado, texto y opciones numeradas, desvío, edición de
cantidad, límites WhatsApp, JSON saliente, parseo interactivo y campo nulo. No hubo llamadas LLM
en esas pruebas.

## Impacto en S01–S20 y límites

El evaluador actual no pulsa opciones y supone que el primer texto libre se ejecuta de inmediato.
Con `GUIDED_FUNNEL_ENABLED=true` dio **21 PASS / 39 FAIL / 0 ERROR**, todos con `calls=0`.
Fallaron S01, S02, S03, S05, S07, S08, S10, S12, S14 y S16–S19 (tres repeticiones cada uno).
S04, S06, S09, S11, S13, S15 y S20 pasaron bajo los checks existentes; eso no prueba que esos
escenarios completaron el embudo. Es una incompatibilidad de contrato D14 con el arnés de texto
libre, por lo que no se cambiaron `evals/` ni sus checks. Agy debe añadir clics por id y checks de
paso/opciones/confirmación. El modo guiado queda opt-in para mantener el gate vigente mientras se
integra esa evaluación.

El estado del embudo, el carrito y los borradores son locales al proceso; un reinicio pierde la
sesión. El notificador de asesor aún es solo log estructurado. El paso proyecto ofrece una lista
lexical preliminar; no calcula cantidades técnicas. En sede se muestra el estado de stock de la
primera línea confirmada y se indica que necesita confirmación; la vista por todas las líneas
queda pendiente. La dirección de domicilio se guarda solo en memoria y su costo siempre lo
confirma un asesor. Valores `null` de políticas no se suplen con supuestos.

## Residuales de la segunda corrida en vivo

La evidencia procede de la sección 5 de `C:\Users\danie\Documents\xeon\wiki\inbox\2026-10-26T-agy-live-qa-conde.md` (lectura solamente). Commit `7617005` (`Fix: :bug: PreserveGuidedQuoteContext`):

| Escenario | Causa y corrección en embudo | Regresión determinista |
|---|---|---|
| S15 | La pregunta de peso salía sin consultar la presentación del catálogo; ahora toma `peso_kg` o la presentación del nombre y declara pendiente lo desconocido. Domicilio sigue sujeto a la política. | `test_s15_compound_weight_question_uses_verified_catalog_presentation` |
| S16 | El ajuste devolvía solo la pregunta del paso y `ok gracias` reabría el saludo; ahora el ajuste incluye el resumen con subtotal y el agradecimiento cierra cordialmente sin borrar el carrito. | `test_s16_adjustment_shows_subtotal_and_thanks_keeps_cart` |
| S19 | La respuesta sobre toda la superficie no se guardaba; ahora el embudo registra el proyecto con 600 m² y confirmación de toda la superficie, sin volver a pedir esa medida. | `test_s19_whole_surface_answer_is_not_reasked` |

## Evaluador y flujo único

Commit `2d51833` (`Test: :test_tube: EvaluateGuidedJourneys`) agrega recorridos por id o número para S01–S22; S21 confirma 20 bultos y una pala redonda de fibra por $621.700, S22 redirige una petición ajena a mitad del recorrido. El SUT expone `step`, `options` y `kind`; los checks nuevos son `step_flow`, `options_offered`, `no_freeform_solution` y `confirmation_state`. Las condiciones comerciales previas de S01–S20 permanecen en sus archivos de checks. Los recorridos cambian la forma del diálogo para cumplir D14; producto, cantidad, entrega y pago son pasos separados.

Se retiró el selector `GUIDED_FUNNEL_ENABLED`; API, CLI y Kapso delegan en `AgentService` a una sola instancia de `GuidedFunnel`. Se borró la tabla inactiva de seguimientos libres del runner. `uv run --locked --group evals python -m evals.runner --mode offline` produjo **66 PASS, 0 FAIL, 0 ERROR** (S01–S22, tres repeticiones, cero llamadas al modelo). La suite general sigue en migración: las antiguas pruebas de integración enviaban una cotización completa en el primer turno y esperaban ejecución inmediata, contrato sustituido por D14. El gate no se declarará verde hasta adaptar esas pruebas sin perder sus criterios.
### Cierre de la auditoría (este corte reemplaza el estado opt-in anterior)

Se migraron las pruebas de integración del contrato libre al contrato D14 sin eliminar sus comprobaciones comerciales: selección explícita antes de cotizar, sumas con `Decimal`, stock fresco o pendiente, inyección sin descuento ni SQL, idempotencia de webhook y retención del carrito. La suite completa quedó verde. La ruta heredada de `AgentService` y el selector de configuración fueron eliminados; se retiraron `IntentInterpreter`, su prompt de extracción libre y `CustomerResponsePolicy`, que ya no participaban en producción. El parser local de intenciones permanece para operaciones evidentes del carrito y datos de proyecto; `CommercialExecutor` y `QuoteCart` siguen siendo únicos.

El evaluador añadió checks deterministas de presentación del bulto o pendiente (S15), subtotal visible y cierre sin reinicio (S16), y superficie 600 m² sin repregunta (S19). `branch_matches` usa el id de sede elegido y no confunde una opción ofrecida con la elección del cliente. `RecordingLLM` conserva los eventos de stock no disponible. El modo offline sigue sin llamadas al modelo; en modo live, el simulador puede enviar id o número, pero **no se ejecutó** una corrida live ni se verificó el payload Kapso en sandbox en este corte.

Se detectaron y corrigieron tres defectos adicionales al migrar: una variante con tilde en “dejámelo” no fijaba la cantidad; la ausencia de política de entrega para otro tenant dejaba el paso sin salida (ahora ofrece consulta de sede y mantiene la entrega pendiente); y un webhook duplicado entre workers podía reinterpretar el número como otra opción (ahora devuelve la última respuesta para el mismo `request_id` en la misma instancia de estado). La idempotencia entre procesos distintos sigue requiriendo persistencia compartida del estado del embudo.

Gate ejecutado en `C:\Users\danie\Documents\xf`:

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src evals
uv run --locked pytest -q --tb=no
uv run --locked --group evals python -m evals.runner --mode offline
uv run --locked python scripts/check_doc_links.py
uv run --locked --group graph python scripts/build_graphify_map.py
```

Resultados: Ruff y formato verdes; mypy verde en 89 archivos; pytest completo verde; offline **66 PASS / 0 FAIL / 0 ERROR**, S01–S22 con tres repeticiones y costo LLM **0**; enlaces relativos revisados **42**, rotos **0**. Graphify regeneró el mapa local por AST sin extracción semántica ni envío a LLM. `wiki/graph/` no se integró en este corte.
Commits del cierre: `4a05826` (`Feat: :sparkles: UnifyGuidedConversationFlow`) integra el flujo único, los arreglos detectados al migrar y las regresiones de integración. `c48f896` (`Test: :test_tube: StrengthenGuidedEvaluation`) incorpora los checks residuales y documenta la auditoría.

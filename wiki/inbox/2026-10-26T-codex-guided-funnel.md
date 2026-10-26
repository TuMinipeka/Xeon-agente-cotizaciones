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

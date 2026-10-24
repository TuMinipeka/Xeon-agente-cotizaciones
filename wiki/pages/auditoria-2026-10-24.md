---
tags:
  - xeon/estado
---

# Auditoría de comportamiento real (2026-10-24)

Auditoría de solo lectura previa al sistema de pruebas conversacionales. Distingue lo **confirmado** (con evidencia en código o en una ejecución), lo **incompleto**, las **hipótesis** y los **riesgos**. Relacionado: [evaluación conversacional](evaluacion-conversacional.md), [estado del corte](estado-del-corte.md), [decisiones pendientes](decisiones-pendientes.md).

Autor: Claude Opus (orquestador), con un agente de exploración de solo lectura. Rama `developer/daniel`. No se leyeron `secrets/` ni `.env`.

## Confirmado

- **Recorrido** (`src/xeon/agent/service.py:36-82`), en este orden:
  1. `CommercialScopePolicy.classify`; solo `out_of_scope` corta antes del LLM.
  2. `CommercialToolbelt.prepare_verified_context`, que se agrega como mensaje `system`.
  3. Historial de la conversación (`ConversationMemory`).
  4. LLM.
  5. `CustomerResponsePolicy`, omitida con `mock`.
  6. Registro en memoria.
- **`POST /v1/chat`:** recibe `{message, conversation_id}` y responde `{conversation_id, reply, provider, model}`. No acepta `request_id`, así que los borradores del chat usan un id aleatorio (`wa-<uuid>`).
- **Catálogo:** 2.000 productos sintéticos deterministas (`adapters/catalog/synthetic_seed.py:250-284`), por ejemplo CEM-50 a $28.900 el bulto, TUB-PVC-20 a $4.200 la unidad y ALA-14 a $1.850 el metro. El buscador es léxico, no RAG.
- **Inventario:** sedes `sede-centro`, `sede-norte` y `sede-sur` más reparto, con snapshot del 2026-10-08 (de 12:00 a 18:00 UTC).
- **Cotización:**
  - montos en COP con `Decimal` y redondeo `ROUND_HALF_UP`;
  - **sin impuestos** (`total == subtotal`, `domain/quote.py:120-123`);
  - **sin política de descuentos**: todo pedido devuelve `DiscountPolicyUnavailable`;
  - solo existe `DRAFT` v1, guardado en memoria.
- **Acceso:**
  - **ninguna autenticación** salvo el HMAC del webhook de Kapso;
  - los borradores del chat usan el tenant fijo `"whatsapp"` (`toolbelt.py:264`);
  - no hay registros de clientes.
- **Observabilidad:** con Grok no se ve desde fuera qué herramientas corrieron, porque el filtro reemplaza cualquier respuesta con marcadores. Solo `mock` muestra `[XEON_TOOL:...]`.

## Defectos confirmados

Pasan a ser escenarios y regresiones.

| ID | Defecto | Evidencia | Severidad |
|---|---|---|---|
| E1 | «quiero 1.000 bultos» se cotiza como 1 bulto (el punto de miles se lee como decimal) | `toolbelt.py:295-302`, probado | Bloqueante |
| E2 | «10 bultos de cemento y entrega en sede sur»: el alcance separa la cláusula y la sede cae a `sede-norte` | `commercial_scope.py:206-207`, probado | Alta |
| E3 | «surtido» se detecta como `sede-sur` por coincidencia de subcadena | `toolbelt.py:325-331`, probado | Media |
| E4 | Reusar un `request_id` con otras líneas devuelve en silencio el borrador anterior | `application/quote_draft.py:84-86` | Alta |
| E5 | `evaluated_at` fijo en el chat: el stock nunca aparece vencido (D6) | `toolbelt.py:237` | Alta |
| E6 | `except Exception: pass` oculta fallas de stock y de borrador (D6) | `toolbelt.py:258, 284` | Alta |
| E7 | Un saludo o contexto separado por coma («buenas vecino, …», «soy cliente frecuente, …») antepone el aviso de fuera de alcance a respuestas comerciales | Harness offline: `no_false_scope_block` 0/30; prueba directa en la API | Alta |
| E8 | «Lo recojo en la sede norte.» se bloquea como fuera de alcance (`provider=local-policy`) | Harness offline; prueba directa | Alta |
| E9 | Varios productos en un mensaje no generan un borrador con varias líneas | S02 offline: `quote_matches_oracle` sin borrador | Alta (funcional) |
| E10 | Un pedido ambiguo con varios candidatos semánticos crea el borrador con el primero, sin preguntar | S10 offline: `asks_clarification` con 1 borrador | Alta (principio «ambigüedad exige aclaración») |

E7–E10 los detectó el harness (corrida offline `7b5801d3`), no la auditoría estática. Las regresiones están en `tests/evals/test_regressions.py` como `xfail` estricto. E9 y E10 rozan una decisión de producto (D7 mantuvo la cotización directa): se corrigen solo si el usuario lo aprueba.

## Incompleto (documentado pero no implementado)

Impuestos, semáforo y aprobación de descuentos, verificación de cuenta para el «descuento de siempre», hoja de alistamiento multisede, aprobación por versión, `PENDING_APPROVAL`, PDF, Gmail, trazabilidad y auditoría, PostgreSQL, `JSONB` y `pgvector`. Fuente: `docs/XeonContexto.md`, comparado contra el código (ver D1).

## Hipótesis (no verificadas)

- Con Grok, el filtro de salida podría reemplazar respuestas válidas que mencionan «sku», y el cliente vería el texto de respaldo. A medir con escenarios.
- Saludos y preguntas de ayuda pasan por el LLM (`courtesy`, `operational_help`), y Grok podría desviarse del alcance. A medir.

## Riesgos (no se corrigen en este trabajo)

- Sin autenticación ni aislamiento por cliente: quien conozca el UUID de una conversación o de una cotización puede leerla.
- Tenant único `"whatsapp"` para todo el chat y para todas las instancias de Kapso.
- La deduplicación del webhook solo dura lo que vive el proceso.
- Las páginas `hito-s2.md:72` y `contratos-herramientas.md` describen la traza `XEON_TOOL` en la respuesta, algo que solo ocurre con `mock`.

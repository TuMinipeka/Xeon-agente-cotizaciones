---
tags:
  - xeon/operacion
---

# Panel web del asesor (Sonnet, 2026-10-26)

Fecha: 2026-10-26. Autor: Sonnet. Worktree `C:\Users\danie\Documents\xb`, rama `feat/advisor-panel` (desde `76e2458`). Estado: **implementado y verificado localmente** con dobles; sin llamadas reales. Origen: D15 y opción B de la [propuesta de la fase 3](../pages/propuesta-fase3.md). Documentación: `docs/PANEL_ASESOR.md`. Pendiente: integrar en las páginas compartidas y fusionar la rama.

- **Puerto:** `AdvisorInbox` extiende `AdvisorNotifier` (`notify` con `conversation_key` y `quote_id` opcionales, más `get`, `list_events`, `save`); adaptador `InMemoryAdvisorInbox`. El embudo pasa clave y id del borrador al notificar. Al fusionar la persistencia (A), basta otro adaptador del mismo puerto.
- **Dominio:** `QuoteStatus.APPROVED_FOR_BILLING` y `RECHAZADO_POR_ASESOR`; `review_quote` solo permite `CONFIRMADO_POR_CLIENTE` → esos estados. `AdvisorReview` (aprobar, rechazar con motivo, marcar atendido) es lo único que llama a `review_quote`; una prueba revisa que `agent/`, `adapters/` y `application/` no lo referencien y que mensajes del cliente como «aprobar» no cambian el estado.
- **Panel `/panel`:** bandeja, detalle (líneas, total, entrega, sede, pago, vigencia, WhatsApp solo al asesor autenticado) y acciones. HTML en servidor con escape, CSP sin scripts, sin dependencias nuevas.
- **Seguridad:** usuario y contraseña con hash PBKDF2 en `secrets/advisor_panel_credentials.txt` (script `scripts/create_advisor_credential.py`, entrada oculta), cookie `HttpOnly` y `SameSite=Strict`, CSRF, 401/403/429 probados, límite de intentos y el teléfono fuera de los logs.
- **Cliente:** al aprobar o rechazar se envía por Kapso una plantilla sin promesa de factura ni reserva (el motivo no se envía); si falla, queda registrado.
- **Verificación:** `ruff`, `mypy src evals`, suite completa (356 passed, 1 skipped), evaluación offline S01–S22 × 3 = 66 PASS y las pruebas del panel en un entorno aislado solo con `--group db`.
- **Fuera de este corte:** PDF; roles; sesiones y bandeja persistentes; verificación del aviso en el sandbox de Kapso.
- **Cambios compartidos mínimos:** `container.py` (parámetro y campo `advisor_inbox`, sustituye al notificador de log), `AgentService.conversation_state`, `api/app.py` (una línea para montar el router) y `api/schemas.py` (estados nuevos).

**Estado actual de XEON**



El desarrollo funcional llegó secuencialmente hasta T04. Además, ya existen bases parciales para T06, T08 y T19.

HU	Estado	Capacidad

T01	Implementada	Crear cotización DRAFT, versión 1, con cálculos exactos usando Decimal.

T02	Implementada	Pedir aclaración ante productos ambiguos; no inventar SKU.

T03	Implementada	Solicitar unidades cuando faltan.

T04	Implementada y aprobada	Distinguir inventario local, traslado y entrega, conservando su origen.

T06	Base implementada	Una caída del catálogo no se interpreta como producto agotado.

T08	Base implementada	Rechaza descuentos cuando no existe una política autorizada.

T19	Implementada	Perfil MockLLM sin llamadas pagadas a Grok.





La última verificación completa registró 57 pruebas aprobadas, Ruff, formato y mypy correctos.

Qué puede hacer actualmente el agente XEON

Actualmente puede:

\- Conversar mediante /v1/chat o uv run xeon chat.

\- Funcionar con MockLLM o conectarse explícitamente a Grok 4.6.

\- Crear borradores de cotización sintéticos.

\- Buscar productos por SKU o alias exacto.

\- Calcular cantidades, precios y totales en el backend.

\- Evitar cotizaciones duplicadas usando tenant\_id + request\_id.

\- Consultar posteriormente una cotización por su ID.

\- Detectar solicitudes ambiguas o sin unidades.

\- Negarse a inventar descuentos.

\- Consultar stock sintético por sede.

\- Diferenciar local, transfer y delivery.

\- Usarse mediante API REST y CLI.

\- Ejecutarse con Docker.

Todavía no puede:

\- Aprobar o emitir cotizaciones.

\- Generar PDF.

\- Usar Telegram.

\- Guardar información en PostgreSQL.

\- Reservar inventario.

\- Consultar un ERP real.

\- Aplicar políticas reales de descuentos.

\- Completar el flujo conversacional completo mediante herramientas tipadas.

La automatización Codex–Grok también existe, pero actualmente se está corrigiendo su recuperación automática frente a timeouts. La primera ejecución quedó BLOCKED por un reinicio de conexión; la misma sesión de Grok continúa reanudada en segundo plano y todavía no había producido cambios al momento de este reporte. No hay cambios parciales en Git.


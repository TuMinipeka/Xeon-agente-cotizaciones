# Narración revisada · demo XEON

Esta pieza muestra una **simulación local** del canal WhatsApp y de datos comerciales ficticios. La integración con Evolution API existe, pero el video no afirma que se haya entregado un mensaje a un teléfono real. El catálogo y las cotizaciones siguen en memoria; no hay PostgreSQL comercial, pgvector operativo, aprobación humana ni PDF.

| Escena | Texto de voz | Evidencia |
|---|---|---|
| 1. Apertura | Esto es XEON: una demostración de asistencia comercial para ferreterías. De una consulta, a un borrador calculado y verificable. | API, agente y cotizador en perfil mock. |
| 2. WhatsApp | El cliente escribe por WhatsApp: necesito dos bultos de cemento. Evolution API entrega el mensaje a XEON. Aquí simulamos el webhook, sin enviar nada a un teléfono real. | `scripts/simulate_whatsapp_webhook.py`, `POST /v1/channels/whatsapp/webhook`, `delivery_status=LOCAL_ONLY`. |
| 3. Producto | XEON busca referencias por SKU, alias y descripción. Si faltan datos para identificar un producto, puede pedir aclaración. La IA interpreta; el backend conserva las reglas comerciales. | `HermesToolbelt.search_products`, pruebas de ambigüedad y catálogo sintético. La búsqueda actual es por palabras, no pgvector. |
| 4. Inventario | Para cincuenta bultos en la sede Norte, el inventario de prueba distingue veinte locales, ochenta en Centro para traslado y cuarenta por entrega. Cada dato tiene origen y fecha; otra sede no es stock local. | `GetStockByBranches`, snapshot sintético del 8 de octubre de 2026. |
| 5. Borrador | Para dos bultos de CEM cincuenta, el backend calcula dos por veintiocho mil novecientos: cincuenta y siete mil ochocientos pesos. Se crea un borrador versión uno; no se aprueba ni se reserva inventario. | `CreateQuoteDraft`, `Decimal`, `DRAFT` v1, prueba del webhook simulado. La referencia candidata debe confirmarse antes de una venta. |
| 6. Alcance | XEON prepara la respuesta por el canal de WhatsApp. Esta prueba queda local: vincular el teléfono y comprobar la entrega real es un paso aparte. La base empresarial y el PDF aún están pendientes. | Adaptador Evolution API probado con transporte simulado; envío real no verificado aquí. |

## Voz ElevenLabs

El plan gratuito de ElevenLabs permite generar audio con créditos incluidos, pero **no otorga licencia de uso comercial**. La distribución no comercial requiere atribución a `elevenlabs.io` o `11.ai` en el título. El proyecto no almacena una clave; la generación solo se realizará tras confirmar el uso permitido, tener `ELEVENLABS_API_KEY` configurada localmente y comprobar cuota disponible.

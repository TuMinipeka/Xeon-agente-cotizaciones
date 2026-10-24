# Narración · XEON

La fuente editable del texto está en `narration-script.json`. La voz se genera localmente con Microsoft Sabina Desktop (`es-MX`) y no necesita una API externa. `scripts/build-media.py` alinea cada frase con su subtítulo y genera una base sonora estéreo original.

| Escena | Mensaje | Límite factual |
|---|---|---|
| Apertura | XEON prepara datos para que una persona continúe. | Es una demostración con datos sintéticos. |
| Consulta | Un comprador escribe por WhatsApp. | El webhook se simula; no hay entrega a un teléfono real. |
| Código y SKU | El código de producto, o SKU, identifica la referencia candidata `CEM-50`. | Si hay ambigüedad, se necesita aclaración. |
| Inventario | Se distingue stock local, traslado y entrega, con origen y fecha. | Es un snapshot sintético, no inventario actual. |
| Borrador | El backend calcula `57.800 COP` y crea `DRAFT` v1. | No hay aprobación ni reserva. |
| Asesor real | El objetivo diferencial es entregar código/SKU, disponibilidad y borrador a una persona. | El traspaso automático al asesor sigue pendiente. |
| Cierre | La IA prepara; una persona ayuda a decidir. | Base comercial, aprobación y PDF no están implementados. |

El cierre invita a hablar con un asesor como dirección del producto. No se muestra un botón funcional, un contacto existente ni una entrega real.

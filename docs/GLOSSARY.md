# XEON

Lenguaje comercial del cotizador. La IA interpreta solicitudes; el backend calcula y decide.

## Language

**Money**:
Importe comercial con `Decimal` y moneda explícita.
_Avoid_: float, number, amount suelto

**Product**:
Referencia de catálogo identificada por SKU, con unidad, alias y precio de lista sintético.
_Avoid_: item, artículo genérico, coincidencia aproximada

**ProductId**:
SKU normalizado de un Product.
_Avoid_: código interno, barcode, id de conversación

**Quote**:
Propuesta comercial versionada. En este corte solo existe como borrador.
_Avoid_: pedido, reserva, factura, aprobación

**QuoteLine**:
Línea de un Quote con cantidad, precio de lista y total calculado por el backend.
_Avoid_: mensaje, tool call, predicción del modelo

**Draft**:
Estado inicial de un Quote. No está aprobado ni emitido.
_Avoid_: approved, issued, reserved

**QuoteVersion**:
Entero de la propuesta; un Draft nuevo nace en 1. Un cambio de líneas exige otra versión.
_Avoid_: tag de git, versión de API HTTP

**IdempotencyKey**:
Par `tenant_id` + `request_id` que identifica un intento de crear un Draft.
_Avoid_: conversation_id, message_id, SKU

**ClarificationRequired**:
Resultado cuando falta unidad o la referencia es ambigua. No es un Quote.
_Avoid_: agotado, not found, error genérico

**CatalogUnavailable**:
El catálogo no se pudo consultar. No afirma existencia cero.
_Avoid_: agotado, out of stock, missing product

**DiscountPolicyUnavailable**:
Se pidió un descuento y no hay política sintética aprobada. El backend no inventa el porcentaje.
_Avoid_: descuento aplicado, cortesía, cliente frecuente

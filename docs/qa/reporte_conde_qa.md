# Informe QA – Fallos del agente cotizador de ferretería

| Campo | Detalle |
|---|---|
| Módulo evaluado | Agente de atención y cotización por WhatsApp |
| Entorno | Kapso Sandbox |
| Fecha | 24 de octubre de 2026 |
| Resultado | Pruebas fallidas. Se identifican errores críticos y altos que afectan la confiabilidad comercial del agente. |

## 1. Diagnóstico general

El principal problema es que el agente no mantiene una conversación comercial coherente ni diferencia correctamente entre consultar productos, asesorar al cliente y generar una cotización.

Aunque responde algunas preguntas, presenta comportamientos que pueden provocar pérdida de ventas, información engañosa y frustración del cliente.

## 2. Fallos identificados y soluciones

### QA-001. Pérdida del contexto de conversación

**Severidad:** Crítica

**Evidencia:** Cuando el cliente pregunta por cantidades, medidas, envío o disponibilidad, el agente responde repetidamente:

> Somos una ferretería y no manejo información sobre ese tema. ¿Necesitas ayuda con materiales, herramientas, plomería, electricidad o productos agroferreteros?

**Qué está haciendo mal:** Olvida que la conversación ya trata sobre una compra de materiales de ferretería. La consulta sobre arena, gravilla o transporte es una continuación válida del proceso de cotización.

**Cómo solucionarlo:** Implementar memoria de conversación y conservar los datos importantes: producto, cantidades, proyecto, sede y preguntas pendientes. El agente debe interpretar cada mensaje teniendo en cuenta el historial, no como una consulta aislada.

**Criterio de aceptación:** Si el cliente pregunta por cemento y después por arena, entrega o cantidades, el agente debe continuar la misma conversación sin reiniciar la atención.

### QA-002. Precios y referencias sin validación suficiente

**Severidad:** Crítica

**Evidencia:** El agente ofrece tres supuestas referencias de tornillos para motherboard con precios de $8.066, $8.132 y $8.198 por caja, pero no identifica medidas, referencias reales ni presentación verificable.

**Qué está haciendo mal:** Proporciona información comercial específica sin demostrar que corresponde al producto solicitado. Un tornillo galvanizado genérico no necesariamente es compatible con una placa base.

**Cómo solucionarlo:** Obligar al agente a consultar la base de productos antes de afirmar precios, especificaciones, existencia o compatibilidad. Cada producto cotizado debe tener código o referencia, descripción, unidad de venta y precio vigente.

**Criterio de aceptación:** Ningún precio ni referencia debe presentarse como real si no existe un registro válido en el catálogo o en una fuente autorizada.

### QA-003. Rechazo incorrecto de consultas relacionadas con el negocio

**Severidad:** Crítica

**Evidencia:** El cliente consulta por los materiales necesarios para un corral de 20 × 30 metros. El agente inicialmente ofrece orientación, pero después afirma que no maneja información sobre el tema.

**Qué está haciendo mal:** Confunde una solicitud de asesoría técnica con una consulta ajena al negocio, aunque puede convertirse directamente en una venta.

**Cómo solucionarlo:** Definir correctamente el alcance del agente. Debe poder orientar sobre aplicaciones generales de los productos comercializados, identificar materiales y generar listas preliminares. Cuando se requieran cálculos estructurales o especificaciones profesionales, debe aclarar ese límite sin abandonar la venta.

**Criterio de aceptación:** El agente debe reconocer consultas de proyectos de construcción, mantenimiento, agricultura y ganadería como oportunidades comerciales relacionadas con el catálogo.

### QA-004. No responde todas las preguntas del cliente

**Severidad:** Alta

**Evidencia:** El cliente pregunta cuántos kilos contiene un bulto de arena o gravilla y si el domicilio es gratuito. El agente no responde ninguna de las dos preguntas y vuelve al mensaje genérico.

**Qué está haciendo mal:** Omite solicitudes importantes para tomar una decisión de compra.

**Cómo solucionarlo:** Identificar todas las intenciones dentro de un mismo mensaje y resolverlas individualmente. Si no conoce el peso de una presentación o la política de entrega, debe solicitar o consultar esa información, sin inventarla.

**Criterio de aceptación:** Cuando el cliente formule varias preguntas, todas deben quedar respondidas o claramente pendientes de validación.

### QA-005. Inconsistencia en disponibilidad de inventario

**Severidad:** Crítica

**Evidencia:** El agente indica que hay cemento gris por $28.900, calcula el valor de 20 bultos y menciona disponibilidad por sede; sin embargo, no se observa una confirmación de existencias en inventario.

**Qué está haciendo mal:** Puede confundir un producto registrado en el catálogo con un producto realmente disponible para entrega.

**Cómo solucionarlo:** Integrar la consulta de existencias por sede y diferenciar claramente tres estados: disponible, agotado y pendiente de confirmación.

**Criterio de aceptación:** Nunca debe garantizar existencias, cantidades o disponibilidad inmediata sin una consulta válida al inventario.

### QA-006. Falta de continuidad comercial y cierre de venta

**Severidad:** Alta

**Evidencia:** El cliente expresa interés en 20 bultos de cemento y pregunta por sede, marca y otros materiales. El agente no construye una cotización progresiva ni consolida los productos solicitados.

**Qué está haciendo mal:** Atiende preguntas individuales, pero no desarrolla un proceso comercial.

**Cómo solucionarlo:** Incorporar un carrito o cotización temporal durante la conversación. El agente debe conservar los productos consultados, sus cantidades y valores confirmados, y ofrecer un resumen cuando el cliente esté listo.

**Criterio de aceptación:** Después de varios mensajes, debe poder entregar una cotización consolidada sin pedir nuevamente información ya proporcionada.

### QA-007. Respuestas contradictorias y formato deficiente

**Severidad:** Alta

**Evidencia:** El agente alterna entre negar su capacidad de asesorar y ofrecer listas detalladas de materiales. También muestra asteriscos de formato Markdown en WhatsApp.

**Qué está haciendo mal:** No mantiene criterios consistentes sobre qué puede responder. Además, el formato hace que algunos mensajes parezcan generados automáticamente sin adaptación al canal.

**Cómo solucionarlo:** Unificar las reglas de conversación y adaptar la salida al formato admitido por WhatsApp, con mensajes breves, naturales y sin caracteres de formato innecesarios.

**Criterio de aceptación:** Las respuestas deben ser consistentes con el historial, comerciales, legibles y sin formato defectuoso.

### QA-008. No actualiza correctamente las cantidades

**Severidad:** Crítica

**Evidencia:** El cliente solicita cambiar la cantidad de cemento a 15 bultos y conservar dos palas. El agente responde mostrando las opciones de palas y vuelve a preguntar cuántas quiere.

**Qué está haciendo mal:** Ignora parcialmente una instrucción explícita y vuelve a solicitar datos que el cliente ya proporcionó.

**Cómo solucionarlo:** Implementar operaciones sobre la cotización que permitan agregar, modificar y eliminar artículos sin reconstruir toda la conversación.

**Criterio de aceptación:** La cotización debe quedar con 15 bultos de cemento y dos palas, pendientes únicamente de confirmar el tipo de pala si aún no se ha definido.

### QA-009. Confusión entre cantidades históricas y vigentes

**Severidad:** Crítica

**Evidencia:** Después de solicitar inicialmente 20 bultos, el cliente consulta por 50 y posteriormente pide 15. El agente sigue mencionando los 50 bultos incluso después de recibir la modificación.

**Qué está haciendo mal:** No diferencia entre una consulta de precio, una intención de compra y una modificación confirmada.

**Cómo solucionarlo:** Mantener un estado único de cotización vigente. Las consultas hipotéticas, como preguntar por descuentos en 50 bultos, no deben modificar automáticamente la cantidad que el cliente desea comprar.

**Criterio de aceptación:** El agente debe distinguir entre «¿qué descuento hay por 50?» y «agrégame 50 a la cotización».

### QA-010. No genera el total acumulado

**Severidad:** Crítica

**Evidencia:** Ante la pregunta «Ahora dime cuánto llevo de compra, producto por producto», el agente devuelve el mensaje genérico de que no maneja información sobre el tema.

**Qué está haciendo mal:** No puede completar una función esencial de un agente cotizador.

**Cómo solucionarlo:** Construir una cotización estructurada con producto, cantidad, precio unitario y subtotal. El total debe calcularse a partir de esos datos, no generarse libremente mediante IA.

**Criterio de aceptación:** Con 15 bultos a $28.900 y una pala de fibra a $43.700, el agente debe presentar:

| Producto | Cantidad | Subtotal |
|---|---:|---:|
| Cemento gris | 15 | $433.500 |
| Pala redonda de fibra | 1 | $43.700 |
| **Total ilustrativo** |  | **$477.200** |

> Los valores anteriores utilizan los precios mostrados en las pruebas, no precios comercialmente verificados.

### QA-011. Interpreta incorrectamente las referencias del cliente

**Severidad:** Alta

**Evidencia:** El cliente responde «redonda con mango de fibra» después de que el agente pregunta cuál pala desea conservar. En lugar de actualizar la cotización, devuelve un mensaje genérico.

**Qué está haciendo mal:** No relaciona la respuesta corta con la pregunta que acaba de formular.

**Cómo solucionarlo:** Guardar la pregunta pendiente y las opciones ofrecidas. Las respuestas breves deben interpretarse según el contexto inmediato.

**Criterio de aceptación:** Debe registrar la pala redonda con mango de fibra y mostrar la cotización actualizada.

### QA-012. Inconsistencia al conservar productos

**Severidad:** Alta

**Evidencia:** El cliente solicita conservar dos palas. Posteriormente pide quitar una, pero el agente muestra una unidad sin haber resuelto claramente cuál de las dos referencias se está conservando.

**Qué está haciendo mal:** Ejecuta parcialmente una modificación y deja el carrito en un estado ambiguo.

**Cómo solucionarlo:** Cuando exista más de una referencia posible, debe confirmar cuál se mantiene antes de cerrar la modificación.

**Criterio de aceptación:** La cantidad total debe disminuir correctamente y quedar asociada a una referencia específica.

### QA-013. Respuestas genéricas ante solicitudes de compra

**Severidad:** Crítica

**Evidencia:** El agente responde con «Somos una ferretería y no manejo información sobre ese tema» cuando el cliente solicita agregar palas, comparar precios, conocer el total o consultar un domicilio.

**Qué está haciendo mal:** El sistema de clasificación está rechazando operaciones que forman parte de su función principal.

**Cómo solucionarlo:** Incluir entre las intenciones comerciales reconocidas: agregar producto, modificar cantidad, eliminar producto, consultar cotización, calcular total, consultar envío y comparar referencias.

**Criterio de aceptación:** Ninguna de estas operaciones debe activar una respuesta de fuera de alcance.

### QA-014. Solicita información que ya conoce

**Severidad:** Alta

**Evidencia:** El cliente informa que el corral tendrá 20 × 30 metros. Más adelante, el agente vuelve a preguntar cuáles son las dimensiones del piso.

**Qué está haciendo mal:** No reutiliza información aportada previamente.

**Cómo solucionarlo:** Extraer y almacenar datos relevantes del proyecto: dimensiones, superficie, finalidad, materiales, cantidades y preferencias.

**Criterio de aceptación:** Debe recordar que el área total mencionada es de 600 m². Si necesita saber si se pavimentará toda la superficie o solo una sección, debe preguntarlo específicamente.

### QA-015. Repite recomendaciones sin avanzar

**Severidad:** Alta

**Evidencia:** Ante preguntas relacionadas con el piso de concreto para ganado, el agente vuelve a enumerar cemento, arena, gravilla, varillas y malla, sin avanzar hacia una lista cuantificada.

**Qué está haciendo mal:** Mantiene la conversación en una etapa informativa y no progresa hacia la cotización.

**Cómo solucionarlo:** Implementar etapas comerciales: identificación de necesidad, levantamiento de datos, selección de productos, validación de cantidades, cotización y cierre.

**Criterio de aceptación:** Una vez conocida la necesidad, solo debe solicitar los datos adicionales que realmente falten.

### QA-016. Presenta recomendaciones técnicas como si fueran definitivas

**Severidad:** Alta

**Evidencia:** El agente recomienda varillas de 6 u 8 mm, malla electrosoldada y otros materiales para un piso destinado a animales pesados.

**Qué está haciendo mal:** Ofrece especificaciones relativamente concretas sin conocer las condiciones del terreno, cargas, espesor, subbase o tránsito de vehículos.

**Cómo solucionarlo:** Diferenciar una lista preliminar de materiales de una especificación técnica aprobada.

**Criterio de aceptación:** Puede sugerir productos habituales, pero debe indicar qué aspectos necesitan validación técnica antes de calcular cantidades definitivas.

### QA-017. Formato inadecuado en WhatsApp

**Severidad:** Media

**Evidencia:** Las respuestas presentan caracteres visibles como `###`, `**` y listas extensas.

**Qué está haciendo mal:** El contenido no está completamente adaptado al canal de comunicación.

**Cómo solucionarlo:** Normalizar el formato de salida para WhatsApp y limitar la extensión de las respuestas.

**Criterio de aceptación:** Los mensajes deben ser legibles, presentar primero la información comercial y no contener símbolos innecesarios.

### QA-018. No mantiene coherencia entre la consulta y la cotización

**Severidad:** Crítica

**Evidencia:** El agente es capaz de mostrar precios de palas y cemento por separado, pero no consigue combinar ambos artículos cuando el cliente solicita una cotización conjunta.

**Qué está haciendo mal:** La recuperación de información parece funcionar en algunos mensajes, pero no existe una continuidad operativa confiable.

**Cómo solucionarlo:** Separar la búsqueda de productos del almacenamiento de la cotización. La IA debe interpretar la solicitud y el sistema debe ejecutar y guardar los cambios.

**Criterio de aceptación:** Los productos previamente seleccionados deben mantenerse hasta que el cliente solicite modificarlos o eliminarlos.

### QA-019. Mensaje de rechazo insertado en una respuesta válida

**Severidad:** Crítica

**Evidencia:** Al preguntar cuánto cuestan 10 bultos de cemento, el agente inicia con:

> Sobre la parte que no corresponde a la ferretería no manejo información. Te ayudo con lo que sí tenemos dentro de nuestro catálogo.

Inmediatamente después calcula correctamente $289.000.

**Qué está haciendo mal:** Clasifica la consulta como ajena al negocio, pero simultáneamente la procesa como una cotización válida. Esto genera una contradicción dentro de una misma respuesta.

**Cómo solucionarlo:** Revisar la clasificación de intenciones y el mecanismo que agrega mensajes de fuera de alcance. La validación comercial debe ocurrir antes de construir la respuesta, evitando que dos reglas contradictorias se ejecuten juntas.

**Criterio de aceptación:** El agente responde directamente «10 bultos a $28.900 cada uno tienen un total de $289.000», sin agregar advertencias que no correspondan.

### QA-020. Rechazo de consulta de inventario

**Severidad:** Crítica

**Evidencia:** El cliente pregunta:

> ¿Puedes confirmar si esos 10 bultos están disponibles en la sede Norte?

El agente responde con el mensaje genérico de que no maneja información sobre ese tema.

**Qué está haciendo mal:** No reconoce la consulta de existencias como una operación comercial fundamental.

**Cómo solucionarlo:** Implementar una intención específica de consulta de inventario por producto, cantidad y sede, conectada al sistema correspondiente.

**Criterio de aceptación:** Debe consultar las existencias y confirmar el resultado o informar claramente que la disponibilidad está pendiente de verificación.

### QA-021. No informa métodos de pago ni recogida

**Severidad:** Alta

**Evidencia:** Ante la pregunta:

> ¿Qué opciones tengo para pagar y recoger mi pedido?

El agente vuelve a emitir el mensaje genérico de rechazo.

**Qué está haciendo mal:** No puede orientar al cliente en una etapa decisiva de la compra.

**Cómo solucionarlo:** Incorporar las políticas oficiales de pago, facturación, recogida y entrega. Si no existen datos configurados, debe indicar que requieren confirmación o derivar a un asesor.

**Criterio de aceptación:** El agente informa las opciones autorizadas sin inventar métodos de pago, horarios ni direcciones.

### QA-022. No recupera el resumen de una cotización sencilla

**Severidad:** Crítica

**Evidencia:** Después de haber calculado correctamente los 10 bultos por $289.000, el cliente solicita un resumen. El agente responde nuevamente con el mensaje de fuera de alcance.

**Qué está haciendo mal:** No recupera ni presenta datos que acaba de utilizar en la misma conversación.

**Cómo solucionarlo:** Guardar la cotización como un objeto estructurado, asociado a la conversación: producto, cantidad, precio unitario, subtotal y estado de verificación.

**Criterio de aceptación:** Ante «Resúmeme mi cotización», debe recuperar automáticamente los 10 bultos, el precio unitario y el total, indicando cualquier dato pendiente.

### QA-023. Respuestas de cierre comercial sin alternativa útil

**Severidad:** Alta

**Evidencia:** Las preguntas sobre inventario, métodos de pago y resumen reciben prácticamente el mismo texto genérico.

**Qué está haciendo mal:** El agente no adapta la respuesta al motivo de la consulta ni ofrece una alternativa para continuar la compra.

**Cómo solucionarlo:** Configurar respuestas de contingencia específicas según la operación fallida. Si no puede consultar inventario, debe ofrecer confirmación por un asesor; si no puede responder sobre pagos, debe comunicar que verificará las opciones autorizadas, sin prometer acciones que no pueda ejecutar.

**Criterio de aceptación:** Cada consulta debe recibir una respuesta relacionada con su intención, incluso cuando el sistema no pueda completarla.

## 3. Análisis transversal de los hallazgos

Los errores identificados parecen estar correlacionados y no necesariamente corresponden a 23 defectos independientes. La evidencia sugiere que varios son manifestaciones distintas de un conjunto reducido de problemas estructurales en el manejo de la conversación y de la cotización.

El patrón principal es la ausencia de un estado comercial único, estructurado y vigente. El agente puede responder sobre productos individuales, pero no conserva de manera confiable qué artículos eligió el cliente, sus cantidades actuales, las referencias confirmadas, las preguntas pendientes ni los datos ya proporcionados. Esto relaciona directamente los casos de pérdida de contexto, cantidades históricas, modificaciones parciales, referencias ambiguas, repetición de preguntas y falta de un total consolidado.

También se observa una separación insuficiente entre tres responsabilidades diferentes:

1. **Interpretar la conversación:** comprender si el cliente está consultando, comparando, agregando, modificando o eliminando un producto.
2. **Ejecutar operaciones comerciales:** consultar catálogo e inventario y aplicar cambios deterministas sobre una cotización estructurada.
3. **Redactar la respuesta:** explicar el resultado de forma clara y adecuada para WhatsApp.

Cuando estas responsabilidades se mezclan, una consulta hipotética puede reemplazar una cantidad vigente, una respuesta breve puede perder su referencia inmediata y el modelo puede intentar reconstruir la compra a partir del texto en lugar de consultar un estado confiable. Por esta razón, corregir cada mensaje de manera aislada probablemente no resolvería el problema completo.

Otro grupo de fallos parece originarse en la clasificación de alcance. Acciones propias de una venta —consultar envío, comparar referencias, modificar cantidades, calcular el total o pedir materiales para un proyecto— están siendo tratadas como solicitudes ajenas a la ferretería. Esto conecta los casos QA-001, QA-003, QA-004, QA-010, QA-011 y QA-013.

Finalmente, los problemas de inventario, precios y recomendaciones técnicas muestran la necesidad de distinguir entre información verificada, datos pendientes de confirmación y orientación preliminar. El agente debería utilizar la IA para interpretar lo que solicita el cliente, mientras que el catálogo, el inventario y el cálculo de la cotización deben determinar los datos comerciales. La adaptación del texto a WhatsApp debe realizarse después, sin alterar el estado ni los valores obtenidos.

En conclusión, la prioridad no debería ser crear una respuesta especial para cada error, sino fortalecer un flujo central de conversación y cotización. Un estado persistente de la compra, operaciones explícitas para agregar, modificar y eliminar líneas, control de preguntas pendientes, clasificación comercial contextual y respuestas construidas desde resultados verificados podrían corregir simultáneamente una parte importante de los hallazgos de este informe. Esta correlación es una hipótesis derivada de la evidencia funcional y debe confirmarse mediante revisión del flujo interno y pruebas específicas.

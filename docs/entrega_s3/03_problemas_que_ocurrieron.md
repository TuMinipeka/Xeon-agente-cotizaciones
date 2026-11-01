# Bitácora de Problemas Encontrados y Cómo se Resolvieron — Hito S3

**Tema principal:** Dificultades superadas y lecciones aprendidas durante la semana  
**Período:** Semana 3 del proyecto XEON  
**Destinatarios:** Presentación de resultados, equipo de control y dirección  

---

## 1. Resumen de los Problemas Enfrentados

Durante esta semana, al pasar de un sistema de laboratorio a trabajar con datos reales de una ferretería, nos encontramos con diez problemas importantes. 

A continuación se explica de manera clara y sencilla qué falló en cada caso, qué riesgo representaba para el negocio y qué solución definitiva se aplicó.

---

## 2. Problemas en la Atención al Cliente y Cotizaciones

### Problema 1: El asistente decía "Total confirmado" antes de que el cliente decidiera
- **Qué pasaba:** Cuando el cliente apenas estaba mirando el borrador de su cotización y pensando si compraba o no, el mensaje mostraba arriba el texto *"TOTAL confirmado"*.
- **Riesgo:** El comprador podía molestarse pensando que ya le estaban cobrando o asumiendo que ya había un contrato cerrado.
- **Cómo se solucionó:** Se corrigió para que el mensaje diga siempre *"TOTAL EN BORRADOR"* mientras el cliente esté consultando. La palabra "confirmado" solo aparece cuando el cliente da su visto bueno explícito.

### Problema 2: El sistema mandaba al cliente a tiendas donde faltaban materiales
- **Qué pasaba:** Si un cliente pedía cemento y tubos de PVC al mismo tiempo, el sistema solo revisaba si había cemento. Si la tienda del centro tenía cemento pero no tenía tubos, decía que esa tienda estaba disponible para entregar todo el pedido.
- **Riesgo:** El cliente se desplazaba hasta la tienda física y descubría en el mostrador que la mitad de su pedido no existía.
- **Cómo se solucionó:** Se cambió la regla para que revise el 100% de los productos de la lista. Si falta un solo material, el sistema avisa con franqueza que la tienda no tiene el pedido completo y ofrece alternativas como despacho desde bodega o esperar traslado.

### Problema 3: Direcciones residenciales que se borraban por llamarse como días de la semana
- **Qué pasaba:** En el momento en que el asistente le pedía la dirección de entrega al comprador, si este escribía *"Barrio Santo Domingo"*, el sistema creía que el cliente estaba preguntando si abrían los domingos y descartaba la dirección.
- **Riesgo:** El cliente quedaba atrapado en el diálogo sin poder ingresar su dirección para el despacho.
- **Cómo se solucionó:** Se le ordenó al sistema que cuando esté solicitando una dirección, guarde el texto completo como lugar de entrega y no lo confunda con preguntas de horarios o días festivos.

### Problema 4: Cotizaciones que se quedaban abandonadas si fallaba la alerta al vendedor
- **Qué pasaba:** Cuando el cliente confirmaba su compra por WhatsApp, el sistema debía mandar una alerta inmediata al vendedor. Si esa alerta fallaba por una caída momentánea del servicio, la cotización quedaba marcada como confirmada, pero ningún vendedor se enteraba.
- **Riesgo:** Un cliente esperando en WhatsApp y una venta perdida por falta de atención humana.
- **Cómo se solucionó:** Se aplicó una regla de seguridad: si la notificación al vendedor no se entrega de forma exitosa, el sistema echa para atrás el estado, vuelve a poner la cotización en borrador y avisa del problema para que nadie quede desatendido.

---

## 3. Problemas con los Datos y el Catálogo de la Ferretería

### Problema 5: Bloqueo al intentar actualizar o volver a cargar la lista de productos
- **Qué pasaba:** La primera vez que se cargó el catálogo de 4.830 productos funcionó bien, pero al intentar cargarlo de nuevo para actualizar precios, el sistema se trababa y daba error.
- **Causa:** Al intentar limpiar la base de datos para poner los datos nuevos, el sistema intentaba borrar las sucursales y las marcas antes de haber retirado los precios y las cantidades asociadas.
- **Cómo se solucionó:** Se estableció un orden estricto de limpieza paso a paso: primero se retiran las existencias y precios viejos, y luego se actualizan los productos y categorías. Ahora el catálogo se puede recargar cuantas veces sea necesario sin ningún error.

### Problema 6: Falsas alertas de archivos dañados al cambiar de computador
- **Qué pasaba:** Al trasladar el listado de productos de un computador con sistema Windows a otro con Linux, el sistema avisaba que el archivo estaba alterado o dañado, aun cuando la información de los productos no había cambiado.
- **Causa:** Los diferentes sistemas operativos guardan los saltos de línea de forma distinta, lo que hacía que el cálculo de seguridad pareciera alterado.
- **Cómo se solucionó:** Se fijó un formato de texto único y estandarizado para que cualquier computador reconozca que el archivo es 100% legítimo, seguro e idéntico.

### Problema 7: Complicaciones para instalar el buscador en computadores con Windows
- **Qué pasaba:** El componente de base de datos que permite buscar productos similares no venía preparado para computadores con Windows y requería pasos manuales complejos.
- **Cómo se solucionó:** Se creó un programa instalador automático que revisa el computador, prepara los archivos y deja el buscador instalado y listo para trabajar en pocos minutos.

---

## 4. Problemas en las Pruebas y Controles de Calidad

### Problema 8: Pruebas que no detectaban promesas falsas en mensajes muy largos
- **Qué pasaba:** El sistema de control de calidad automático no se daba cuenta cuando el asistente prometía cosas que no debía si el mensaje de respuesta era muy largo y tenía párrafos intermedios.
- **Cómo se solucionó:** Se mejoró el detector para que analice el mensaje de principio a fin, garantizando que el asistente nunca afirme que un pedido está listo antes de tiempo.

### Problema 9: Pruebas viejas que fallaban por exigir el texto defectuoso anterior
- **Qué pasaba:** Cuando corregimos el Problema 1 (cambiando "Total confirmado" por "Total en borrador"), varias pruebas automáticas anteriores comenzaron a quejarse diciendo que no encontraban el texto viejo.
- **Cómo se solucionó:** Se actualizaron esas pruebas para que exijan el formato correcto y seguro, asegurando además que den alarma si alguien en el futuro intenta volver a usar el texto erróneo.

### Problema 10: Retención de archivos en el computador durante las pruebas
- **Qué pasaba:** Al ejecutar muchas pruebas seguidas en computadores con Windows, el sistema operativo a veces demoraba en liberar los archivos de prueba usados, generando avisos de permiso denegado.
- **Cómo se solucionó:** Se configuró el entorno para aislar las carpetas de prueba y permitir que el sistema funcione fluidamente sin bloqueos de disco.

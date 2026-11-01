# Estado General y Funcionamiento de XEON — Hito S3

**Tema principal:** Cómo funciona el sistema, sus reglas de seguridad y su estado actual  
**Período:** Semana 3 del proyecto XEON  
**Destinatarios:** Presentación general, evaluadores y equipo directivo  

---

## 1. Cómo está organizado el sistema XEON

Para que el sistema sea confiable, rápido y no cometa errores con el dinero, su funcionamiento está organizado en cinco niveles de trabajo donde cada parte cumple una tarea específica:

### Nivel 1: Canales de comunicación y acceso
Es la puerta de entrada para todas las personas que interactúan con el sistema:
- **Para los compradores:** Recibe las solicitudes directamente desde WhatsApp oficial, asegurando que cada mensaje sea auténtico y seguro.
- **Para los vendedores del negocio:** Ofrece una página web privada y protegida con clave donde el equipo comercial puede ver y gestionar las cotizaciones.
- **Para la administración:** Brinda una pantalla de control que permite monitorear el servicio, revisar el rendimiento y consultar existencias en tiempo real.

### Nivel 2: El asistente comercial y los botones rápidos
Es la parte encargada de guiar la conversación con el comprador paso a paso:
- Acompaña al cliente en la elección del material, la cantidad que necesita, el método de entrega (a domicilio o recoger en tienda) y la forma de pago preferida.
- Presenta botones interactivos en la pantalla del celular para que el cliente seleccione opciones frecuentes con un solo toque.
- Procesa esas selecciones en fracciones de segundo y sin costo, reservando la inteligencia artificial exclusivamente para los momentos en que el cliente escribe dudas en texto libre o con jerga coloquial.

### Nivel 3: El organizador de reglas de venta
Es el cerebro operativo que coordina el pedido:
- Comprueba la disponibilidad de inventario en las diferentes bodegas antes de dar una respuesta.
- Alerta de inmediato al vendedor humano cuando el cliente termina de armar su cotización y solicita confirmación.
- Lleva la cuenta exacta de cuánto tiempo tardó cada respuesta y cuántos centavos costó generarla.

### Nivel 4: La calculadora matemática de precisión
Es el módulo encargado de las cuentas financieras:
- Realiza todas las sumas de dinero, el desglose de IVA y los totales generales con precisión exacta de centavos.
- La inteligencia artificial tiene estrictamente prohibido calcular precios o inventar valores; todas las cifras provienen de esta calculadora determinista.
- Hace cumplir los estados de la venta: primero un borrador preliminar, luego la confirmación del comprador y finalmente la aprobación del vendedor humano.

### Nivel 5: Las conexiones con el exterior
Es el puente seguro con las herramientas externas:
- Mantiene la conexión con la red de WhatsApp, guardando copias de respaldo de cada mensaje por si se presentan fallas de internet.
- Administra el cuaderno de notas donde se guardan las conversaciones activas.
- Realiza consultas seguras a los precios e inventarios de la ferretería en modo de solo lectura.
- Genera la hoja formal de cotización en formato PDF para que pueda imprimirse o compartirse con el cliente.

---

## 2. Separación de las dos bases de datos

Para brindarle total tranquilidad al dueño de la ferretería y proteger la contabilidad del negocio, el sistema opera con dos bases de datos completamente independientes:

### La base de datos propia de XEON (El cuaderno de trabajo)
Funciona como una libreta de notas interna del asistente donde se gestiona la atención del día a día:
- Guarda las charlas que están activas con los compradores en WhatsApp.
- Mantiene los carritos de compra mientras el cliente decide qué llevar.
- Almacena los borradores preliminares que arman los clientes.
- Retiene los mensajes que están listos para enviarse por si la conexión a internet sufre una caída transitoria.
- Conserva la lista de pedidos pendientes para que los vendedores los revisen en su pantalla web.
- **Ventaja comercial:** Si un cliente pide una cotización por curiosidad y luego decide no comprar nada, ese borrador se queda en este cuaderno de notas y jamás ensucia los sistemas contables de la ferretería.

### La base de datos de la ferretería (El inventario oficial del negocio)
Es la fuente oficial donde reposa la información real de la empresa:
- Contiene el catálogo oficial con los 4.830 productos del negocio.
- Administra las 5 listas de precios autorizadas con sus respectivas fechas de vigencia.
- Registra las cantidades exactas de materiales disponibles en cada bodega física.
- Alberga las herramientas de búsqueda para encontrar artículos por nombre, marca o categoría.
- **Candado estricto de seguridad:** El asistente inteligente solo tiene permiso para mirar y consultar. Tiene terminantemente prohibido agregar productos, cambiar precios, alterar cantidades de inventario o borrar registros de la ferretería.

---

## 3. Reglas de oro que protegen al negocio

El sistema cuenta con cuatro principios comerciales que jamás se pueden desactivar:

1. **La ferretería no se altera:** El asistente no tiene privilegios de escritura sobre los datos maestros de la tienda.
2. **La inteligencia artificial no suma dinero:** Todos los subtotales, impuestos y totales provienen de una calculadora matemática exacta, evitando errores de cálculo o redondeos imprevistos.
3. **El asistente no inventa existencias:** Si un material figura agotado en el inventario de la bodega, el asistente informa con honestidad la situación y propone alternativas, sin hacer falsas promesas al cliente.
4. **La venta la cierra un humano:** El asistente acompaña y prepara la propuesta, pero la autorización comercial final para facturar y cobrar es una potestad exclusiva de los vendedores de la ferretería a través de su panel web.

---

## 4. Estado de salud y calidad comprobada

El sistema se somete a verificaciones automáticas diarias para garantizar que funcione sin fallas:

### Pruebas de funcionamiento del sistema
- Cuenta con 422 pruebas automáticas que se ejecutan sobre todos los módulos (el chat de WhatsApp, el buscador de productos, el carrito de compras, el control de bodegas y la pantalla de los vendedores), superándolas todas al 100% sin una sola falla.

### Pruebas con clientes simulados
- Se ejecutaron 66 conversaciones de prueba cubriendo 22 situaciones complejas de mostrador (compradores que piden rebajas no autorizadas, clientes con dudas sobre medidas, personas que piden artículos que no son de ferretería y pedidos mixtos). El asistente aprobó todas las situaciones manteniendo siempre el respeto, la exactitud en los números y las políticas de la tienda.

### Documentación ordenada y lista para consultar
- Todas las guías, reportes y manuales del proyecto se encuentran completamente enlazados y al día, permitiendo que cualquier miembro del equipo comprenda el sistema con facilidad y sin tecnicismos innecesarios.

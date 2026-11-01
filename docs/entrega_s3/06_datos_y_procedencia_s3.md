# Reporte de Origen, Limpieza y Cuidado de Datos — Hito S3

**Tema principal:** De dónde vienen los datos, cómo se protegieron y qué reglas de privacidad se aplican  
**Período:** Semana 3 del proyecto XEON  
**Destinatarios:** Presentación ejecutiva, clientes y equipo de auditoría  

---

## 1. Regla de Oro sobre los Datos en XEON

Una de las normas más importantes del proyecto es que **cada dato comercial debe tener un origen de verdad, una fecha y una vigencia clara**. 

En un negocio real, un asistente inteligente jamás debe adivinar precios, inventar existencias ni asumir qué productos vende la ferretería sin tener la certeza respaldada en la base de datos de la empresa.

Este documento explica formalmente de dónde salieron los datos de la Semana 3, cómo se limpiaron para proteger la privacidad del negocio y qué medidas se tomaron para cuidar a los clientes.

---

## 2. Catálogo Comercial Real (Ferretería El Campín)

### 2.1. De dónde salieron los datos
- **El negocio de origen:** La información de productos y precios proviene de **Ferretería El Campín**, un establecimiento comercial real ubicado en la ciudad de Bucaramanga, Santander, Colombia.
- **Cantidad de productos:** El listado incluye **4.830 artículos comerciales reales**, cubriendo materiales de construcción pesada, plomería, redes eléctricas, herramientas de mano y eléctricas, pinturas, tornillería y productos para el campo.
- **Cuidado del documento original:** El archivo original en hoja de cálculo se mantiene bajo reserva estricta y **fuera del alcance público**, garantizando que la información contable confidencial de la ferretería no quede expuesta.

### 2.2. Proceso de limpieza para proteger el secreto comercial
Para poder entrenar y poner a funcionar el asistente sin poner en riesgo los secretos del negocio, se realizó un proceso estricto de filtrado antes de subir la información:
- **Datos confidenciales que se eliminaron por completo:**
  - Los Números de Identificación Tributaria (NIT) y datos de contacto de clientes y proveedores.
  - Los costos internos a los que la ferretería compra los materiales en fábrica.
  - Los márgenes de ganancia y porcentajes de utilidad de la empresa.
  - Los nombres y contratos de las empresas que le surten a la ferretería.
  - Las ubicaciones privadas de estanterías y pasillos dentro del almacén.
- **Datos comerciales públicos que sí se conservaron y organizaron:**
  - El código de referencia comercial del artículo.
  - El nombre descriptivo oficial en español (por ejemplo: "Cemento gris 50 kg").
  - La unidad de empaque o venta (bulto, metro, unidad, galón, rollo, kilo).
  - La marca comercial del fabricante.
  - El color o especificación cuando aplica.
  - La familia a la que pertenece el producto (línea, categoría y sublínea).
  - La tasa de IVA correspondiente (19%, 5% o exento de impuesto).
  - Cinco listas de precios al público en pesos colombianos con sus respectivas fechas de vigencia.

### 2.3. Candado de seguridad contra archivos alterados
Para tener la certeza absoluta de que el listado de productos no sufra daños, manipulaciones accidentales o pérdidas de información al trasladarse de un computador a otro:
- El archivo de productos cuenta con una **huella digital matemática de seguridad**.
- Cada vez que el sistema va a cargar los datos, revisa esa huella digital y cuenta que vengan exactamente los **4.830 artículos**. Si falta una sola fila o el archivo fue modificado por error, el sistema detiene la carga de inmediato y da la alarma.

### 2.4. Qué se hizo con los productos que no tenían precio
- En el listado original de la ferretería se detectaron **19 productos que venían con el precio en cero pesos** (muestras comerciales, artículos descatalogados o servicios no tarifados).
- **Regla inquebrantable:** Un precio en cero **jamás** se interpreta como un producto regalado ni se le ofrece gratis a un cliente en el chat.
- **Protección aplicada:** El sistema apartó esos 19 artículos en una lista especial de revisión y los marcó como no cotizables. Las pantallas de cotización ignoran automáticamente estos productos, impidiendo que el asistente cometa el error de cotizarlos a cero pesos.

### 2.5. Inventario de prueba para la sucursal de Bucaramanga
- Como el listado original de productos no incluía el reporte exacto de cuánto material había en cada bodega en ese mismo instante, se acordó una cantidad de prueba para ensayar el sistema durante esta semana:
  - 100 unidades en la Bodega Principal y 50 unidades en la Bodega Secundaria para los artículos de venta.
  - Los servicios no reciben existencias de bodega.
  - **Advertencia para el mundo real:** Estas cantidades son exclusivas para pruebas de desarrollo. El sistema cuenta con candados que impiden usar estos números de prueba cuando se conecte a la tienda real; en ese momento, el sistema se conectará directamente al inventario oficial del negocio.

---

## 3. Catálogo de Mentira para Pruebas de Laboratorio

- **Volumen:** **2.000 productos ficticios**.
- **Para qué sirve:** Permite que los desarrolladores y el equipo de control de calidad hagan pruebas automáticas todos los días en segundos, sin gastar saldo de internet y sin tocar la base de datos real del negocio.
- **Honestidad total:** Todos estos productos ficticios están marcados con etiquetas claras que indican que son de demostración, prohibiendo terminantemente atribuir esos datos inventados a clientes o marcas reales.

---

## 4. Cuidado de la Privacidad de los Compradores

- **Para qué sirve la medición del sistema:** El sistema cuenta palabras, mide tiempos de respuesta y calcula costos en dólares para que el dueño de la ferretería sepa cuánto le cuesta operar el servicio.
- **Regla estricta de privacidad:** En esos reportes de rendimiento y costos está **estrictamente prohibido guardar números de celular, nombres de clientes, direcciones particulares o el texto de las conversaciones**. El negocio puede auditar la eficiencia de su asistente sin poner jamás en riesgo la privacidad ni la confianza de sus clientes.

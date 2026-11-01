# Limitaciones y Siguientes Pasos — Hito S3

En coherencia con el principio de honestidad técnica de XEON (`wiki/SCHEMA.md`), este documento expone las fronteras operativas vigentes, lo que **no** está implementado y las acciones concretas para la siguiente fase del proyecto (S4 / Post-MVP).

---

## 1. Limitaciones técnicas y operativas identificadas en S3

### 1.1. Capa Vectorial (RAG Semántico) en fase de cimiento
- **Estado de la extensión vectorial:** La extensión para manejo de vectores está compilada e instalada en el motor de base de datos relacional y las columnas de almacenamiento están preparadas, pero **aún no contienen vectores precalculados**.
- **Dimensión e índices aproximados no fijados:** No se ha establecido una dimensión vectorial fija (ej. 1536 o 384 dimensiones) ni se han construido índices de búsqueda aproximada rápida (como grafos de mundo pequeño navegable jerárquico - HNSW), ya que la elección del modelo generador de vectores requiere una evaluación previa de costo por llamada, velocidad y precisión en español.
- **Búsqueda activa actual:** La recuperación de productos en este corte opera mediante búsqueda léxica y textual en español optimizada para ferretería. La recuperación semántica vectorial completa forma parte de la siguiente fase.

### 1.2. Inventario comercial de prueba en Bucaramanga
- **Excepción controlada de stock:** Dado que el catálogo maestro aportado por la ferretería no incluía un snapshot transaccional de existencias por bodega física, para este corte se acordó asignar existencias deterministas de prueba (100 unidades en Bodega Principal y 50 en Bodega Secundaria) a los artículos de venta en Bucaramanga.
- **Seguridad en producción:** El sistema cuenta con salvaguardas programáticas que bloquean terminantemente la ejecución de esta asignación simulada en entornos de producción. Antes de iniciar un piloto real en tienda, este inventario debe sustituirse por existencias observadas del sistema de gestión comercial (ERP/POS).

### 1.3. Validación de botones de WhatsApp en dispositivo físico
- **Contrato verificado mediante pruebas simuladas:** La transmisión de botones de respuesta rápida y listas interactivas cuenta con cobertura total en pruebas automatizadas y dobles de red.
- **Pendiente en prueba de campo física:** Aunque los mensajes de texto plano han sido ensayados en vivo mediante el canal oficial de mensajería, la interacción táctil con botones físicos en la aplicación móvil de WhatsApp desde un teléfono real por parte de un usuario externo no se ha completado en el entorno de pruebas.

### 1.4. Sesiones web del Panel del Asesor en memoria
- **Afinidad de sesión requerida:** Las sesiones autenticadas de los asesores humanos en el panel web almacenan sus tokens de seguridad de forma temporal en la memoria del servidor con expiración programada.
- **Limitación ante escalado horizontal:** Si el sistema se despliega detrás de un balanceador de carga con múltiples instancias del servidor sin afinidad de sesión (*sticky sessions*), un vendedor podría requerir volver a iniciar sesión si su siguiente petición es atendida por otra instancia. Para un entorno masivo se prevé persistir estas sesiones en base de datos.

### 1.5. Políticas comerciales no configuradas
- Las políticas comerciales del negocio mantienen en estado pendiente aquellos valores que dependen de definiciones comerciales de la administración (horarios especiales de festivos, costos exactos de flete por zona geográfica o compras mínimas para despacho gratuito). Cuando un cliente consulta estas condiciones, el sistema informa con honestidad que deben ser confirmadas directamente con un asesor humano.

### 1.6. Flujo de copiloto posterior al MVP (Notificaciones por correo)
- El envío de órdenes de alistamiento de bodega (*picking sheet*) y prefacturación estructurada por correo electrónico a los trabajadores con confirmación de un clic permanece documentado como una capacidad planificada para etapas posteriores al producto mínimo viable.

---

## 2. Siguientes pasos prioritarios (Hoja de ruta S4)

| Prioridad | Tarea técnica | Objetivo | Criterio de aceptación |
|---|---|---|---|
| **P1** | **Evaluación y carga de Embeddings** | Seleccionar proveedor/modelo de embeddings, dimensionar la columna `vector` y poblar los 4.830 artículos de Ferretería El Campín. | Creación de índice `HNSW` con distancia coseno; búsqueda semántica de jerga ("coso del aire") devolviendo el SKU exacto. |
| **P2** | **Piloto en sitio con Ferretería El Campín** | Reemplazar el stock fijo de prueba por conexión o importación periódica de existencias observadas del ERP/POS. | Inventario reflejando disponibilidad física real en Bucaramanga; sin asignaciones sintéticas. |
| **P3** | **Prueba en vivo de botones Kapso en sandbox** | Ejecutar una sesión completa del embudo guiado desde un smartphone en WhatsApp Cloud API vía Kapso. | Pulsación de botón físico capturada por el webhook, procesada sin LLM y respondida en menos de 1.5 segundos. |
| **P4** | **Worker asíncrono para el Outbox** | Implementar un proceso en segundo plano dedicado a consumir la tabla `kapso_outbox` con política de reintentos exponenciales (*exponential backoff*). | Tolerancia a cortes temporales de la API de Meta/Kapso sin pérdida de mensajes ni bloqueo del webhook entrante. |
| **P5** | **Reglas de retención de datos operativos (M5)** | Definir y configurar el período de vida útil (*TTL*) para logs de auditoría, estados de conversación inactivos y eventos de webhook. | Job periódico de purga automática sin borrado de cotizaciones confirmadas o aprobadas. |


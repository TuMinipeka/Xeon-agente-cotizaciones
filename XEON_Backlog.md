# XEON — Backlog Funcional y Criterios de Calidad

**Proyecto:** XEON  
**Versión:** 1.0  
**Estado:** Specification to start development  
**Fecha:** 2026-10-07

---

## 1. Descripción general

XEON es un agente de IA orientado a la asistencia comercial y preparación de cotizaciones para empresas de ferretería, agroferretería, distribuidores y negocios de hardware.

El sistema conversa con compradores, identifica los productos solicitados, consulta información empresarial y prepara una cotización que posteriormente puede ser revisada, corregida y aprobada por un asesor humano.

El objetivo principal es reducir el tiempo operativo del vendedor y permitir atender simultáneamente a más clientes.

---

# 2. Épicas

| ID | Épica | Objetivo |
|---|---|---|
| EP-01 | Gestión de conversaciones | Recibir, procesar y mantener conversaciones independientes con compradores. |
| EP-02 | Catálogo y búsqueda de productos | Identificar productos, referencias, unidades, atributos y sustitutos. |
| EP-03 | Inventario y abastecimiento | Consultar disponibilidad por sede y manejar información de abastecimiento. |
| EP-04 | Cotización y reglas comerciales | Calcular precios, descuentos, impuestos, totales y crear cotizaciones. |
| EP-05 | Revisión y aprobación humana | Permitir que un asesor revise, modifique y apruebe una versión de cotización. |
| EP-06 | Generación y entrega de cotizaciones | Generar el PDF aprobado y entregarlo al comprador. |
| EP-07 | IA y agente XEON | Interpretar solicitudes y seleccionar herramientas de forma controlada. |
| EP-08 | Seguridad, trazabilidad y operación | Proteger información, registrar eventos y garantizar recuperación ante fallos. |

---

# 3. Historias de usuario

## EP-01 — Gestión de conversaciones

### HU-01 — Recibir solicitud del comprador

**Como** comprador  
**quiero** enviar una solicitud mediante el canal disponible  
**para** iniciar el proceso de cotización.

### SubTasks

- Implementar recepción de mensajes de Telegram.
- Validar la identidad del canal y del usuario.
- Crear o recuperar la conversación.
- Persistir el mensaje recibido.
- Manejar `external_event_id` y `external_message_id`.
- Implementar deduplicación de eventos.
- Mantener conversaciones aisladas entre usuarios.

### Criterios de aceptación

- El sistema recibe mensajes mediante Telegram.
- Cada usuario mantiene una conversación independiente.
- Los eventos duplicados no generan un segundo efecto de negocio.
- El mensaje recibido queda registrado.
- Un usuario no autorizado no puede acceder a información empresarial.
- La conversación puede recuperarse después de un reinicio.

### Scope

**Incluido:**

- Telegram.
- Conversaciones persistentes.
- Identidad por `channel_account_id`.
- Deduplicación.
- Recuperación de estado.

**Fuera de scope:**

- WhatsApp en MVP.
- Campañas masivas.
- Otros canales no definidos.

### Criterios de calidad

- Integridad de mensajes.
- Aislamiento entre conversaciones.
- Idempotencia.
- Trazabilidad.
- Recuperabilidad.

### RF relacionados

- RF-01
- RF-02
- RF-23
- RF-24
- RF-25

### RNF relacionados

- RNF-02
- RNF-03
- RNF-04
- RNF-06
- RNF-08

---

## HU-02 — Identificar productos solicitados

**Como** comprador  
**quiero** describir los productos que necesito  
**para** que XEON identifique las referencias y cantidades necesarias.

### SubTasks

- Extraer productos de la solicitud.
- Identificar cantidades.
- Identificar unidades.
- Buscar coincidencias en catálogo.
- Detectar ambigüedad.
- Solicitar aclaraciones cuando sean necesarias.
- Identificar posibles sustitutos.

### Criterios de aceptación

- Una referencia válida puede ser identificada.
- La cantidad es interpretada correctamente.
- Si falta una unidad necesaria, XEON solicita aclaración.
- Si la solicitud es ambigua, XEON no inventa una referencia.
- Se pueden presentar alternativas cuando existan.
- La información utilizada queda asociada a su fuente.

### Scope

**Incluido:**

- Texto en español.
- Catálogo.
- Alias.
- Atributos.
- Referencias.
- Sustitutos.

**Fuera de scope:**

- Compra autónoma.
- Modificación automática del inventario.

### Criterios de calidad

- Exactitud.
- Manejo de ambigüedad.
- Trazabilidad.
- No alucinación comercial.

### RF relacionados

- RF-03
- RF-04
- RF-05

### RNF relacionados

- RNF-01
- RNF-04
- RNF-05

---

# EP-02 — Catálogo y búsqueda de productos

## HU-03 — Consultar disponibilidad por sede

**Como** vendedor  
**quiero** conocer la disponibilidad de un producto por sede  
**para** determinar desde dónde puede atenderse la solicitud.

### SubTasks

- Consultar inventario.
- Consultar existencias por sucursal/almacén.
- Identificar fecha de actualización.
- Diferenciar stock real de información desconocida.
- Detectar información obsoleta.
- Identificar productos disponibles en otras sedes.

### Criterios de aceptación

- Se muestran las sedes con disponibilidad conocida.
- Un error de conexión no se interpreta como stock cero.
- Los datos antiguos se identifican como obsoletos.
- No se promete disponibilidad cuando la información no es confiable.
- El sistema distingue stock, traslado y entrega.

### Scope

**Incluido:**

- Inventario por sede.
- Fecha de actualización.
- Datos sintéticos.
- Adaptador CSV.
- Integración futura con ERP.

**Fuera de scope:**

- Ejecutar traslados.
- Modificar inventario automáticamente.

### Criterios de calidad

- Consistencia.
- Trazabilidad de la fuente.
- Manejo explícito de incertidumbre.

### RF relacionados

- RF-06
- RF-07

### RNF relacionados

- RNF-01
- RNF-04
- RNF-07

---

# EP-03 — Inventario y abastecimiento

## HU-04 — Crear cotización

**Como** vendedor  
**quiero** crear una cotización con los productos solicitados  
**para** presentar una propuesta comercial al comprador.

### SubTasks

- Crear cotización en estado `DRAFT`.
- Agregar líneas.
- Calcular precios.
- Aplicar reglas comerciales.
- Calcular impuestos.
- Calcular totales.
- Persistir la cotización.
- Crear versión inicial.

### Criterios de aceptación

- Una solicitud válida genera un borrador.
- Las cantidades son válidas.
- Los precios provienen de una fuente identificable.
- Los cálculos utilizan `Decimal`.
- La moneda está explícitamente definida.
- La cotización queda versionada.

### Scope

**Incluido:**

- Cotizaciones.
- Líneas.
- Precios.
- Impuestos.
- Totales.
- Versionamiento.

**Fuera de scope:**

- Reserva automática.
- Conversión automática a pedido.
- Pago.

### Criterios de calidad

- Exactitud matemática.
- Integridad transaccional.
- Versionamiento.
- Trazabilidad.

### RF relacionados

- RF-08
- RF-10
- RF-11
- RF-12

### RNF relacionados

- RNF-01
- RNF-05
- RNF-08

---

## HU-05 — Aplicar descuentos autorizados

**Como** vendedor  
**quiero** que se validen los descuentos según las reglas de la empresa  
**para** evitar condiciones comerciales no autorizadas.

### SubTasks

- Consultar reglas comerciales.
- Validar descuento.
- Aplicar orden de descuentos.
- Validar acumulación.
- Registrar origen de la regla.
- Escalar cuando la condición no esté autorizada.

### Criterios de aceptación

- Los descuentos se calculan según reglas configuradas.
- XEON no inventa porcentajes máximos.
- Un descuento no autorizado es rechazado o escalado.
- El resultado indica la fuente y versión de la regla.

### RF relacionados

- RF-09

### RNF relacionados

- RNF-01
- RNF-04

---

# EP-04 — Cotización y reglas comerciales

## HU-06 — Revisar cotización

**Como** asesor autorizado  
**quiero** revisar una cotización  
**para** verificar y corregir la propuesta antes de aprobarla.

### SubTasks

- Consultar cotización.
- Consultar líneas.
- Modificar líneas.
- Revisar precios.
- Revisar descuentos.
- Revisar disponibilidad.
- Guardar una nueva versión.

### Criterios de aceptación

- Solo un usuario autorizado puede revisar.
- Las modificaciones generan una nueva versión.
- La versión anterior permanece disponible.
- Una modificación posterior a una aprobación invalida la aprobación anterior.

### RF relacionados

- RF-13
- RF-15

### RNF relacionados

- RNF-02
- RNF-04
- RNF-08

---

## HU-07 — Versionar cotizaciones

**Como** asesor  
**quiero** que cada modificación genere una versión identificable  
**para** mantener un historial confiable de la cotización.

### SubTasks

- Crear versiones.
- Asociar cambios.
- Mantener versión anterior.
- Identificar versión actual.
- Asociar aprobación a una versión específica.

### Criterios de aceptación

- Cada modificación relevante genera una versión.
- Una aprobación está vinculada a una versión concreta.
- Una versión antigua no puede utilizarse como aprobación de una versión nueva.
- El historial puede consultarse.

### RF relacionados

- RF-12
- RF-15
- RF-20

### RNF relacionados

- RNF-04
- RNF-08

---

# EP-05 — Revisión y aprobación humana

## HU-08 — Generar PDF

**Como** asesor autorizado  
**quiero** generar un PDF de una cotización aprobada  
**para** entregarla al comprador.

### SubTasks

- Validar que la versión esté aprobada.
- Cargar plantilla de la empresa.
- Generar documento.
- Incluir productos, unidades, precios y totales.
- Generar archivo.
- Persistir referencia del documento.

### Criterios de aceptación

- No se genera una cotización final sin aprobación.
- El PDF corresponde a la versión aprobada.
- Los totales coinciden con la cotización.
- Se mantienen unidades, moneda y datos comerciales.
- El documento puede ser enviado posteriormente.

### Scope

**Incluido:**

- PDF.
- Plantillas por empresa.
- WeasyPrint.
- Almacenamiento local.

### RF relacionados

- RF-16
- RF-17

### RNF relacionados

- RNF-01
- RNF-05
- RNF-09

---

## HU-09 — Enviar cotización al comprador

**Como** comprador  
**quiero** recibir la cotización aprobada  
**para** conocer la propuesta comercial.

### SubTasks

- Validar aprobación.
- Generar/obtener PDF.
- Preparar mensaje.
- Enviar documento mediante Telegram.
- Registrar resultado del envío.
- Manejar reintentos controlados.
- Gestionar estado incierto.

### Criterios de aceptación

- Solo se puede enviar una cotización aprobada.
- El documento corresponde a la versión aprobada.
- Los reintentos no generan efectos comerciales duplicados.
- Un timeout de envío genera estado `UNCERTAIN` cuando no se puede confirmar el resultado.
- El sistema no realiza reenvíos ciegos.

### RF relacionados

- RF-18
- RF-23
- RF-24

### RNF relacionados

- RNF-03
- RNF-06
- RNF-08

---

# EP-06 — Generación y entrega de cotizaciones

## HU-10 — Interpretar solicitudes mediante IA

**Como** sistema  
**quiero** utilizar un agente de IA para interpretar las solicitudes  
**para** convertir lenguaje natural en acciones comerciales controladas.

### SubTasks

- Implementar grafo de LangGraph.
- Implementar contexto.
- Implementar selección de herramientas.
- Integrar `LLMPort`.
- Implementar adaptador de Grok 4.6.
- Implementar modo `MockLLM`.
- Limitar pasos, tokens y tiempo.
- Validar permisos de herramientas.

### Criterios de aceptación

- La IA puede interpretar solicitudes.
- La IA puede seleccionar herramientas disponibles.
- La IA no puede aprobar cotizaciones.
- La IA no puede ejecutar SQL arbitrario.
- La IA no puede modificar inventario.
- Las decisiones comerciales finales pertenecen al backend.
- Un intento de prompt injection es rechazado.

### Principio fundamental

> La IA interpreta; el backend decide y calcula.

### RF relacionados

- RF-26
- RF-27

### RNF relacionados

- RNF-01
- RNF-04
- RNF-05
- RNF-10

---

## HU-11 — Escalar a un humano

**Como** comprador  
**quiero** ser atendido por un asesor cuando XEON no pueda resolver mi solicitud  
**para** evitar respuestas incorrectas.

### SubTasks

- Detectar necesidad de intervención.
- Crear solicitud de atención.
- Transferir contexto.
- Cambiar estado de conversación.
- Detener al bot mientras el humano está activo.
- Registrar cierre de atención.

### Criterios de aceptación

- Una situación no resoluble puede escalarse.
- El asesor recibe el contexto relevante.
- Cuando un humano toma la conversación, el bot deja de responder automáticamente.
- La atención queda registrada.
- El comprador no recibe información inventada.

### RF relacionados

- RF-19

### RNF relacionados

- RNF-04
- RNF-08

---

# EP-07 — IA y agente XEON

## HU-12 — Controlar acceso

**Como** administrador  
**quiero** controlar quién puede acceder a información y operaciones  
**para** proteger los datos comerciales.

### SubTasks

- Implementar autenticación OIDC.
- Integrar Keycloak.
- Validar permisos.
- Implementar aislamiento por empresa.
- Implementar aislamiento por sucursal cuando corresponda.
- Aplicar autorización en API y herramientas.
- Mantener allowlist para usuarios de Telegram durante el desarrollo.

### Criterios de aceptación

- Un usuario no autorizado no puede consultar información.
- No existe acceso cruzado entre empresas.
- Las herramientas respetan permisos.
- Los documentos y datos están protegidos.
- Un usuario de Telegram fuera de la allowlist no consume información privada ni llamadas al LLM.

### RF relacionados

- RF-21
- RF-22

### RNF relacionados

- RNF-02
- RNF-10
- RNF-11

---

## HU-13 — Mantener trazabilidad

**Como** administrador  
**quiero** conocer el origen y evolución de cada dato comercial  
**para** poder auditar las decisiones del sistema.

### SubTasks

- Registrar fuente.
- Registrar fecha de actualización.
- Registrar versión.
- Registrar eventos.
- Registrar cambios de cotización.
- Registrar aprobaciones.
- Registrar envíos.
- Implementar logs estructurados.
- Integrar tracing.

### Criterios de aceptación

- Los datos comerciales relevantes tienen procedencia.
- Se puede identificar la versión de una cotización.
- Se puede consultar quién aprobó.
- Se pueden reconstruir eventos relevantes.
- Los errores quedan registrados.
- Los logs no exponen secretos.

### RF relacionados

- RF-20
- RF-28

### RNF relacionados

- RNF-04
- RNF-07
- RNF-12

---

# EP-08 — Seguridad, trazabilidad y operación

## HU-14 — Recuperarse ante fallos

**Como** sistema  
**quiero** recuperarme de errores y reinicios  
**para** evitar pérdida o duplicación de información.

### SubTasks

- Implementar reintentos controlados.
- Implementar persistencia de eventos.
- Implementar Outbox.
- Persistir cursor de Telegram.
- Implementar recuperación de workers.
- Implementar backups.
- Probar restauración.
- Manejar envíos inciertos.

### Criterios de aceptación

- Un reinicio no elimina conversaciones.
- Un evento procesado no genera un segundo efecto de negocio.
- Un fallo antes de persistir no avanza el cursor.
- Un fallo después de persistir permite recuperar el procesamiento.
- Los backups pueden restaurarse.
- Los envíos inciertos no se reenvían automáticamente a ciegas.

### RF relacionados

- RF-23
- RF-24
- RF-25

### RNF relacionados

- RNF-03
- RNF-06
- RNF-08
- RNF-09

---

# 4. Requisitos funcionales

| ID | Requisito |
|---|---|
| RF-01 | Recibir mensajes mediante Telegram. |
| RF-02 | Mantener conversaciones independientes. |
| RF-03 | Identificar productos y cantidades. |
| RF-04 | Solicitar aclaraciones ante referencias ambiguas. |
| RF-05 | Consultar el catálogo. |
| RF-06 | Consultar stock por sede. |
| RF-07 | Diferenciar stock cero, desconocido y datos obsoletos. |
| RF-08 | Calcular precios mediante reglas comerciales. |
| RF-09 | Validar descuentos autorizados. |
| RF-10 | Calcular impuestos y totales. |
| RF-11 | Crear borradores de cotización. |
| RF-12 | Versionar cotizaciones. |
| RF-13 | Permitir revisión humana. |
| RF-14 | Permitir aprobación humana. |
| RF-15 | Invalidar una aprobación cuando cambia la versión. |
| RF-16 | Generar PDF de una cotización aprobada. |
| RF-17 | Utilizar plantillas específicas de la empresa. |
| RF-18 | Enviar la cotización aprobada mediante Telegram. |
| RF-19 | Escalar conversaciones a un humano. |
| RF-20 | Registrar trazabilidad y procedencia de información. |
| RF-21 | Autenticar operadores internos. |
| RF-22 | Controlar permisos por empresa/sucursal. |
| RF-23 | Implementar reintentos controlados. |
| RF-24 | Evitar efectos comerciales duplicados. |
| RF-25 | Recuperar conversaciones y trabajos después de fallos. |
| RF-26 | Soportar modo `MockLLM`. |
| RF-27 | Integrar Grok 4.6 mediante `LLMPort`. |
| RF-28 | Registrar logs y trazas operativas. |

---

# 5. Requisitos no funcionales

| ID | Categoría | Requisito |
|---|---|---|
| RNF-01 | Integridad | Los cálculos comerciales deben ser deterministas y utilizar `Decimal`. |
| RNF-02 | Seguridad | El acceso debe estar autenticado y autorizado. |
| RNF-03 | Confiabilidad | Los mensajes y operaciones deben soportar reintentos controlados. |
| RNF-04 | Trazabilidad | Los datos comerciales deben tener fuente, fecha y/o versión cuando corresponda. |
| RNF-05 | Testabilidad | Las reglas críticas deben contar con pruebas automatizadas. |
| RNF-06 | Recuperación | El sistema debe recuperarse después de reinicios y fallos controlados. |
| RNF-07 | Observabilidad | El sistema debe generar logs estructurados y trazas. |
| RNF-08 | Consistencia | Las operaciones críticas deben mantener integridad transaccional. |
| RNF-09 | Respaldo | La información debe contar con mecanismos de backup y restauración. |
| RNF-10 | Seguridad de IA | El modelo no debe ejecutar operaciones fuera de sus permisos. |
| RNF-11 | Aislamiento | Los datos de diferentes empresas/clientes deben estar aislados. |
| RNF-12 | Auditoría | Las aprobaciones, versiones y operaciones relevantes deben poder auditarse. |
| RNF-13 | Rendimiento | Un borrador estándar debe buscar como objetivo inicial menos de 60 segundos con fuentes disponibles. |
| RNF-14 | Escalabilidad | La arquitectura debe permitir aumentar capacidad sin convertir el MVP en microservicios innecesarios. |
| RNF-15 | Mantenibilidad | El dominio y las reglas comerciales deben estar desacoplados de infraestructura. |
| RNF-16 | Portabilidad | El sistema debe poder ejecutarse localmente mediante Docker Compose. |
| RNF-17 | Configurabilidad | Secretos, tokens, conexiones y parámetros deben estar fuera del código. |
| RNF-18 | Reproducibilidad | El proyecto debe utilizar `uv`, `pyproject.toml` y lockfile. |
| RNF-19 | Calidad de código | Se deben utilizar Ruff, mypy y pruebas automatizadas. |
| RNF-20 | Compatibilidad | Las integraciones externas deben estar encapsuladas mediante adaptadores/puertos. |
| RNF-21 | Privacidad | No se deben utilizar datos reales no autorizados en el MVP. |
| RNF-22 | Disponibilidad | Los workers deben poder reiniciarse sin perder trabajos persistidos. |
| RNF-23 | Idempotencia | Eventos externos repetidos no deben producir efectos de negocio duplicados. |
| RNF-24 | Control | Las operaciones críticas deben requerir autorización humana cuando corresponda. |
| RNF-25 | Demo | Los datos sintéticos deben identificarse explícitamente como ficticios. |

---

# 6. Criterios generales de calidad

| ID | Criterio | Descripción |
|---|---|---|
| CQ-01 | Correctness | Los cálculos, estados y decisiones comerciales deben ser correctos. |
| CQ-02 | Security | La información y las operaciones deben estar protegidas mediante autenticación y autorización. |
| CQ-03 | Reliability | El sistema debe manejar fallos, reintentos y recuperación sin perder información. |
| CQ-04 | Traceability | Debe existir trazabilidad sobre datos, versiones, aprobaciones y eventos. |
| CQ-05 | Testability | Las reglas críticas deben ser verificables mediante pruebas automatizadas. |
| CQ-06 | Maintainability | El código debe estar modularizado y mantener separadas las responsabilidades. |
| CQ-07 | Observability | Los eventos, errores, latencias y operaciones deben poder observarse. |
| CQ-08 | Performance | El sistema debe mantener tiempos de respuesta razonables y medir p50/p95. |

---

# 7. Scope del MVP

## Incluido

- Conversación en español.
- Telegram como primer canal.
- Catálogo de productos.
- Unidades, aliases y atributos.
- Búsqueda de referencias.
- Inventario por sede/almacén.
- Fecha de actualización de fuentes.
- Precios y descuentos mediante reglas explícitas.
- Preparación de cotizaciones.
- Revisión humana.
- Aprobación humana.
- Versionamiento.
- Generación de PDF.
- Historial de conversaciones.
- Recuperación de estado.
- Auditoría.
- Solicitudes de abastecimiento.
- Escalamiento a humano.
- CLI autenticada.
- Datos sintéticos.
- Adaptador CSV.
- Ejecución local.
- Reintentos controlados.
- Backups.
- Pruebas automatizadas.
- Modo MockLLM.
- Integración con Grok 4.6.

## Fuera del MVP

- WhatsApp como canal inicial.
- Reservas reales.
- Conversión automática a pedido.
- Seguimientos automáticos.
- Predicción de demanda.
- Autoaprobación de cotizaciones.
- Compras autónomas.
- Pagos.
- Campañas masivas.
- Modificación autónoma de inventario.
- Fine-tuning.
- Múltiples agentes autónomos.
- AWS como infraestructura obligatoria.
- Kubernetes.
- Microservicios empresariales.

---

# 8. Criterios de aceptación globales

El MVP se considera funcional cuando:

- [ ] Un comprador puede iniciar una conversación por Telegram.
- [ ] XEON puede interpretar una solicitud válida.
- [ ] XEON solicita aclaraciones cuando existe ambigüedad.
- [ ] El catálogo puede ser consultado.
- [ ] El inventario puede consultarse por sede.
- [ ] El sistema diferencia información desconocida de stock cero.
- [ ] Se puede crear una cotización `DRAFT`.
- [ ] Las reglas comerciales se aplican correctamente.
- [ ] La cotización puede ser modificada por un asesor.
- [ ] Las modificaciones crean una nueva versión.
- [ ] Una aprobación está asociada a una versión concreta.
- [ ] Una modificación invalida la aprobación anterior.
- [ ] Solo un humano autorizado puede aprobar.
- [ ] Se genera un PDF de una versión aprobada.
- [ ] El PDF puede enviarse al comprador.
- [ ] Un fallo de envío no genera un reenvío ciego.
- [ ] Las conversaciones permanecen aisladas.
- [ ] Los usuarios no autorizados no acceden a información.
- [ ] Los eventos duplicados no producen efectos comerciales duplicados.
- [ ] El sistema puede recuperarse después de reinicios.
- [ ] Los datos comerciales cuentan con trazabilidad.
- [ ] Las pruebas automatizadas cubren las reglas críticas.
- [ ] El proyecto puede ejecutarse localmente.
- [ ] El modo MockLLM no realiza llamadas externas a xAI.

---

# 9. Casos mínimos de prueba

| ID | Caso |
|---|---|
| T01 | SKU válido + cantidad válida crea un borrador exacto. |
| T02 | Solicitud ambigua como “coso del aire” solicita aclaración. |
| T03 | Solicitud sin unidad necesaria solicita aclaración. |
| T04 | Producto disponible en otra sede identifica correctamente el origen. |
| T05 | Disponibilidad parcial explica faltantes y alternativas. |
| T06 | Fuente caída no se interpreta como producto agotado. |
| T07 | Snapshot obsoleto muestra su antigüedad y evita promesa firme. |
| T08 | Descuento no autorizado se rechaza o escala. |
| T09 | Una cotización modificada después de aprobación no puede enviarse con la aprobación antigua. |
| T10 | Evento duplicado de Telegram no genera segundo efecto de negocio. |
| T11 | Dos conversaciones simultáneas permanecen aisladas. |
| T12 | Fallo del receptor después de persistir permite recuperación sin duplicación. |
| T13 | Fallo antes de persistir no avanza el cursor. |
| T14 | Usuario fuera de allowlist no recibe datos ni consume LLM. |
| T15 | Prompt intentando aprobar o ejecutar SQL es rechazado. |
| T16 | Cuando un humano toma la conversación, el bot deja de responder. |
| T17 | PDF grande conserva totales, páginas, acentos y unidades. |
| T18 | Reinicio del contenedor conserva DB, versiones y archivos. |
| T19 | MockLLM genera cero llamadas externas a xAI. |
| T20 | Con frontend deshabilitado, CLI + agente completan el MVP. |
| T21 | Acceso cruzado entre empresas/clientes es rechazado. |
| T22 | Timeout de envío queda en estado incierto y no se realiza reenvío ciego. |

---

# 10. Definition of Done

Una historia se considera terminada cuando:

- [ ] Cumple sus criterios de aceptación.
- [ ] Existe una demostración reproducible.
- [ ] Las pruebas relevantes pasan.
- [ ] El código cumple formato y tipado.
- [ ] Se realizó revisión por pares cuando afecta contratos o reglas compartidas.
- [ ] No contiene secretos.
- [ ] No utiliza datos reales no autorizados.
- [ ] No agrega dependencias pagas no aprobadas.
- [ ] Las migraciones están actualizadas.
- [ ] La configuración está actualizada.
- [ ] La documentación está actualizada.
- [ ] Las limitaciones conocidas están documentadas.
- [ ] Ninguna funcionalidad incompleta se presenta como terminada.

---

# 11. Demo funcional del MVP

La demostración debe utilizar una empresa ficticia y:

1. Crear tres sucursales ficticias.
2. Cargar un catálogo sintético.
3. El comprador solicitará cemento y alambre.
4. XEON identificará los productos.
5. XEON solicitará información faltante cuando sea necesario.
6. XEON consultará disponibilidad.
7. XEON creará el borrador.
8. El vendedor revisará la cotización mediante CLI.
9. El vendedor modificará una línea.
10. El sistema creará una nueva versión.
11. La aprobación de la versión anterior dejará de ser válida.
12. El vendedor aprobará la versión actual.
13. Se generará el PDF.
14. Se enviará el documento al comprador.
15. Se demostrará una solicitud ambigua.
16. Se demostrará un fallo de fuente.
17. Se demostrará el reinicio de un worker.
18. Se revisarán trazas, costos, errores y tiempos.
19. Se registrarán las tareas pendientes.

---

# 12. Métricas de éxito

Las métricas iniciales son:

- Tiempo hasta generar el borrador.
- Minutos de revisión activa.
- Correcciones por cotización.
- Número de preguntas de aclaración.
- Porcentaje de escalamiento.
- Errores comerciales.
- Latencia de fuentes.
- Costo de inferencia.
- p50 de tiempo de respuesta.
- p95 de tiempo de respuesta.

Objetivo inicial:

> Una cotización estándar debe poder generar un borrador en menos de 60 segundos cuando las fuentes necesarias están disponibles.

El tiempo del sistema debe diferenciarse del tiempo de espera humano.

---

# 13. Principios obligatorios

1. **La IA interpreta; el backend decide y calcula.**
2. Todo dato comercial debe tener procedencia.
3. Información desconocida no significa stock cero.
4. La intervención humana es una funcionalidad del producto.
5. Una cotización no equivale a una reserva.
6. La aprobación pertenece a una versión específica.
7. Las modificaciones posteriores a una aprobación deben invalidar dicha aprobación.
8. Los reintentos no deben duplicar efectos evitables.
9. Los datos sintéticos deben identificarse como ficticios.
10. El comprador no necesita una aplicación web para utilizar XEON.
11. Las operaciones comerciales críticas no deben quedar bajo control autónomo del modelo.

---

# 14. Jerarquía del backlog

```text
XEON
│
├── EP-01 Gestión de conversaciones
│   └── HU-01 Recibir solicitud
│
├── EP-02 Catálogo y búsqueda
│   └── HU-02 Identificar productos
│
├── EP-03 Inventario y abastecimiento
│   └── HU-03 Consultar disponibilidad
│
├── EP-04 Cotización y reglas comerciales
│   ├── HU-04 Crear cotización
│   └── HU-05 Aplicar descuentos
│
├── EP-05 Revisión y aprobación humana
│   ├── HU-06 Revisar cotización
│   └── HU-07 Versionar cotizaciones
│
├── EP-06 Generación y entrega
│   ├── HU-08 Generar PDF
│   └── HU-09 Enviar cotización
│
├── EP-07 IA y agente XEON
│   ├── HU-10 Interpretar solicitudes
│   └── HU-11 Escalar a humano
│
└── EP-08 Seguridad, trazabilidad y operación
    ├── HU-12 Controlar acceso
    ├── HU-13 Mantener trazabilidad
    └── HU-14 Recuperarse ante fallos
```

---

# 15. Arquitectura relacionada con el backlog

XEON utiliza un **monolito modular con arquitectura hexagonal**.

```text
                    ┌─────────────────────┐
                    │       Telegram      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │        API          │
                    │ Auth / Validation   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     Application     │
                    │      Use Cases      │
                    └──────────┬──────────┘
                               │
             ┌─────────────────▼─────────────────┐
             │              Domain               │
             │ Entities / Rules / Policies       │
             └─────────────────┬─────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼───────┐      ┌───────▼───────┐      ┌──────▼──────┐
│  PostgreSQL   │      │     xAI        │      │   Telegram  │
│   + pgvector  │      │   Grok 4.6    │      │     API     │
└───────────────┘      └───────────────┘      └─────────────┘
```

Los workers ejecutan la misma lógica de negocio que la API y no duplican las reglas comerciales.

---

# 16. Stack tecnológico

| Área | Tecnología |
|---|---|
| Lenguaje | Python 3.14 |
| Gestión | uv / pyproject / lockfile |
| API | FastAPI / Uvicorn / Pydantic |
| Dominio | Python / Decimal |
| Agente | LangGraph |
| LLM | Grok 4.6 vía xAI |
| Persistencia | PostgreSQL 17 |
| ORM | SQLAlchemy 2 |
| Driver | psycopg 3 |
| Migraciones | Alembic |
| Búsqueda | PostgreSQL FTS / pg_trgm / pgvector |
| Embeddings | Sentence Transformers multilingual-e5-small |
| PDF | pypdf / Jinja2 / WeasyPrint |
| Jobs | Celery / RabbitMQ |
| Scheduler | Celery Beat |
| Canal MVP | Telegram Bot API / HTTPX |
| CLI | Typer / HTTPX |
| Auth | Keycloak / OIDC / Authlib |
| Frontend opcional | Jinja2 / HTMX |
| Infraestructura | Docker Compose / Linux / WSL2 |
| Observabilidad | structlog / OpenTelemetry |
| Monitoring opcional | Prometheus / Loki / Tempo / Grafana |
| Backups | pgBackRest / restic |
| Testing | Pytest / HTTPX / Hypothesis / Testcontainers |
| E2E opcional | Playwright |
| Calidad | Ruff / mypy |
| CI/CD | GitHub Actions / GHCR |

---

# 17. Estado del documento

**Estado:** Especificación para iniciar desarrollo.

Antes de comenzar el desarrollo se deben confirmar:

- Repositorio.
- Distribución de responsabilidades.
- Contratos internos.
- Datos sintéticos.
- Reglas comerciales.
- Casos de prueba.
- Acceso Git.
- Entorno local.
- Bots personales de Telegram.
- Tokens y allowlist.
- Ejecución inicial con MockLLM.
- Presupuesto.

Antes de un piloto real se debe validar adicionalmente:

- Fuente ERP.
- Permisos.
- Semántica real de stock.
- Precios.
- Descuentos.
- Impuestos.
- Reglas de aprobación.
- Logística.
- Calendarios.
- Identidad y retención de compradores.
- Recuperación.
- Aislamiento.
- Envíos inciertos.
- Soporte humano.
- Integración con WhatsApp.
- Aceptación del negocio.

# Entrega y Análisis S3 — XEON (Semana 3)

**Período analizado:** Desde el último commit del 24 de octubre de 2026 (`034e7d9` / cierre Hito #2) hasta el 31 de octubre de 2026 (`1e50603`).  
**Rama de trabajo activa:** `QA/testing` (con base sincronizada de `developer/daniel`).  
**Tema general del Hito S3:** **Datos reales, evaluación propia y costo por tarea**.  
**Responsables del corte:** Daniel Mayorga y Juan Pablo Conde Zapata.  

---

## 1. Propósito de este paquete documental

Este directorio reúne la documentación integral, técnica, arquitectónica y operativa del ciclo **Semana 3 (Hito S3)** del proyecto XEON. Responde puntualmente a la solicitud de consolidación del trabajo realizado tras el cierre del Hito #2, estructurando la evidencia en siete ejes fundamentales:

1. **[01. Lo que se implementó](01_lo_que_se_implemento.md):** Inventario técnico exhaustivo de componentes desarrollados (embudo guiado único, persistencia operativa en PostgreSQL propio, panel web del asesor con revisión y PDF, outbox durable de Kapso, telemetría y costo por tarea, arnés de evaluación conversacional con 22 escenarios, base de datos comercial normalizada en 4FN con 4.830 SKU reales de Ferretería El Campín, cimiento de pgvector y ciclo de QA).
2. **[02. Limitaciones y siguientes pasos S3](02_limitaciones_y_siguientes_pasos.md):** Fronteras y restricciones honestas observadas (embeddings y búsqueda ANN pendientes, stock de Bucaramanga como excepción controlada de pruebas, sesiones del panel en memoria, copiloto Gmail post-MVP) y hoja de ruta para S4.
3. **[03. Problemas que ocurrieron y su resolución](03_problemas_que_ocurrieron.md):** Bitácora detallada de incidentes, defectos de software, problemas de concurrencia y retos de infraestructura superados durante la semana (etiquetado prematuro de totales, agregación multilínea de stock, colisiones con palabras clave en direcciones, rollback transaccional de notificaciones, orden de borrado bajo FK `RESTRICT` en semillas, compilación de pgvector en Windows).
4. **[04. Matriz de cumplimiento S3 — Datos reales](04_matriz_cumplimiento_s3_datos_reales.md):** Cuadro de trazabilidad y verificación que evalúa cada compromiso del Hito S3 frente a la implementación real en código, pruebas automatizadas y base de datos.
5. **[05. Estado actual de XEON en S3](05_estado_xeon_s3.md):** Radiografía arquitectónica del sistema (arquitectura hexagonal, puertos y adaptadores, separación estricta entre persistencia operativa y base comercial, comandos CLI, suite de pruebas y gates de calidad).
6. **[06. Datos y procedencia S3](06_datos_y_procedencia_s3.md):** Registro de origen, integridad criptográfica (SHA-256), esquema de sanitización de datos empresariales, volumen de registros reales y separación de responsabilidades entre datos sintéticos y comerciales.
7. **[Cambios de Conde — 31 de octubre](../CONDE_IMPLEMENTADO_31_OCTUBRE.md):** Detalle commit por commit de las 33 contribuciones realizadas por Juan Pablo Conde el 31 de octubre de 2026 en la rama `QA/testing`.

---

## 2. Resumen ejecutivo de los 3 temas centrales de S3

### Eje 1: Datos reales (Ferretería El Campín)
- Se incorporó un catálogo real sanitizado de **4.830 artículos comerciales (SKUs)** con descripciones, marcas, familias, impuestos y 5 listas de precios versionadas en PostgreSQL 18.6 con la extensión `pgvector` 0.8.7.
- El modelo comercial se estructuró hasta **Cuarta Forma Normal (4FN)**, separando dimensiones de negocio, productos, taxonomía, vigencias tributarias, listas de precio y stock multisede.
- Se implementó un cargador transaccional determinista con verificación criptográfica SHA-256 en el manifiesto de datos, repetible e idempotente, conectado mediante el adaptador declarativo de solo lectura.

### Eje 2: Evaluación propia (Arnés conversacional determinista)
- Se desarrolló una suite de evaluación conversacional con **22 escenarios end-to-end (S01–S22)** que simulan compradores reales mediante arquetipos predefinidos.
- Dispone de un ejecutor con dos modos:
  - **Modo offline (costo $0):** Utiliza un modelo simulado determinista y evalúa oráculos de negocio sin llamadas a proveedores externos.
  - **Modo live:** Ejecuta evaluaciones reales contra el modelo de lenguaje en la nube con límites estrictos de presupuesto y medición de adherencia a contratos.
- Las fixtures y oráculos del evaluador son inmutables: ningún defecto se oculta relajando aserciones.

### Eje 3: Costo por tarea (Telemetría y observabilidad)
- Se construyó el sistema de telemetría y métricas con persistencia estructurada, recolectando latencias por etapa (turno general, inferencia de inteligencia artificial, reglas de negocio, catálogo, inventario y mensajería).
- Captura de tokens reales de entrada y salida directamente desde la telemetría del proveedor del modelo de lenguaje.
- Utilidad analítica para calcular el costo monetario en USD por cada tarea, escenario de evaluación o conversación comercial.

---

## 3. Estado de verificación del corte

- **Linters y tipos:** `ruff check .`, `ruff format --check .` y `mypy src evals` aprobados sin errores.
- **Pruebas unitarias y de integración local:** Suite de pytest con **422 pruebas aprobadas** en modo estándar determinista.
- **Evaluación offline:** S01–S22 ejecutadas en 3 repeticiones consecutivas: **66 PASS, 0 FAIL, 0 ERROR**.
- **Integridad de documentación:** Enlaces relativos verificados con `scripts/check_doc_links.py` (0 rotos).


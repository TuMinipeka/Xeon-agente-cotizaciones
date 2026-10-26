---
tags:
  - xeon/operacion
---

# PDF del borrador (Sonnet, 2026-10-26)

Fecha: 2026-10-26. Autor: Sonnet. Worktree `C:\\Users\\danie\\Documents\\xp`, rama `feat/quote-pdf` (desde `c4d1c0a`). Estado: **implementado y verificado localmente**. Origen: resto de la opción B de la [propuesta de la fase 3](../pages/propuesta-fase3.md) (D15). Documentación: sección «PDF del borrador» de `docs/PANEL_ASESOR.md`. Pendiente: integrar en la wiki y fusionar la rama.

- **Puerto y adaptador:** `QuotePdfRenderer` + `QuotePdfDocument` (datos ya formateados, `application/quote_document.py`) y `adapters/pdf/reportlab_renderer.py`. El núcleo no importa la librería; `load_pdf_renderer()` la carga de forma perezosa y la ruta responde 503 si falta.
- **Librería:** ReportLab 5.1.0 (BSD) en los grupos opcionales `pdf` y `pdf-test` (con `pypdf` 6.21.2 para leer el texto en pruebas), frente a fpdf2 2.8.9 (LGPL-3.0). Override de mypy `ignore_missing_imports` para `reportlab.*` (sin stubs).
- **Contenido:** tienda (nuevos campos opcionales de la política: `nombre_comercial`, `nit`, `direccion`, `telefono_tienda`), número `COT-XXXXXXXX` y versión, fecha, líneas, total COP con `Decimal`, entrega, sede, pago, vigencia, IVA según política (pendiente si no está) y la leyenda «Borrador de cotización - no es factura ni reserva de inventario». Sin teléfono del cliente.
- **Ruta:** `GET /panel/quotes/{id}/pdf`: 401 sin sesión, 404 desconocido, 409 si sigue en `DRAFT`, 503 sin la librería, adjunto con `Cache-Control: no-store`. Cambios en `panel.py`: la ruta, tres imports y un enlace «Descargar PDF» en el detalle. Las etiquetas de estado viven en el dominio (`STATUS_LABEL_ES`) para no romper la prueba que impide referenciar los estados humanos fuera del panel.
- **Verificación:** `ruff`, `mypy src evals`, suite completa (366 passed, 1 skipped), offline S01–S22 × 3 = 66 PASS. En un entorno aislado con solo `--group db` las pruebas del PDF que necesitan ReportLab se omiten (2 skipped) y las demás pasan; para ejecutarlas, `--group pdf-test`.

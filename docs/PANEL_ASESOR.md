# Panel web del asesor

Ruta `/panel` de la API de XEON (decisión D15). El asesor revisa los borradores que el cliente
confirmó y las solicitudes de «Hablar con asesor», y toma las decisiones humanas. Es HTML
renderizado en el servidor, sin JavaScript ni recursos externos.

## Qué hace

- **Bandeja** de pendientes y atendidos recientes (`AdvisorInbox`, hoy en memoria; con la
  persistencia PostgreSQL usará el mismo puerto sin cambios).
- **Detalle** de la cotización vigente: líneas, total, entrega, sede, pago, vigencia y, solo para el
  asesor autenticado, el WhatsApp del cliente (en la bandeja aparece enmascarado).
- **Acciones humanas:** *Aprobar para facturación* (`APPROVED_FOR_BILLING`), *Rechazar* con motivo
  obligatorio (`RECHAZADO_POR_ASESOR`) y *Marcar atendido*. Solo se parte de
  `CONFIRMADO_POR_CLIENTE`. El agente, el embudo y el LLM no tienen camino hacia esas transiciones
  (una prueba revisa el código y los mensajes del cliente).
- **Aviso al cliente por Kapso** con una plantilla fija: «un asesor revisó tu cotización… no es una
  factura ni una reserva». El motivo del rechazo no se envía. Si el envío falla (por ejemplo,
  fuera de la ventana de 24 h de WhatsApp) la decisión se conserva y el panel marca «aviso al
  cliente falló».

## Crear la credencial sin exponerla

El panel exige usuario y contraseña. Solo se guarda el hash PBKDF2-SHA256 en
`secrets/advisor_panel_credentials.txt` (ruta configurable con `ADVISOR_PANEL_CREDENTIALS_FILE`, que
debe estar dentro de `secrets/`; Git la ignora). Ejecuta tú mismo, en una terminal:

```powershell
uv run python scripts/create_advisor_credential.py asesor1
```

El script pide la contraseña con entrada oculta (mínimo 12 caracteres), la repite para confirmar,
escribe solo el hash y no imprime nada sensible. Repetirlo con el mismo usuario reemplaza su
contraseña. Sin archivo, el panel responde 503 (falla cerrado). No pegues la contraseña en
mensajes, prompts ni variables de entorno.

## Seguridad

- Sesión en cookie `HttpOnly` y `SameSite=Strict`, con caducidad (`ADVISOR_PANEL_SESSION_MINUTES`,
  480 por defecto). **En producción la cookie `Secure` es obligatoria y, por tanto, también
  HTTPS.** Se activa con `APP_ENV=production`: la API marca entonces las dos cookies del panel
  como `Secure` y el navegador solo las envía por HTTPS. Publica XEON detrás de un proxy inverso
  o túnel que termine TLS (y reenvíe a la API por la red privada); si lo sirves por HTTP con
  `APP_ENV=production`, el inicio de sesión no funcionará. Con `APP_ENV=development` (valor por
  defecto) la cookie no es `Secure`: úsalo solo en local, nunca expuesto a internet.
- CSRF: cada formulario POST lleva un token de la sesión; el inicio de sesión usa un token propio en
  cookie y campo. Un POST sin token válido recibe 403.
- Sin sesión, las rutas responden 401. Tras `ADVISOR_PANEL_MAX_ATTEMPTS` fallos (5) por IP o por
  usuario, el inicio de sesión responde 429 durante `ADVISOR_PANEL_LOCKOUT_MINUTES` (15). El
  tiempo de verificación no revela si el usuario existe.
- Todo el HTML escapa los valores; cabeceras `Content-Security-Policy` (sin scripts, estilos con
  nonce), `X-Content-Type-Options`, `Referrer-Policy: no-referrer` y `Cache-Control: no-store`.
- El teléfono no se escribe en logs (el evento solo registra tenant y tipo) ni en la bandeja.

## PDF del borrador

`GET /panel/quotes/{id}/pdf` (solo con sesión; el detalle de cada evento tiene el enlace «Descargar
PDF») entrega el borrador como adjunto (`Content-Disposition: attachment`, nombre
`cotizacion-COT-XXXXXXXX-vN.pdf`).

- **Respuestas:** 401 sin sesión; 404 si el id no existe o no tiene evento en la bandeja; 409 si el
  borrador sigue en `DRAFT` (el cliente no lo confirmó); 503 si no está instalado el grupo `pdf`.
  Se puede descargar en `CONFIRMADO_POR_CLIENTE`, `APPROVED_FOR_BILLING` y `RECHAZADO_POR_ASESOR`.
- **Contenido:** datos de la tienda (`nombre_comercial`, `nit`, `direccion` y `telefono_tienda` de
  `config/policies/<tenant>.yaml`; si faltan, el tenant), número `COT-XXXXXXXX`, versión, fecha de
  emisión (zona `DEFAULT_TIMEZONE`), estado, líneas con cantidad, precio unitario y subtotal, total en
  pesos (`Decimal`, formato `$1.234.500`), entrega, sede, forma de pago, vigencia en días e IVA según
  la política (pendiente de confirmar con un asesor si no está definido). Lleva la leyenda
  «Borrador de cotización - no es factura ni reserva de inventario» arriba y abajo. **No incluye el
  teléfono del cliente.**
- **Diseño:** el puerto `QuotePdfRenderer` recibe un `QuotePdfDocument` ya formateado
  (`application/quote_document.py`); el adaptador `adapters/pdf/reportlab_renderer.py` solo
  dibuja. El núcleo no importa ReportLab: `load_pdf_renderer()` lo carga de forma perezosa.
- **Librería:** ReportLab 5.1.0 (BSD), grupo opcional `pdf` (`uv sync --locked --group pdf`). Se
  eligió sobre fpdf2 2.8.9 (LGPL-3.0, más pequeña y también de Python puro, pero licencia
  copyleft débil que conviene evitar en un producto comercial). Con las fuentes integradas
  (Helvetica, WinAnsi) las tildes y la «ñ» salen bien sin empaquetar tipografías; depende de
  Pillow. Los bytes son deterministas (`invariant`). Las pruebas que leen el PDF usan `pypdf`
  (grupo `pdf-test`) y se omiten si no está instalado.

## Límites y siguientes pasos

- **Bandeja y sesiones siguen en memoria** hasta fusionar la persistencia (A): un reinicio cierra
  las sesiones y borra los eventos pendientes y los intentos fallidos. Con varios workers cada uno
  tendría su propia sesión.
- Una cuenta compartida por asesor; sin roles. El panel no factura: `APPROVED_FOR_BILLING` solo
  indica que un humano autorizó seguir.
- Probado con dobles HTTP y sin llamadas reales a Kapso; el aviso al cliente no se verificó en el
  sandbox. Ejecútalo detrás de HTTPS (proxy o túnel) antes de exponerlo.

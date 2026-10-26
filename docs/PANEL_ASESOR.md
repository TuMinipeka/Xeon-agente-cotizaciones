# Panel web del asesor

Ruta `/panel` de la API de XEON (decisión D15). El asesor revisa los borradores que el cliente
confirmó y las solicitudes de «Hablar con asesor», y toma las decisiones humanas. Es HTML
renderizado en el servidor, sin JavaScript ni recursos externos.

## Qué hace

- **Bandeja** de pendientes y atendidos recientes (`AdvisorInbox`). Con `STATE_STORE=postgres`,
  los eventos y su estado sobreviven a reinicios; el perfil predeterminado sigue en memoria.
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

## Endurecimiento (revisión de seguridad, 2026-10-26)

- **Tiempo constante:** un usuario inexistente se verifica contra un hash con las mismas
  iteraciones PBKDF2 que uno real, así que el tiempo de respuesta no revela qué usuarios existen.
- **Bloqueo por (IP, usuario) con retardo progresivo:** tras `ADVISOR_PANEL_MAX_ATTEMPTS` fallos el
  par queda bloqueado 30 s, luego 60 s, 120 s… hasta una hora (`Retry-After`). Otra IP no se ve
  afectada, de modo que un extraño no puede dejar fuera al asesor real. Además cada IP tiene un
  tope global de fallos (4 veces el anterior) contra la prueba de muchos usuarios.
- **IP real detrás de un proxy:** declara el proxy en `TRUSTED_PROXIES`; solo desde esas IP se leen
  `X-Forwarded-For` y `X-Forwarded-Proto`. Sin eso todos los clientes comparten la IP del proxy.
- **Solo HTTPS fuera de localhost:** el panel responde 403 a cualquier cliente remoto que no llegue
  por HTTPS (directo o reenviado por un proxy de confianza). Desde loopback (desarrollo) funciona
  por HTTP; las cookies llevan `Secure` siempre que la petición sea HTTPS o `APP_ENV=production`.
- **Contraseña:** máximo 128 caracteres, sin truncar (el script lo comprueba al crearla). Las
  sesiones caducadas y los contadores de fallos se purgan, con topes de memoria.
- **Bandeja:** 50 filas por página (`?page=N`) y como máximo 2.000 eventos en memoria (se descartan
  primero los resueltos y luego las peticiones de asesor más antiguas).

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

- Las sesiones y los intentos fallidos permanecen en cada proceso con caducidad. Solo se retiene
  una huella HMAC del token de sesión; no se guarda el token ni el CSRF en claro. Reiniciar cierra
  las sesiones. Con varios workers, el panel necesita afinidad de sesión para mantener el login;
  las decisiones y la bandeja sí comparten PostgreSQL. La autenticación distribuida queda pendiente.
- Una cuenta compartida por asesor; sin roles. El panel no factura: `APPROVED_FOR_BILLING` solo
  indica que un humano autorizó seguir.
- Probado con dobles HTTP y sin llamadas reales a Kapso; el aviso al cliente no se verificó en el
  sandbox. Ejecútalo detrás de HTTPS (proxy o túnel) antes de exponerlo.

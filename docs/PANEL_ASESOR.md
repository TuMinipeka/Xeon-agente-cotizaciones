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

- Sesión en cookie `HttpOnly` y `SameSite=Strict` (`Secure` cuando `APP_ENV=production`, es decir,
  detrás de HTTPS), con caducidad (`ADVISOR_PANEL_SESSION_MINUTES`, 480 por defecto).
- CSRF: cada formulario POST lleva un token de la sesión; el inicio de sesión usa un token propio en
  cookie y campo. Un POST sin token válido recibe 403.
- Sin sesión, las rutas responden 401. Tras `ADVISOR_PANEL_MAX_ATTEMPTS` fallos (5) por IP o por
  usuario, el inicio de sesión responde 429 durante `ADVISOR_PANEL_LOCKOUT_MINUTES` (15). El
  tiempo de verificación no revela si el usuario existe.
- Todo el HTML escapa los valores; cabeceras `Content-Security-Policy` (sin scripts, estilos con
  nonce), `X-Content-Type-Options`, `Referrer-Policy: no-referrer` y `Cache-Control: no-store`.
- El teléfono no se escribe en logs (el evento solo registra tenant y tipo) ni en la bandeja.

## Límites y siguientes pasos

- **PDF del borrador: fuera de este corte.** Siguiente paso: generarlo desde el borrador
  aprobado (WeasyPrint u otra opción de la [propuesta de la fase 3](../wiki/pages/propuesta-fase3.md)).
- Sesiones, intentos fallidos y la bandeja viven en el proceso: un reinicio cierra las sesiones y,
  hasta fusionar la persistencia (A), pierde los eventos pendientes. Con varios workers cada uno
  tendría su propia sesión.
- Una cuenta compartida por asesor; sin roles. El panel no factura: `APPROVED_FOR_BILLING` solo
  indica que un humano autorizó seguir.
- Probado con dobles HTTP y sin llamadas reales a Kapso; el aviso al cliente no se verificó en el
  sandbox. Ejecútalo detrás de HTTPS (proxy o túnel) antes de exponerlo.

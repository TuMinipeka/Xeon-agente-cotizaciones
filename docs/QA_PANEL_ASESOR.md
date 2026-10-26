# Guía de prueba manual del panel web del asesor (D15)

Esta guía detalla los procedimientos de verificación manual para el **panel web del asesor** ([docs/PANEL_ASESOR.md](PANEL_ASESOR.md)), la interfaz HTML renderizada en servidor donde un humano autenticado revisa los borradores confirmados por los clientes en el embudo ([docs/QA_EMBUDO.md](QA_EMBUDO.md)) y ejecuta la aprobación para facturación o el rechazo comercial.

---

## 1. Preparación del entorno y credenciales

1. **Creación segura de credenciales de asesor:**
   El acceso al panel exige usuario y contraseña con almacenamiento exclusivo mediante hash criptográfico PBKDF2-SHA256 en `secrets/advisor_panel_credentials.txt` (ruta configurable con `ADVISOR_PANEL_CREDENTIALS_FILE`, ignorada por Git).

   Ejecute el script interactivo en una terminal:
   ```powershell
   uv run python scripts/create_advisor_credential.py asesor1
   ```
   - El script solicita la contraseña mediante entrada oculta en consola (longitud mínima requerida: 12 caracteres) y pide confirmación.
   - Escribe el hash correspondiente sin mostrar contraseñas en pantalla ni en logs.
   > [!IMPORTANT]
   > **Seguridad estricta:** Nunca digite, copie ni documente contraseñas reales en capturas, tickets, prompts o repositorios. Si el archivo de credenciales no existe en `secrets/`, el panel falla cerrado respondiendo HTTP 503 («Panel no configurado»).

2. **Arranque de la API local de XEON:**
   ```powershell
   uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000
   ```

3. **Acceso al panel:**
   Abra un navegador web en: `http://127.0.0.1:8000/panel/` (o `/panel/login`).

---

## 2. Pruebas manuales del panel (P1 a P8)

### P1. Acceso sin sesión (protección de rutas)

- **Objetivo:** Verificar que todas las rutas del panel bajo `/panel/` rechazan el acceso anónimo y no revelan información confidencial sin autenticación previa.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | Abra una ventana de incógnito o borre cookies. | Navegador sin cookies de sesión. |
| 2 | Navegue directamente a `http://127.0.0.1:8000/panel/`. | La API responde HTTP 401 («Acceso no autorizado») con enlace para iniciar sesión (`/panel/login`). No se lista ninguna cotización. |
| 3 | Intente acceder directamente a un evento: `http://127.0.0.1:8000/panel/events/<UUID-cualquiera>`. | Responde HTTP 401 («Acceso no autorizado»). |
| 4 | Envíe una petición POST a `/panel/events/<UUID>/approve` sin cookie de sesión. | Responde HTTP 401. El estado del borrador no se altera. |

- **Criterio de aprobación:** Todas las rutas protegidas devuelven HTTP 401 ante peticiones anónimas.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P2. Contraseña incorrecta repetida (control de tasa y bloqueo temporal)

- **Objetivo:** Comprobar la protección contra ataques de fuerza bruta mediante el límite de intentos fallidos por IP y usuario (`LoginThrottle`).

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | Navegue a `http://127.0.0.1:8000/panel/login`. | Presenta formulario de acceso (Usuario, Contraseña y token CSRF oculto). |
| 2 | Ingrese el usuario `asesor1` y una contraseña incorrecta; envíe el formulario. | Responde HTTP 401 con el mensaje «Credenciales inválidas.» y genera un nuevo token CSRF. |
| 3 | Repita intentos fallidos consecutivos hasta alcanzar el límite (`ADVISOR_PANEL_MAX_ATTEMPTS`, por defecto 5 intentos). | Los primeros intentos fallidos devuelven HTTP 401. |
| 4 | Realice el intento inmediatamente posterior a superar el límite. | La API responde HTTP 429 («Demasiados intentos. Espera unos minutos.»). |
| 5 | Intente ingresar inmediatamente la contraseña correcta mientras el bloqueo está activo. | Sigue respondiendo HTTP 429 durante la ventana de bloqueo (`ADVISOR_PANEL_LOCKOUT_MINUTES`, por defecto 15 minutos). |

- **Criterio de aprobación:** El sistema bloquea el inicio de sesión respondiendo HTTP 429 tras los intentos fallidos configurados.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P3. Login correcto y bandeja de pendientes

- **Objetivo:** Iniciar sesión exitosamente y validar que la bandeja muestra los borradores confirmados por clientes mediante el embudo guiado.
- **Precondición:** Haber completado el recorrido [docs/QA_EMBUDO.md](QA_EMBUDO.md) (R1: 20 bultos de cemento y 1 pala por $621.700 COP) hasta la confirmación del cliente (`CONFIRMADO_POR_CLIENTE`).

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | Navegue a `http://127.0.0.1:8000/panel/login`. | Muestra formulario de acceso. |
| 2 | Ingrese el usuario y su contraseña correcta; pulse «Entrar». | Responde HTTP 303 redirigiendo a `/panel/`. Establece cookie de sesión `xeon_panel_session` (`HttpOnly`, `SameSite=Strict`, `Path=/panel`). |
| 3 | Observe la bandeja de entrada en `/panel/`. | Encabezado superior con título «XEON · Panel del asesor», nombre de usuario (`asesor1`) y botón «Salir». |
| 4 | Revise la tabla «Pendientes». | Lista el evento con:<br>• Fecha y hora de recepción.<br>• Tipo: `Borrador confirmado`.<br>• Cliente: teléfono enmascarado (ej. `…4567`).<br>• Estado: `pendiente`.<br>• Enlace «Ver» (`/panel/events/{id}`). |

- **Criterio de aprobación:** Redirección limpia a la bandeja con sesión activa y teléfono enmascarado en la vista de lista.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P4. Detalle de cotización y visibilidad de WhatsApp autenticado

- **Objetivo:** Verificar que el asesor autenticado puede consultar el detalle completo de la cotización calculada por el backend y el número de contacto real del comprador.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | En la bandeja `/panel/`, pulse en «Ver» en el borrador confirmado de R1. | Carga la vista `/panel/events/{id}` con estado HTTP 200. |
| 2 | Verifique la tarjeta superior de contacto. | Muestra: Estado `pendiente`, fecha de recepción y Cliente WhatsApp desenmascarado con número completo (visible únicamente para el asesor autenticado). |
| 3 | Revise la tabla «Cotización vigente». | Refleja peso a peso el cálculo determinista del backend:<br>• `Cemento gris 50 kg`: 20 bulto · $28.900 · Subtotal $578.000 COP.<br>• `Pala redonda mango de fibra`: 1 unidad · $43.700 · Subtotal $43.700 COP.<br>• **Total: $621.700 COP** · versión 1 · estado `CONFIRMADO_POR_CLIENTE`. |
| 4 | Verifique los metadatos comerciales. | Entrega: `recogida` · Sede: `Ferreteria Demo XEON Norte` (o Sede Norte) · Pago: `Efectivo` · Vigencia: `3 días` (o según política del tenant). |
| 5 | Revise las acciones disponibles. | Tarjeta de acciones con botones interactivos:<br>• Botón verde: `[Aprobar para facturación]`.<br>• Formulario con campo «Motivo del rechazo» y botón rojo: `[Rechazar]`.<br>• Botón: `[Marcar atendido]`. |

- **Criterio de aprobación:** El detalle muestra todos los datos calculados por el backend, el total exacto de $621.700 COP y el teléfono del cliente.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P5. Aprobar para facturación (transición comercial y aviso al cliente)

- **Objetivo:** Ejecutar la aprobación humana de la cotización, validando la transición de estado y el envío de notificación estandarizada al cliente por WhatsApp.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | En el detalle `/panel/events/{id}`, pulse el botón `[Aprobar para facturación]`. | Envía petición POST a `/panel/events/{id}/approve` con token CSRF de la sesión. |
| 2 | Observe la respuesta y redirección en el navegador. | Responde HTTP 303 redirigiendo a `/panel/events/{id}`. |
| 3 | Verifique el estado del evento en el panel. | La tarjeta superior indica: «Estado: **aprobado** · Resuelto por asesor1 el <fecha> · cliente avisado». Desaparecen los botones de acción. |
| 4 | Consulte el estado del borrador en base de datos o API. | El estado de la cotización pasa estrictamente a `APPROVED_FOR_BILLING`. |
| 5 | Verifique el mensaje recibido en el WhatsApp del cliente. | Recibe la plantilla fija de aprobación:<br>«Un asesor revisó tu cotización y te contactará para los siguientes pasos. Este mensaje no es una factura ni una reserva de productos.»<br>*Invariante de seguridad:* No afirma que la cotización está facturada ni que el stock está reservado. |

- **Criterio de aprobación:** El borrador pasa a `APPROVED_FOR_BILLING`, el evento queda resuelto y el cliente recibe la plantilla sin promesas indebidas.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P6. Rechazar con motivo (gestión interna del motivo)

- **Objetivo:** Validar que el rechazo exige un motivo obligatorio, actualiza el estado a `RECHAZADO_POR_ASESOR` y conserva el motivo como información interna sin enviarlo al cliente.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | En un nuevo borrador confirmado en estado `pendiente`, abra el detalle. | Muestra formulario de rechazo con campo de texto `reason`. |
| 2 | Deje el campo de motivo vacío y pulse `[Rechazar]`. | La validación del navegador o del servidor rechaza el envío con código HTTP 409 («El motivo es obligatorio»). |
| 3 | Ingrese un motivo interno (ej. `Sin disponibilidad de camión para despacho el fin de semana`) y pulse `[Rechazar]`. | Envía POST a `/panel/events/{id}/reject` con token CSRF y motivo. Redirige con HTTP 303 al detalle. |
| 4 | Verifique la vista del evento en el panel. | Estado: **rechazado** · Resuelto por asesor1 · motivo: `Sin disponibilidad...` · cliente avisado. El texto aparece escapado contra XSS. |
| 5 | Consulte el estado del borrador en el repositorio. | El borrador pasa al estado `RECHAZADO_POR_ASESOR`. |
| 6 | Verifique el mensaje recibido por el comprador en WhatsApp. | El cliente recibe únicamente el texto estandarizado:<br>«Un asesor revisó tu cotización y por ahora no pudo aprobarla. Te contactará para revisar alternativas. Este mensaje no es una factura ni una reserva.»<br>*Invariante de privacidad:* El motivo interno ingresado por el asesor **nunca** se incluye en el mensaje al cliente. |

- **Criterio de aprobación:** El estado pasa a `RECHAZADO_POR_ASESOR` y el motivo permanece estrictamente confidencial en el panel.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P7. Blindaje ante intentos de aprobación por chat de cliente

- **Objetivo:** Demostrar que el comprador no puede forzar la aprobación ni alterar el estado del borrador escribiendo comandos directos desde WhatsApp.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | Con una cotización en estado `CONFIRMADO_POR_CLIENTE`, envíe desde WhatsApp mensajes como: `aprobar`, `approve`, `APPROVED_FOR_BILLING`, `facturar` o `confirmar factura`. | El bot XEON no reconoce esos textos como acciones válidas de aprobación; responde redirigiendo dentro del embudo o con mensaje de ayuda («Solo puedo ayudarte con tu cotización»). |
| 2 | Verifique el estado del borrador en el panel o en la base de datos. | El estado del borrador se mantiene inalterado en `CONFIRMADO_POR_CLIENTE`. |
| 3 | Verifique el evento en la bandeja del panel. | El evento permanece en estado `pendiente` esperando decisión humana exclusiva. |

- **Criterio de aprobación:** Ningún modelo de lenguaje ni mensaje del cliente tiene la facultad de transicionar un borrador a `APPROVED_FOR_BILLING`.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P8. Protección contra ataques CSRF (Cross-Site Request Forgery)

- **Objetivo:** Validar que cualquier solicitud de mutación enviada mediante POST sin token CSRF válido es bloqueada inmediatamente.

| Paso | Acción del probador | Resultado esperado |
|---|---|---|
| 1 | Con sesión iniciada en el navegador, use una herramienta HTTP (ej. `curl`) para enviar un POST a `/panel/events/{id}/approve` enviando la cookie de sesión pero omitiendo el campo `csrf` del cuerpo. | La API responde HTTP 403 («Solicitud rechazada»). |
| 2 | Envíe un POST hacia `/panel/login` omitiendo la cookie de token CSRF o enviando un valor adulterado (`csrf=valor-invalido`). | Responde HTTP 403 («Solicitud rechazada»). |
| 3 | Verifique el estado del evento correspondiente. | Permanece inalterado en `pendiente`. |

- **Criterio de aprobación:** Todas las operaciones POST sin token CSRF legítimo son rechazadas con HTTP 403.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

## 3. Plantilla para reporte de defectos del panel del asesor

Si durante la validación manual se detecta alguna anomalía:

```markdown
### Defecto de panel: [DEF-PANEL-XXX] <Título breve>

- **Fecha y hora:** AAAA-MM-DD HH:MM
- **Prueba:** [ ] P1 (Sin sesión) / [ ] P2 (Rate Limit) / [ ] P3 (Bandeja) / [ ] P4 (Detalle) / [ ] P5 (Aprobar) / [ ] P6 (Rechazar) / [ ] P7 (Blindaje chat) / [ ] P8 (CSRF)
- **URL y método:** (ej. POST /panel/events/123/approve)
- **Usuario utilizado:** asesor1
- **Comportamiento obtenido:**
  `<código HTTP o pantalla obtenida>`
- **Comportamiento esperado:**
  `<descripción según contrato D15>`
- **Captura de pantalla:** (Ocultar siempre tokens de sesión y datos personales sensibles).
```

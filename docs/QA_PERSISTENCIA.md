# Guía de verificación manual de la persistencia operativa (D15 A)

Esta guía describe los procedimientos de control de calidad manual para validar la **persistencia operativa de XEON** ([PERSISTENCIA.md](PERSISTENCIA.md)) en PostgreSQL 17 propio (decisión [D15 A](../wiki/pages/decisiones-pendientes.md)), cubriendo la resiliencia del embudo guiado, la deduplicación de webhooks y el aislamiento entre inquilinos.

---

## 1. Preparación del entorno de persistencia

Para ejecutar las pruebas manuales contra el almacén relacional de estado:

1. **Iniciar el contenedor de base de datos de estado:**
   Levante la instancia local de PostgreSQL 17 configurada exclusivamente para el estado de XEON:
   ```powershell
   docker compose -f compose.state.yaml up -d --wait
   ```
   *Nota:* Este servicio opera de forma independiente al conector de solo lectura de ferreterías (`compose.db-test.yaml`). Utiliza el puerto local `55433` y el volumen persistente `xeon_state_data`.

2. **Configuración segura de credenciales (sin exposición de secretos):**
   Cree el archivo secreto en la ruta ignorada por Git:
   - Ruta: `secrets/xeon_state_url.txt`
   - Contenido: URL de conexión `postgresql+psycopg://...` hacia la base `xeon_state` en el puerto `55433`.
   > [!IMPORTANT]
   > **Seguridad:** Nunca imprima, copie ni versiona la URL de conexión ni sus contraseñas en terminales públicas, logs, prompts o commits. XEON lee este valor en tiempo de ejecución mediante la variable `XEON_STATE_URL_FILE` (que apunta por defecto a `secrets/xeon_state_url.txt`).

3. **Ejecutar migraciones del esquema de base de datos:**
   Sincronice las dependencias del grupo de base de datos y aplique las revisiones de Alembic:
   ```powershell
   uv sync --locked --group db
   uv run --locked --group db alembic upgrade head
   ```

4. **Activar el almacén en el entorno del proceso:**
   Configure la variable de entorno para que XEON utilice la base relacional en lugar del almacenamiento en memoria:
   ```powershell
   $env:STATE_STORE = "postgres"
   ```
   *(Para regresar al comportamiento sin base de datos, use `$env:STATE_STORE = "memory"`).*

5. **Detención del entorno al finalizar:**
   ```powershell
   docker compose -f compose.state.yaml down
   ```
   *(Evite usar `down -v` salvo que desee destruir intencionalmente el volumen y todo el historial de pruebas).*

---

## 2. Pruebas manuales de persistencia (P1 a P4)

### P1. Reinicio a mitad del embudo (resiliencia del carrito y paso conversacional)

- **Objetivo:** Verificar que si la API o el proceso de XEON se reinicia mientras un cliente está en medio del embudo guiado, el paso actual, las opciones pendientes y los productos agregados al carrito se conservan sin reiniciar la conversación.
- **Precondición:** `STATE_STORE=postgres` activo y API iniciada (`uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`).

| Paso | Acción del probador | Comportamiento esperado de XEON |
|---|---|---|
| 1 | Inicia conversación o pulsa botón inicial | Presenta opciones iniciales (`inicio`). |
| 2 | Pulsa `[Cotizar productos]` y escribe `cemento` | Retorna lista interactiva con `Cemento gris 50 kg` (`CEM-50`). |
| 3 | Selecciona `Cemento gris 50 kg` y pulsa botón `[20]` | Registra la línea en el carrito (20 bultos x $28.900 = **$578.000 COP**) y avanza al paso `mas` («¿Algo más para tu cotización?»). |
| 4 | **Simular caída del servidor:** Detenga el proceso de la API en la terminal (`Ctrl+C`). | El proceso se apaga. Los datos quedan persistidos en las tablas `funnel_states` y `cart_states` de PostgreSQL. |
| 5 | **Reiniciar la API:** Ejecute nuevamente `uv run uvicorn xeon.api.app:app --host 127.0.0.1 --port 8000`. | La API inicia con conexión activa a PostgreSQL. |
| 6 | Desde el mismo chat o número de teléfono, envíe el siguiente turno pulsando `[Ver cotizacion]` | XEON recupera el contexto desde PostgreSQL: reconoce que estaba en el paso `mas`, avanza correctamente a `entrega` («¿Cómo lo recibes?») y conserva intacto el carrito con los 20 bultos por **$578.000 COP**. |

- **Criterio de aprobación:** El sistema no reinicia el flujo a «¿Qué necesitas?», no pierde los 20 bultos de cemento y retoma la conversación en el punto exacto.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P2. Webhook duplicado (deduplicación transaccional e idempotencia)

- **Objetivo:** Garantizar que si Kapso o la red envían dos veces el mismo webhook con idéntico `message.id` (o si dos workers concurrentes procesan la misma entrega), se registre una sola reclamación y se genere una única mutación de borrador.
- **Precondición:** `STATE_STORE=postgres` activo.

| Paso | Acción del probador | Comportamiento esperado de XEON |
|---|---|---|
| 1 | Envíe un webhook firmado de WhatsApp con un `message.id` único (ej. `wamid.test.001`) conteniendo una selección (ej. cantidad `10`). | La API responde HTTP 200 `{"status": "processed"}`. Se crea el borrador y se envía la respuesta saliente. |
| 2 | Envíe inmediatamente un segundo webhook con exactamente el mismo `message.id` (`wamid.test.001`) y el mismo payload. | La API responde HTTP 200 `{"status": "processed"}`. |
| 3 | Inspeccione la base de datos PostgreSQL local:<br>`SELECT count(*) FROM processed_events WHERE message_id = 'wamid.test.001';`<br>`SELECT count(*) FROM quote_drafts;` | • `processed_events`: contiene exactamente 1 registro para la tupla `(tenant_id, instance, message_id)`.<br>• `quote_drafts`: se conserva un único borrador sin duplicación de líneas ni doble facturación. |

- **Criterio de aprobación:** Cero duplicaciones en base de datos; la restricción transaccional descarta el segundo evento sin generar efectos secundarios ni mensajes repetidos al cliente.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P3. Confirmación y reinicio (durabilidad del estado comercial)

- **Objetivo:** Verificar que una vez que el cliente confirma la cotización, el estado comercial `CONFIRMADO_POR_CLIENTE` permanece inalterado tras reiniciar la aplicación.
- **Precondición:** `STATE_STORE=postgres` activo.

| Paso | Acción del probador | Comportamiento esperado de XEON |
|---|---|---|
| 1 | Complete un flujo de cotización guiado (R1) hasta el paso `resumen` (ej. 20 cementos, total $578.000 COP). | Muestra resumen con botones `[Confirmar]`, `[Modificar]`, `[Cancelar]`. |
| 2 | Pulsa `[Confirmar]` | Responde: «Recibimos tu confirmación. Un asesor revisará y te contactará.» El borrador pasa al estado `CONFIRMADO_POR_CLIENTE`. |
| 3 | Detenga la API de XEON (`Ctrl+C`) y vuelva a iniciarla. | La API reinicia limpiamente. |
| 4 | Consulte el borrador en la base de datos o mediante el subcomando del CLI (`uv run xeon quotes show <UUID>`). | El borrador existe, conserva el monto total exacto ($578.000 COP) y su estado es persistentemente `CONFIRMADO_POR_CLIENTE` (nunca vuelve a `DRAFT` ni se eleva a `APPROVED_FOR_BILLING`). |

- **Criterio de aprobación:** El estado `CONFIRMADO_POR_CLIENTE` sobrevive al reinicio completo del proceso y no se altera sin intervención humana autorizada.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

### P4. Aislamiento estricto de tenant (particionamiento multi-inquilino)

- **Objetivo:** Comprobar que los estados de conversación, carritos y cotizaciones pertenecientes a un inquilino (`tenant_id`) no son accesibles ni interfieren con los de otro inquilino, incluso si comparten la misma clave de conversación o número de teléfono.
- **Precondición:** `STATE_STORE=postgres` activo.

| Paso | Acción del probador | Comportamiento esperado de XEON |
|---|---|---|
| 1 | En el inquilino A (`tenant_id: "demo"`), inicie conversación y agregue 10 bultos de cemento. | El carrito del inquilino A contiene 10 bultos y el paso del embudo es `mas`. |
| 2 | Envíe una solicitud con el mismo identificador de conversación (`conversation_key: "cliente-prueba"`), pero configurando el inquilino B (`tenant_id: "ferreteria_b"`). | El inquilino B inicia en el paso `inicio`, con carrito vacío. |
| 3 | Avance en el inquilino B agregando una referencia diferente (ej. alambre). | Los carritos y estados de ambos inquilinos coexisten de forma independiente. |
| 4 | Verifique en PostgreSQL las tablas `cart_states`, `funnel_states` y `quote_drafts`. | Carrito y embudo usan una clave de conversación prefijada por tenant; `quote_drafts` tiene columna `tenant_id`. Ninguna consulta del inquilino B debe recuperar datos del inquilino A. |

- **Criterio de aprobación:** El repositorio devuelve solo datos del tenant configurado, tanto por clave de conversación prefijada como por filtro `tenant_id` en borradores.
- **Resultado:** `[ ] PASS    [ ] FAIL`

---

## 3. Límites conocidos y consideraciones de arquitectura

Los siguientes límites corresponden al diseño implementado en [PERSISTENCIA.md](PERSISTENCIA.md) y deben ser considerados durante la evaluación:

1. **Retención de datos: POR DEFINIR por el usuario:**
   Actualmente no existe una tarea de limpieza automática de conversaciones o carritos abandonados ni un plazo de expiración inferido. La política de retención, purga de datos históricos y archivado debe ser definida por el producto.
2. **Sin outbox transaccional de envío:**
   El adaptador de mensajería (Kapso) se invoca antes de ejecutar el commit de la transacción en PostgreSQL para permitir el rollback ante fallos del canal. Si ocurre una caída del servidor entre la aceptación remota del mensaje por Meta/Kapso y el commit local, un reintento del webhook podría provocar un reenvío. La entrega *exactly-once* ante fallos de proceso requerirá idempotencia de salida o una cola de outbox dedicada.
3. **Sin cola durable de mensajería:**
   La respuesta HTTP 200 `{"status": "processed"}` del webhook certifica que el evento fue recibido y programado para procesamiento transaccional, pero no constituye una confirmación de entrega en el dispositivo del cliente.
4. **Evolución y migración de esquemas JSONB:**
   Los estados de carrito, embudo y memoria se almacenan como `JSONB` estructurado con metadatos explícitos (`schema_version=1`). Cualquier cambio futuro en los modelos de dominio requerirá scripts de migración sobre los documentos existentes antes de desplegar nuevas versiones del código.
5. **Privacidad y datos personales (PII):**
   La memoria conversacional persiste texto libre del comprador, números de contacto y direcciones físicas registradas durante el paso de entrega a domicilio. El acceso a la base de datos, respaldos y volúmenes debe estar protegido y restringido en producción.

---

## 4. Plantilla para reporte de defectos de persistencia

Si se identifica un fallo de consistencia, pérdida de estado o error transaccional:

```markdown
### Defecto de persistencia: [DEF-STATE-XXX] <Título breve>

- **Fecha y hora:** AAAA-MM-DD HH:MM
- **Prueba:** [ ] P1 (Reinicio) / [ ] P2 (Deduplicación) / [ ] P3 (Confirmación) / [ ] P4 (Aislamiento)
- **Instancia / Tenant:** (ej. tenant_id: demo, puerto: 55433)
- **Mensaje o evento enviado:**
  `<payload o acción ejecutada>`
- **Estado esperado en PostgreSQL:**
  `<descripción de las filas esperadas en tablas>`
- **Estado obtenido en PostgreSQL:**
  `<resultado de las consultas SQL o logs de error>`
- **Evidencia / Log:** (Adjuntar traza de PostgreSQL o Uvicorn sin exponer credenciales reales).
```

# Persistencia operativa de XEON (D15 A)

XEON puede guardar el embudo, carrito, memoria conversacional, borradores, bandeja del asesor y los IDs de webhooks procesados en un PostgreSQL **propio de XEON**. Es independiente del `DATA_SOURCE=sql` de la ferretería: ese conector conserva sus consultas de solo lectura y su propio archivo de URL. El valor por defecto `STATE_STORE=memory` mantiene las pruebas sin red.

## Desarrollo local en cuatro pasos

1. Iniciar PostgreSQL 17 local: `docker compose -f compose.state.yaml up -d --wait`. El compose usa credenciales visibles **solo para desarrollo**, puerto local `55433` y volumen `xeon_state_data`. No usar estas credenciales en producción.
2. Crear `secrets/xeon_state_url.txt` (ignorado por Git) con la URL `postgresql+psycopg://xeon_dev:xeon-local-only@127.0.0.1:55433/xeon_state`. El archivo se lee en ejecución; no colocar la URL en YAML, variables de log ni `alembic.ini`.
3. Ejecutar `uv sync --locked --group db` y `uv run --locked --group db alembic upgrade head`. Alembic lee `XEON_STATE_URL_FILE`, cuyo valor predeterminado es `secrets/xeon_state_url.txt`.
4. Configurar `STATE_STORE=postgres` en el entorno del proceso XEON. `DATA_SOURCE` se configura por separado (`synthetic` o `sql`).

Para volver a memoria, usar `STATE_STORE=memory`. Para detener el servicio local: `docker compose -f compose.state.yaml down`. `down -v` **elimina el volumen y todo el estado local**; usarlo únicamente en una base de pruebas desechable. Probar la reversión de esquema con `uv run --locked --group db alembic downgrade base` en una base desechable y volver a `upgrade head`.

## Garantías y límites

- Una transacción PostgreSQL y `pg_advisory_xact_lock` por clave de conversación serializan pasos del embudo en distintos workers. En ella se guardan embudo, carrito, memoria y borrador. El carrito además compara su versión y rechaza una escritura obsoleta.
- `processed_events` tiene clave primaria `(tenant_id, instance, message_id)`. El webhook toma la reclamación dentro de esa transacción, junto con la respuesta. Dos workers con el mismo ID generan un solo envío y un solo borrador. El repositorio de borradores tiene la restricción única `(tenant_id, request_id)`.
- La migración `0002_advisor_inbox` añade eventos del asesor con separación por tenant y deduplicación de pendientes. Una revisión humana bloquea el evento y el borrador en la misma transacción: dos asesores compitiendo por aprobar o rechazar reciben un éxito y un conflicto. Los borradores también se leen por tenant.
- Las sesiones del panel conservan solo la huella HMAC del token en memoria, con expiración. Reiniciar invalida los inicios de sesión y un despliegue con varios workers necesita afinidad para el panel; la bandeja y sus decisiones sí son compartidas. Esta elección evita persistir credenciales de sesión. La autenticación distribuida queda fuera del corte.
- El canal se llama antes del commit para poder revertir el estado ante un error explícito. Una caída entre la aceptación remota del mensaje y el commit puede causar reenvío al reintentar; la entrega exactamente una vez ante fallos de proceso requiere idempotencia confirmada por Kapso o un outbox de envío. El acuse `processed` del webhook no confirma entrega al teléfono.
- Los payloads de estado son `JSONB` con `schema_version=1` y serializadores explícitos. Un despliegue futuro que cambie su estructura debe migrar los datos antes de cambiar el lector. La memoria incluye texto del cliente y la dirección; proteger la base, el volumen, copias de seguridad y accesos de producción.
- **Retención de datos: POR DEFINIR por el usuario.** No hay limpieza automática ni plazo inferido. También quedan por definir cifrado en reposo, copias de seguridad y recuperación en producción.

## Verificación

La suite normal no necesita PostgreSQL. Para integración local, levantar además `docker compose -f compose.db-test.yaml up -d --wait` (conector D13), ejecutar `uv run --locked --group db --group db-test pytest -m integration` y apagar ambos servicios al terminar. `tests/integration/test_state_postgres.py` verifica reinicio, dos instancias y carrera del carrito; `tests/integration/test_sql_engines.py` comprueba el conector de ferretería por separado. Ninguna prueba invoca un LLM pagado.

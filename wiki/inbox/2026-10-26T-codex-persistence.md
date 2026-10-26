---
tags:
  - xeon/estado
---

# D15 A: persistencia operativa de XEON

Fecha: 2026-10-26. Aporte: Codex en `feat/state-persistence`, worktree `xa`. Estado: implementado y probado localmente; pendiente de integración en páginas compartidas. Fuente: decisión D15 del usuario, [propuesta fase 3 A](../pages/propuesta-fase3.md), [guía](../../docs/PERSISTENCIA.md), código y pruebas del worktree.

Commits: `f234e89` (persistencia y regresiones), `60a0974` (recorridos SQL guiados). No se hizo push.

## Diseño y archivos

- `STATE_STORE=memory|postgres` conserva memoria como valor predeterminado. La URL de escritura de PostgreSQL 17 se lee solo de `XEON_STATE_URL_FILE` dentro de `secrets/`; es distinta de `SQL_URL_FILE` del conector D13. Dependencias `alembic==1.20.1`, SQLAlchemy 2 y psycopg 3 en grupo opcional `db`, fijadas en `uv.lock`. Con memoria, el núcleo no importa SQLAlchemy.
- `src/xeon/adapters/persistence/postgres/` implementa embudo, carrito, memoria conversacional, borradores y deduplicación de webhooks con SQLAlchemy Core y JSONB versionado. `src/xeon/application/ports/state_store.py` expresa la transacción y reclamación de eventos; `GuidedFunnel` entra a una transacción serializada por conversación. Claves de conversación separadas por tenant. El carrito rechaza escrituras con versión obsoleta.
- `migrations/versions/0001_operational_state.py` y `alembic.ini` gestionan cinco tablas y la unicidad `(tenant_id, request_id)` de borradores y `(tenant_id, instance, message_id)` de eventos. `compose.state.yaml` es un servicio local con volumen y credenciales solo de desarrollo. `docs/PERSISTENCIA.md` documenta configuración, migraciones, pruebas y límites; `docs/ARCHITECTURE.md` y `docs/XeonContexto.md` distinguen esta base propia del futuro índice híbrido comercial.
- `tests/test_state_codec.py` prueba serialización exacta de dinero, estado y respuesta y rechazo de URL fuera de `secrets/`, sin red. `tests/integration/test_state_postgres.py` prueba continuidad tras recrear el contenedor, dos workers con el mismo webhook (un envío, un borrador), carrera de carrito y aislamiento de tenant. `tests/integration/test_sql_engines.py` migró tres recorridos anteriores de texto libre al embudo; conserva precio real, stock y manejo de fecha sin zona. Para un tenant sin política de entrega/pago, usa las opciones `delivery:branch_inquiry` y `payment:pending` sin inventar términos.

## Comandos y evidencia

`uv sync --locked`; `docker compose -f compose.state.yaml up -d --wait`; archivo local `secrets/xeon_state_url.txt`; `uv run --locked --group db alembic upgrade head`; `uv run --locked --group db alembic downgrade base`; `uv run --locked --group db alembic upgrade head`; `docker compose -f compose.db-test.yaml up -d --wait`; `uv run --locked --group db --group db-test --group evals ruff check .`; `ruff format --check .`; `mypy src evals`; `pytest -q`; `pytest -m integration -q`; `python -m evals.runner --mode offline`.

Verificado: migración ida/vuelta hasta `0001_operational_state (head)`, pruebas de integración 14/14, ruff, formato, mypy y pytest normal verdes; evaluación offline S01–S22: 66 PASS, 0 FAIL, 0 ERROR. LLM pagado: 0 llamadas. En una primera corrida de integración fallaron tres pruebas del conector SQL porque invocaban el flujo libre anterior a D14; se migraron al recorrido guiado sin alterar sus criterios de negocio y la corrida posterior pasó.

El grafo local se regeneró mediante `uv run --locked --group graph python scripts/build_graphify_map.py`: 2534 nodos, 7795 aristas, 155 comunidades, 290 archivos, 0 llamadas LLM y 0 rutas o valores excluidos detectados. Los hubs versionados de `wiki/graph/` se restauraron después de la generación para evitar cambios de nombres de nodos dependientes del worktree; el grafo local ignorado permanece disponible. `scripts/check_doc_links.py`: 51 enlaces relativos revisados, 0 rotos.

## Límites y siguiente paso

- **Retención: POR DEFINIR por el usuario.** No se implementó TTL, limpieza automática, cifrado en reposo ni backup de producción. La dirección y texto de conversación persistidos exigen acceso restringido a la base.
- La transacción mantiene el bloqueo mientras se invoca Kapso. El caso de caída después de que Kapso acepte el envío y antes del commit aún puede duplicar el envío al reintentar; para garantía ante fallos de proceso se requiere idempotencia comprobada del proveedor o outbox de envío. El acuse del webhook no confirma entrega al teléfono.
- La API programa webhooks en tareas de fondo locales. Una caída entre el acuse HTTP y la ejecución no tiene cola durable; es el siguiente corte operativo. No se hicieron envíos reales a Kapso.
- Un cambio futuro de estructura de JSONB debe migrar `schema_version=1` antes de desplegar el nuevo lector. La persistencia D15 A no implementa el índice RAG D12 ni aprobación humana.

Páginas afectadas para futura integración de wiki: `arquitectura-actual`, `estado-del-corte`, `conector-ferreteria`, `propuesta-fase3`.

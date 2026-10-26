---
tags:
  - xeon/operacion
---

# Conector SQL contra PostgreSQL y MySQL reales (Sonnet, 2026-10-26)

Estado: **verificado** con contenedores desechables. Docker 29.8.0. Se ejecutó `tests/integration/test_sql_engines.py`: **9 passed** (PostgreSQL 17.6 y MySQL 8.4.6). Suite normal: 310 passed, 9 deselected; `ruff`, `ruff format --check` y `mypy src evals` en verde. Contenedores retirados con `docker compose -f compose.db-test.yaml down -v`. Documentación: `docs/CONECTOR_FERRETERIA.md`. Páginas a actualizar por el orquestador: [conector de la ferretería](../pages/conector-ferreteria.md) (límite «solo SQLite») y [estado del corte](../pages/estado-del-corte.md).

## Resultados por motor

| Prueba | PostgreSQL 17.6 | MySQL 8.4.6 |
|---|---|---|
| Cotiza con precios de la base (2 × $37.550 = $75.100), sede resuelta por alias | pasa | pasa (con fechas en UTC con sufijo, ver H1) |
| `LIMIT :limit` y parámetros enlazados; `' OR 1=1 --` no devuelve nada; precio `Decimal` | pasa | pasa |
| Usuario de solo lectura no puede `INSERT` ni `UPDATE` aun con consulta que salta `ReadQuery` | pasa (permiso denegado) | pasa (permiso denegado) |
| Transacción de solo lectura del conector incluso con cuenta de escritura | pasa («read-only transaction») | no aplica: el conector no la activa |
| YAML con DML rechazado al cargar | pasa | pasa |

## Hallazgos en `src/` (no corregidos; Codex edita src)

- **H1 (real, MySQL): `DATETIME` sin zona deja el stock «pendiente».** Reproducción: con `compose.db-test.yaml` arriba y `connectors/example-ferreteria.yaml`, `SqlBranchInventory(SqlReader("mysql+pymysql://tienda_ro:solo-prueba-lectura@127.0.0.1:53450/tienda", timeout_seconds=5), cfg).list_snapshots("FER-01")` lanza `InvalidInventoryError: observed_at debe incluir zona horaria UTC` porque pymysql devuelve `datetime.datetime(2026, 10, 26, 17, 21, 9)` sin `tzinfo` y `inventory/sql.py` aplica `str(...)`. En el chat, la respuesta es «Inventario pendiente de confirmación con un asesor» (falla segura). Es el comportamiento documentado, pero MySQL no tiene tipo con zona. Opciones: formatear en el YAML (`DATE_FORMAT(..., '%Y-%m-%dT%H:%i:%s+00:00')`, documentado y probado) o que el adaptador trate `datetime` naive como UTC bajo un campo opcional del conector (decisión del orquestador).
- **H2 (límite documentado): MySQL no tiene solo lectura a nivel de conexión.** `SqlReader` activa `query_only` en SQLite y `SET TRANSACTION READ ONLY` en PostgreSQL, nada en MySQL. Con una cuenta de escritura, una consulta forjada (sin pasar por `ReadQuery`) podría escribir; la barrera es el usuario con solo `SELECT`, probado. Posible mejora: `SET SESSION TRANSACTION READ ONLY` en el evento `begin` de MySQL.
- Sin hallazgos en `LIMIT`, parámetros, `Decimal` ni `BIGINT`/`NUMERIC`/`DECIMAL`.

## Cómo repetir

```powershell
docker compose -f compose.db-test.yaml up -d --wait
uv run --locked --group db-test pytest -m integration tests/integration
docker compose -f compose.db-test.yaml down -v
```

Nota: el puerto MySQL es 53450 porque Windows reserva 53232–53331 en esta máquina.

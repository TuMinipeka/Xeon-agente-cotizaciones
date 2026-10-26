# Conectar una ferretería a XEON

Estado: conector SQL de solo lectura implementado. Cada empresa aporta su esquema y sus consultas; XEON conserva los contratos canónicos de producto, inventario y sede. El carrito y los borradores siguen en memoria.

## Cuatro pasos

1. Instalar el grupo opcional: `uv sync --locked --group db`. Instalar aparte el driver del motor: `uv pip install psycopg` (PostgreSQL), `uv pip install pymysql` (MySQL) o `uv pip install pyodbc` (SQL Server). SQLite no requiere driver adicional.
2. Crear un usuario de base de datos con **solo SELECT** en las tablas o vistas necesarias. Limitarlo a una base y a un esquema; configurar timeout también en el servidor. El conector usa consultas SELECT parametrizadas, pero los permisos de la base son la barrera definitiva.
3. Copiar `connectors/example-ferreteria.yaml` a `connectors/<tenant>.yaml` y adaptar las cuatro consultas, mapeos de columnas, `price_divisor` y `unit_map`. Las consultas reciben `:sku` o `:query` como parámetros enlazados. `search_text` recibe `%texto%`, apto para `LIKE`; ajustar la expresión SQL al dialecto. `price_divisor: 100` transforma centavos en unidad monetaria. Alias separados por `|`.
4. Guardar solo la URL en `secrets/store_database_url.txt`; configurar `DATA_SOURCE=sql`, `TENANT_ID=<tenant>`, `CURRENCY=COP`, `SQL_URL_FILE=secrets/store_database_url.txt` y arrancar XEON. Opcional: `CONNECTOR_ROOT` cambia el directorio YAML. Nunca poner URL ni contraseña en YAML, logs o Git.

Ejemplos de URL **sin credenciales reales**:

| Motor | URL ilustrativa | Driver |
|---|---|---|
| PostgreSQL | `postgresql+psycopg://USUARIO:CLAVE@HOST/BASE` | `psycopg` |
| MySQL | `mysql+pymysql://USUARIO:CLAVE@HOST/BASE` | `pymysql` |
| SQL Server | `mssql+pyodbc://USUARIO:CLAVE@HOST/BASE?driver=ODBC+Driver+18+for+SQL+Server` | `pyodbc` y controlador ODBC del sistema |

Las cuatro consultas son `find_by_sku`, `search_text`, `stock_by_sku` y `list_branches`. Cada una declara `sql` y `columns`, un mapa de nombre canónico a nombre de columna resultante. `search_text` también recibe `:limit`: úsalo en `LIMIT`, `TOP` o `FETCH NEXT` según el motor. El catálogo exige `sku`, `name`, `unit`, `price`; inventario exige `branch_id`, `quantity` y puede aportar `branch_name`, `observed_at`, `valid_until`; sedes exigen `id`, `name` y admiten `aliases`. La omisión de `valid_until` deja el stock pendiente de confirmación. Las fechas observadas deben incluir zona horaria UTC. La moneda proviene de Settings, no de la base.

La configuración rechaza consultas que no comiencen con un único SELECT, punto y coma, comentarios y palabras de DML/DDL. Los valores del usuario pasan por parámetros enlazados. El conector activa `query_only` en SQLite y transacciones de solo lectura en PostgreSQL. MySQL y SQL Server dependen de permisos de usuario para la protección de escritura. El timeout de PostgreSQL limita la sentencia; en SQLite `busy_timeout` limita espera por bloqueo. En otros motores se requiere timeout del servidor o driver. El catálogo hace búsqueda lexical con `LIKE` y no indexa datos de clientes.

`DATA_SOURCE=synthetic` sigue siendo el valor por defecto. `rest` y `csv` están reservados y fallan de forma explícita. No hay migración automática de esquemas, escritura SQL, persistencia de carrito ni índice híbrido en esta fase.

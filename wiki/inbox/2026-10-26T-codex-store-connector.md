---
tags:
  - xeon/operacion
---

# Fase 2: conector declarativo de ferretería

Fecha: 2026-10-26. Aportó: Codex, a partir de la tarea del orquestador y la decisión D13. Estado: **implementado y verificado localmente** en `feat/store-connector`; pendiente integración por el orquestador. Páginas relacionadas: [conector](../pages/conector-ferreteria.md), [arquitectura](../pages/arquitectura-actual.md), [contratos](../pages/contratos-herramientas.md).

## Diseño y archivos

- `BranchDirectory` expone id, nombre y alias. `IntentInterpreter` resuelve sedes contra el directorio; el ejecutor usa el id verificado para stock. `InMemoryBranchDirectory` conserva los datos sintéticos y alimenta la generación de inventario sintético.
- `DATA_SOURCE=synthetic|sql|rest|csv`; `synthetic` sigue predeterminado. `rest` y `csv` fallan explícitamente. `TENANT_ID` y `CURRENCY` vienen de Settings. El dominio no importa SQLAlchemy. La nota sintética de cotización vive ahora en el adaptador sintético; el dominio usa nota neutral. La priorización de referencias sintéticas queda en el catálogo en memoria.
- `src/xeon/connectors/schema.py` valida `connectors/<tenant>.yaml` con Pydantic: un único SELECT, sin comentarios, punto y coma ni palabras DML/DDL; mapeos canónicos obligatorios; `:sku`, `:query` y `:limit` exigidos según consulta.
- `src/xeon/adapters/sql/connection.py` usa SQLAlchemy 2 Core con parámetros enlazados y oculta parámetros en errores. SQLite activa `query_only`; PostgreSQL marca transacciones de solo lectura. `src/xeon/adapters/catalog/sql.py`, `inventory/sql.py` y `branches/sql.py` leen catálogo, stock y sedes. La URL se obtiene exclusivamente del archivo `SQL_URL_FILE` bajo `secrets/`.
- `pyproject.toml` y `uv.lock` añaden SQLAlchemy 2.1.6 en el grupo opcional `db`; no se importa en el arranque sintético. Drivers externos documentados en [guía](../../docs/CONECTOR_FERRETERIA.md): psycopg, pymysql y pyodbc.
- Nuevos: `src/xeon/domain/branch.py`, puerto `src/xeon/application/ports/branches.py`, adaptadores de sedes, SQL y `connectors/example-ferreteria.yaml`; documentación `docs/CONECTOR_FERRETERIA.md`; regresiones `tests/test_sql_connector.py`. Modificados: configuración, contenedor, intérprete, ejecutor, inventario sintético, cotización y pruebas de contrato antiguas. `evals/checks/core.py` solo recibió formato para pasar el gate.

## Verificación

Comandos ejecutados dentro de `C:\Users\danie\Documents\xeon-connector`:

```powershell
uv sync --locked
uv lock
uv sync --locked --group db --group evals
uv run --locked --group db --group graph --group evals ruff check .
uv run --locked --group db --group graph --group evals ruff format --check .
uv run --locked --group db --group graph --group evals mypy src evals
uv run --locked --group db --group graph --group evals pytest -q
uv run --locked --group db --group graph --group evals python -m evals.runner --mode offline
uv run --locked --group db --group graph --group evals python scripts/check_doc_links.py
uv run --locked --group graph --group db python scripts/build_graphify_map.py
```

- Suite completa: verde; 294 pruebas recolectadas. Tras exigir `:limit`, las 11 pruebas focalizadas SQL volvieron a pasar. `ruff`, formato y `mypy`: verdes; enlaces relativos: 42 revisados, 0 rotos.
- Evaluador offline: **60 PASS, 0 FAIL, 0 ERROR** (S01–S20, tres repeticiones); usa MockLLM. Costo real de modelos: **0**. Graphify: extracción AST local, **0 llamadas LLM**; 1984 nodos, 5951 aristas, 119 comunidades, 238 archivos cubiertos; 0 rutas excluidas ni valores con aspecto de clave en la salida. El artefacto generado queda ignorado por Git.
- SQLite temporal usa `articulos`, `sucursales` y `existencias`, con columnas no canónicas, precio como texto en centavos, stock por bodega y alias de sede. El servicio conversacional cotizó 2 bultos a 37.550 COP cada uno, total 75.100 COP, y consultó disponibilidad en la sede `BOD-7`. Pruebas rechazaron INSERT, UPDATE, DROP, consultas múltiples y comentarios; parámetros con texto de inyección no cambiaron la consulta.

## Límites y siguiente paso

El carrito, la memoria y los borradores siguen en proceso. La búsqueda SQL es lexical y depende de los índices y de la consulta configurada por la ferretería; no hay descubrimiento automático de esquemas. `busy_timeout` de SQLite limita espera por bloqueo, no duración de SELECT; MySQL y SQL Server dependen de permisos y límites del servidor o driver. Un usuario SQL de solo lectura es obligatorio. La prueba con SQLite demuestra independencia de esquema, no compatibilidad ya verificada contra motores externos.

Siguientes adaptadores propuestos: REST para Siigo y Alegra, CSV para piloto e índice híbrido de catálogo con `pgvector` y búsqueda textual. No implementados en esta fase.

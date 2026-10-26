---
tags:
  - xeon/arquitectura
---

# Conector de la ferretería

Objetivo: que XEON lea el catálogo, los precios, el stock y las sedes desde el sistema de **cada ferretería** y no desde nuestros datos sintéticos. Decisión: [D13](decisiones-pendientes.md). Relación con el RAG: [D12](decisiones-pendientes.md). Relacionado: [arquitectura actual](arquitectura-actual.md), [contratos de herramientas](contratos-herramientas.md).

Revisado: 2026-10-26. Estado: **`implementado`** (Codex, `87ca4d2`; fusionado en `developer/daniel`). Auditado por el orquestador. Guía de uso: [`docs/CONECTOR_FERRETERIA.md`](../../docs/CONECTOR_FERRETERIA.md).

## Punto de partida (verificado el 2026-10-26)

- Todos los adaptadores son en memoria y con datos generados en código: `synthetic_seed.py`, `InMemoryProductCatalog`, `InMemoryBranchInventory` e `InMemoryQuoteDraftRepository`.
- `build_container` fija esos adaptadores. `Settings.data_mode` existe, pero no se usa.
- **Valores fijos en el código:**
  - `tenant_id="whatsapp"` en el toolbelt;
  - las sedes `sede-norte`, `sede-centro` y `sede-sur`;
  - la nota sintética en `domain/quote.py`;
  - la penalización `referencia_sintetica` en el ranking.
- No hay SQLAlchemy ni *drivers* entre las dependencias.

## Diseño

1. **Contrato:** los puertos `ProductCatalog`, `BranchInventory` y `BranchDirectory` (nuevo).
2. **Adaptador SQL:** SQLAlchemy 2 Core, de solo lectura.
   - `connectors/<tenant>.yaml` con consultas parametrizadas (`find_by_sku`, `search_text`, `stock_by_sku`, `list_branches`) y el mapeo de columnas a los campos canónicos.
   - El YAML se valida con Pydantic y se rechaza cualquier sentencia que no sea `SELECT`.
   - La URL de conexión se lee desde `secrets/`.
3. **Selección:** `DATA_SOURCE=synthetic|sql|rest|csv` y `TENANT_ID`.
4. **Después:** adaptador REST para ERP (Siigo, Alegra), adaptador CSV para pilotos, e índice híbrido propio (`pgvector` y *full-text*) sincronizado de forma incremental, solo con el catálogo descriptivo.
5. **Prueba de independencia:** una base SQLite con un esquema **distinto** al canónico debe cotizar correctamente solo con cambiar el YAML.

## Implementación (2026-10-26)

- **Dominio y puerto:** `domain/branch.py` y el puerto `application/ports/branches.py` (`BranchDirectory`). El intérprete resuelve las sedes contra el directorio, sin sedes fijas.
- **Configuración:** `Settings` tiene `DATA_SOURCE` (`synthetic` por defecto; `rest` y `csv` todavía fallan con un mensaje claro), `TENANT_ID`, `CURRENCY` y `SQL_URL_FILE`. La URL de conexión solo se lee desde `secrets/`.
- **Validación del YAML:** `connectors/schema.py` la hace con Pydantic.
  - Solo admite un `SELECT`, sin `;`, sin comentarios y sin palabras de DML o DDL.
  - Exige los parámetros `:sku`, `:query` y `:limit`, y el mapeo de los campos obligatorios.
- **Conexión:** `adapters/sql/connection.py` usa SQLAlchemy 2.1.6 Core (grupo opcional `db`) con parámetros enlazados y oculta los parámetros en los errores.
  - Solo lectura forzada en SQLite (`query_only`) y PostgreSQL (`READ ONLY`).
  - En MySQL y SQL Server depende de un usuario de solo lectura, que es **obligatorio**.
- **Adaptadores:** `adapters/catalog/sql.py`, `inventory/sql.py` y `branches/sql.py`. La nota y la penalización de referencias sintéticas se movieron al adaptador sintético.
- **Prueba de independencia** (`tests/test_sql_connector.py`):
  - una base SQLite con otro esquema (`articulos`, `sucursales` y `existencias`, con precios en centavos como texto y stock por bodega) cotiza 2 × $37.550 = $75.100 y consulta el stock en la sede `BOD-7`;
  - se rechazan INSERT, UPDATE, DROP, sentencias múltiples y comentarios;
  - una inyección pasada por parámetro no altera la consulta.
- **Verificación tras la fusión:** 294 pruebas, `ruff`, `mypy` y evaluación offline con 60 PASS.

## Límites

- No hay descubrimiento automático del esquema: alguien escribe el YAML de cada ferretería.
- La búsqueda SQL es léxica y depende de cómo se configure la consulta.
- El carrito, la memoria y los borradores siguen en el proceso.
- **Probado con motores reales** (Sonnet, `4af2c69`): PostgreSQL 17.6 y MySQL 8.4.6 en contenedores desechables (`compose.db-test.yaml`, `pytest -m integration`), con 9 de 9 pruebas aprobadas.
  - Cotiza con los precios de la base y resuelve las sedes por alias.
  - `LIMIT` y los parámetros funcionan.
  - El usuario de solo lectura no puede escribir y la inyección no devuelve filas.
  - SQL Server sigue sin probarse.
- **Hallazgos en MySQL, en corrección:**
  - **H1:** `DATETIME` no guarda zona horaria, por eso el stock queda «pendiente». Se resuelve con un campo opcional del conector que declara la zona.
  - **H2:** la conexión no estaba en modo solo lectura. Se resuelve con `SET SESSION TRANSACTION READ ONLY`.

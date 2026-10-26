---
tags:
  - xeon/arquitectura
---

# Conector de la ferretería

Objetivo: que XEON lea el catálogo, los precios, el stock y las sedes desde el sistema de **cada ferretería** y no desde nuestros datos sintéticos. Decisión: [D13](decisiones-pendientes.md). Relación con el RAG: [D12](decisiones-pendientes.md). Relacionado: [arquitectura actual](arquitectura-actual.md), [contratos de herramientas](contratos-herramientas.md).

Revisado: 2026-10-26. Estado: **`aprobado`, sin implementar**. Es la fase 2, después de las [correcciones de QA](qa-conde-2026-10-24.md).

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

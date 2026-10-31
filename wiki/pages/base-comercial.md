---
tags:
  - xeon/arquitectura
---

# Base comercial de Ferretería El Campín

Estado: `implementado` en `QA/testing` el 2026-10-31; ejecución contra PostgreSQL local pendiente.
Relacionado: [conector de la ferretería](conector-ferreteria.md), [arquitectura actual](arquitectura-actual.md) y [estado del corte](estado-del-corte.md).

El usuario proporcionó un reporte de 4.830 SKU únicos y declaró que sus artículos, impuestos y
precios son datos reales de Ferretería El Campín. El libro original no se versiona. La semilla
sanitizada excluye identidad tributaria, secretos, costos, márgenes, proveedores, ubicaciones
internas y el archivo fuente. La autenticidad y el permiso de publicación no fueron comprobados de
forma independiente.

## Implementación verificada

- Cinco migraciones Alembic aisladas crean el núcleo, catálogo hasta 4FN, precios e impuestos con
  vigencia, `stock`, vistas calculadas, búsqueda textual y almacenamiento `pgvector`.
- Marca, color, líneas, categorías y sublíneas son dimensiones y asociaciones independientes.
- El cimiento vectorial no fija dimensión ni crea HNSW/IVFFlat; embeddings y recuperación semántica
  siguen planificados.
- `scripts/build_commercial_seed.py` produce `manifest.json` y `products.jsonl` con huellas
  verificables; `scripts/seed_commercial_db.py` carga la revisión esperada en una transacción.
- El conector `ferreteria-el-campin.yaml` expone solo consultas `SELECT` para catálogo, búsqueda,
  stock por sucursal y sedes.

## Excepción vigente de la prueba

Por decisión explícita del usuario, el cargador asigna existencias vendibles a los artículos de
venta en Bucaramanga: 100 en Bodega 1 y 50 en Bodega 2. Los servicios no manejan stock. No existe un
estado de origen adicional. El cargador rechaza `APP_ENV=production`; antes de un piloto o venta
real esta carga debe sustituirse por inventario observado y deben restablecerse las reglas estrictas
de procedencia.

## Límites

La base aún no se migró ni sembró en la instancia local porque la URL debe ser creada por el usuario
en `secrets/xeon_commercial_url.txt`. La base comercial no contiene cotizaciones ni estado del
agente: esas responsabilidades permanecen en la persistencia operativa. La búsqueda consumida por
el agente continúa siendo lexical.

Fuente principal: [guía de base comercial](../../docs/BASE_COMERCIAL.md). Revisión: 2026-10-31.

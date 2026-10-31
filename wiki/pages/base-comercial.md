---
tags:
  - xeon/arquitectura
---

# Base comercial de Ferretería El Campín

Estado: `implementado` y cargado en PostgreSQL local el 2026-10-31.
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
- PostgreSQL 18.6 tiene pgvector 0.8.7 compilado e instalado. La revisión física es
  `0005_vector_search_foundation`: 4.830 productos, 23.148 precios, 37.216 filas de stock, 19
  incidencias por precio faltante, una sucursal y dos bodegas.
- La repetición completa del seed produce los mismos conteos. El primer reintento reveló un orden
  incorrecto bajo FK `RESTRICT`; se corrigió eliminando productos y tablas puente antes que las
  dimensiones de empresa.

## Excepción vigente de la prueba

Por decisión explícita del usuario, el cargador asigna existencias vendibles a los artículos de
venta en Bucaramanga: 100 en Bodega 1 y 50 en Bodega 2. Los servicios no manejan stock. No existe un
estado de origen adicional. El cargador rechaza `APP_ENV=production`; antes de un piloto o venta
real esta carga debe sustituirse por inventario observado y deben restablecerse las reglas estrictas
de procedencia.

## Límites

La base comercial no contiene cotizaciones ni estado del agente: esas responsabilidades permanecen
en la persistencia operativa. La búsqueda consumida por el agente continúa siendo lexical y la
tabla de embeddings está vacía hasta seleccionar modelo y dimensión.

Fuentes: [guía de base comercial](../../docs/BASE_COMERCIAL.md) y
[modelos E/R, lógico y físico](../../docs/MODELO_DATOS_COMERCIAL.md). Revisión: 2026-10-31.

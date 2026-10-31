# Base comercial de Ferretería El Campín

## Alcance y procedencia

Esta base comercial fue proporcionada por **Ferretería El Campín**. Según la declaración expresa
del usuario, los artículos, clasificaciones, impuestos y precios son datos completamente reales.
El repositorio conserva una semilla sanitizada; no incluye el libro original, identificadores
tributarios, credenciales, costos internos, márgenes, proveedores ni ubicaciones internas. La
autenticidad y el permiso de publicación no fueron verificados de forma independiente.

La fuente tiene 4.830 SKU únicos. `seeds/commercial/manifest.json` registra las huellas SHA-256
del archivo de origen y de `products.jsonl`, y el cargador rechaza cualquier alteración o diferencia
de cantidad. Los precios son COP e incluyen IVA. Los valores de precio iguales a cero no se
convierten en precios vendibles; los productos sin ningún precio positivo quedan registrados como
`MISSING_PRICE` y no aparecen en la vista cotizable.

## Modelo normalizado

El esquema `commercial` separa las dependencias multivaluadas para evitar grupos repetidos y
mantener el catálogo hasta 4FN:

- empresa, sucursales y bodegas: `businesses`, `branches`, `warehouses`;
- producto: `product_types`, `products`, `units_of_measure`, `product_units` y medidas;
- marca y color: dimensiones independientes y relaciones muchos-a-muchos; cuando el color no
  aplica se usa el valor explícito `NO_APLICA`;
- taxonomía: líneas, categorías y sublíneas independientes, con sus tablas de asociación;
- fiscal y precios: clases y vigencias tributarias, listas de precio y precios efectivos;
- inventario: `stock` por producto, bodega, unidad, tipo de cantidad, observación y vigencia;
- búsqueda: documento textual en español, cimiento `pgvector` y modelos de embedding separados;
- trazabilidad: fuentes, lotes de importación y problemas de calidad.

La migración `0005_vector_search_foundation` instala la extensión y crea la columna vectorial sin
dimensión fija ni índice ANN. El modelo, dimensión y HNSW/IVFFlat se decidirán cuando exista un
proveedor de embeddings evaluado. Los precios y el stock nunca se almacenan en el vector.

La base comercial es distinta de la base de estado operativo de XEON. Cotizaciones, conversaciones,
outbox y panel siguen bajo `STATE_STORE`; no se duplican aquí.

Los diagramas y el detalle de cardinalidades, claves, tipos, vistas e índices están en
[MODELO_DATOS_COMERCIAL.md](MODELO_DATOS_COMERCIAL.md).

## Sucursal e inventario temporal de prueba

La carga inicial crea la sucursal `Bucaramanga` y las bodegas `Bodega 1` y `Bodega 2`; el modelo
permite añadir otras sedes sin cambiar el esquema. Para la prueba actual, los artículos de venta
reciben 100 unidades en Bodega 1 y 50 en Bodega 2. Los servicios no manejan inventario. Esta es una
excepción explícita para el entorno actual: `scripts/seed_commercial_db.py` rechaza su ejecución con
`APP_ENV=production`. Antes de un piloto o venta real se debe reemplazar esa carga por existencias
observadas del sistema empresarial y volver a aplicar las reglas estrictas de procedencia.

## Configuración y carga

La URL SQLAlchemy PostgreSQL se guarda exclusivamente en
`secrets/xeon_commercial_url.txt`; ese archivo no se versiona ni se imprime. Debe usar el esquema de
driver `postgresql+psycopg://`. Con PostgreSQL y pgvector disponibles:

```powershell
uv run --locked --group db alembic -c alembic.commercial.ini upgrade head
$env:APP_ENV = "development"
uv run --locked --group db python scripts/seed_commercial_db.py
uv run --locked --group db python scripts/verify_commercial_db.py
```

El cargador exige la revisión `0005_vector_search_foundation`, adquiere un bloqueo transaccional,
reemplaza solamente los datos de `FERRETERIA_EL_CAMPIN`, y confirma el lote en una sola transacción.
Puede repetirse sin duplicar filas. Para que el agente consulte estas vistas, configure
`DATA_SOURCE=sql`, `TENANT_ID=ferreteria-el-campin` y mantenga la URL del conector en el archivo de
secretos previsto por `SQL_URL_FILE`.

En Windows con PostgreSQL 18, pgvector 0.8.7 se compila siguiendo el procedimiento oficial. El
script `scripts/install_pgvector_windows.cmd` valida Build Tools C++, la raíz de PostgreSQL y la
fuente antes de ejecutar `nmake`; la copia final en `Program Files` requiere UAC. La instalación
local verificada usa PostgreSQL 18.6 y pgvector 0.8.7.

## Límites actuales

- La recuperación que consume hoy el agente mediante el conector continúa siendo lexical; el
  almacenamiento vectorial aún no genera embeddings ni ejecuta similitud.
- No se reserva ni modifica inventario desde el agente: todas las consultas son `SELECT` y el
  backend conserva la autoridad sobre precios, impuestos y disponibilidad.
- La semilla no crea costos, descuentos, clientes, proveedores ni facturas.

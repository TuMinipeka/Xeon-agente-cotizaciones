# Modelo de datos comercial

Este documento representa el esquema implementado por las migraciones de `commercial_migrations`.
La fuente comercial sanitizada pertenece a Ferretería El Campín. La base comercial permanece
separada del estado operativo, las conversaciones y las cotizaciones de XEON.

## Modelo E/R conceptual

El modelo conceptual muestra las entidades de negocio y sus cardinalidades, sin tipos físicos:

```mermaid
erDiagram
    EMPRESA ||--o{ SUCURSAL : tiene
    SUCURSAL ||--o{ BODEGA : contiene
    EMPRESA ||--o{ PRODUCTO : comercializa
    TIPO_PRODUCTO ||--o{ PRODUCTO : clasifica
    PRODUCTO }o--o{ MARCA : posee
    PRODUCTO }o--o{ COLOR : posee
    PRODUCTO }o--o{ LINEA : pertenece
    PRODUCTO }o--o{ CATEGORIA : pertenece
    PRODUCTO }o--o{ SUBLINEA : pertenece
    LINEA }o--o{ CATEGORIA : admite
    CATEGORIA }o--o{ SUBLINEA : admite
    PRODUCTO }o--o{ UNIDAD_MEDIDA : vende_en
    PRODUCTO ||--o{ MEDIDA_PRODUCTO : describe
    PRODUCTO ||--o{ PRECIO_PRODUCTO : tiene
    LISTA_PRECIO ||--o{ PRECIO_PRODUCTO : define
    CLASE_IMPUESTO ||--o{ TASA_IMPUESTO : versiona
    PRODUCTO }o--o{ CLASE_IMPUESTO : tributa
    PRODUCTO ||--o{ STOCK : dispone
    BODEGA ||--o{ STOCK : almacena
    TIPO_CANTIDAD ||--o{ STOCK : califica
    FUENTE_DATOS ||--o{ LOTE_IMPORTACION : origina
    LOTE_IMPORTACION ||--o{ PRODUCTO : incorpora
    LOTE_IMPORTACION ||--o{ PROBLEMA_CALIDAD : registra
    PRODUCTO ||--|| DOCUMENTO_BUSQUEDA : proyecta
    PRODUCTO ||--o{ EMBEDDING_PRODUCTO : representa
    MODELO_EMBEDDING ||--o{ EMBEDDING_PRODUCTO : genera
```

Decisiones principales:

- Una empresa admite múltiples sucursales y cada sucursal múltiples bodegas.
- Marca, color y las tres clasificaciones comerciales son relaciones independientes y
  multivaluadas; no se guardan como listas dentro de `products`.
- Precios, impuestos y stock tienen vigencia u observación temporal.
- Los documentos y embeddings sirven para recuperar candidatos; nunca son autoridad de precio o
  inventario.

## Modelo lógico normalizado

El esquema lógico usa claves sustitutas para entidades empresariales, claves naturales para
catálogos globales y tablas puente para dependencias multivaluadas:

```mermaid
erDiagram
    businesses {
        bigint id PK
        varchar code UK
        varchar legal_name
        varchar display_name
        boolean active
    }
    branches {
        bigint id PK
        bigint business_id FK
        varchar code
        varchar name
        varchar city
    }
    warehouses {
        bigint id PK
        bigint branch_id FK
        varchar code
        varchar name
    }
    products {
        bigint id PK
        bigint business_id FK
        varchar product_type_code FK
        uuid_text import_batch_id FK
        varchar sku
        varchar name
        date registered_on
        jsonb specs
        text description_context
    }
    units_of_measure {
        varchar code PK
        varchar name
        varchar dimension
        boolean allows_fraction
    }
    product_units {
        bigint product_id PK,FK
        varchar unit_code PK,FK
        boolean is_primary
        numeric conversion_to_primary
        varchar assignment_method
    }
    price_lists {
        bigint id PK
        bigint business_id FK
        varchar code
        smallint priority
        boolean is_default
        boolean includes_tax
    }
    product_prices {
        bigint id PK
        bigint product_id FK
        bigint price_list_id FK
        bigint warehouse_id FK
        char currency_code FK
        numeric amount
        date valid_from
        date valid_to
    }
    tax_classes {
        bigint id PK
        bigint business_id FK
        varchar source_code
        varchar name
    }
    tax_rates {
        bigint id PK
        bigint tax_class_id FK
        numeric rate
        date valid_from
        date valid_to
    }
    stock {
        bigint id PK
        bigint product_id FK
        bigint warehouse_id FK
        varchar unit_code FK
        varchar quantity_type_code FK
        numeric quantity
        timestamptz observed_at
        timestamptz valid_until
    }
    product_search_documents {
        bigint product_id PK,FK
        text content
        char content_hash
        tsvector search_vector
    }
    product_embeddings {
        bigint product_id PK,FK
        bigint embedding_model_id PK,FK
        vector embedding
        char content_hash
    }

    businesses ||--o{ branches : business_id
    branches ||--o{ warehouses : branch_id
    businesses ||--o{ products : business_id
    products ||--o{ product_units : product_id
    units_of_measure ||--o{ product_units : unit_code
    businesses ||--o{ price_lists : business_id
    products ||--o{ product_prices : product_id
    price_lists ||--o{ product_prices : price_list_id
    tax_classes ||--o{ tax_rates : tax_class_id
    products ||--o{ stock : product_id
    warehouses ||--o{ stock : warehouse_id
    products ||--|| product_search_documents : product_id
    products ||--o{ product_embeddings : product_id
```

La cuarta forma normal se conserva separando las asociaciones `product_brands`, `product_colors`,
`product_lines`, `product_categories`, `product_sublines`, `line_categories` y
`category_sublines`. `products.specs` es una proyección documental de atributos variables; las
medidas repetibles con semántica conocida se almacenan en `product_measurements`.

## Modelo físico PostgreSQL

El despliegue físico usa el esquema `commercial` y cinco revisiones Alembic:

| Revisión | Objetos principales | Controles físicos |
|---|---|---|
| `0001_commercial_core` | empresa, sucursal, bodega, fuentes, lotes y calidad | identidades `BIGINT`, FK con políticas de borrado, `JSONB` para detalle de calidad |
| `0002_normalized_catalog` | productos, unidades, marca, color y taxonomía | restricciones únicas compuestas, GIN sobre `specs`, índice por nombre, unidad primaria parcial |
| `0003_versioned_pricing` | moneda, impuestos, listas y precios | `NUMERIC(18,4)`, rangos de vigencia, lista predeterminada parcial, vista `current_product_prices` |
| `0004_normalized_stock` | tipos de cantidad y `stock` | `NUMERIC(18,3)`, observación/vigencia, vistas `available_stock` y `branch_stock` |
| `0005_vector_search_foundation` | texto completo, modelos y embeddings | `tsvector` generado + GIN, extensión `vector`, columna sin dimensión fija y sin índice ANN |

### Dominios y precisión

- Dinero: `NUMERIC(18,4)` y moneda ISO de tres caracteres; el agente convierte a `Decimal`.
- Cantidad: `NUMERIC(18,3)` para admitir unidades fraccionables.
- Tasas: `NUMERIC(7,4)` entre 0 y 100.
- Instantes: `TIMESTAMPTZ`; fechas de vigencia comercial: `DATE`.
- Atributos flexibles: `JSONB`; texto recuperable: `TSVECTOR` en configuración española.
- Vectores: tipo `vector` sin dimensión hasta seleccionar y versionar el modelo de embeddings.

### Vistas de consumo

- `current_product_prices`: elige el precio vigente por prioridad y lista predeterminada.
- `available_stock`: toma la observación más reciente de cada tipo y calcula disponibilidad sin
  permitir resultados negativos.
- `branch_stock`: agrega bodegas por sucursal.
- `catalog_products`: expone únicamente productos activos con unidad, precio vigente y documento de
  búsqueda; es la fuente del conector de solo lectura.

### Seguridad y operación

Las credenciales viven fuera de Git. El agente usa consultas `SELECT` parametrizadas y no recibe
permisos para aprobar cotizaciones, modificar inventario o ejecutar SQL libre. El esquema comercial
se migra con `alembic.commercial.ini` y no comparte historial con la persistencia operativa.

Revisión: 2026-10-31. Fuente de verdad física: `commercial_migrations/versions/`.

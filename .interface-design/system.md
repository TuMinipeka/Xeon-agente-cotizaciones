# XEON — Sistema de Diseño de Interfaz (`.interface-design/system.md`)

Especificación viva del sistema de diseño para las superficies operativas e interactivas de **XEON** (Consola Comercial de Mostrador, Demo Interactiva del MVP y Herramientas de Revisión), construida aplicando las skills `interface-design`, `impeccable`, `refactoring-ui`, `web-typography`, `ux-heuristics`, `microinteractions` y `web-design-guidelines`.

---

## 1. Intención y Exploración del Dominio

- **Quién es el usuario:** Vendedor de mostrador ferretero, comerciante regional o evaluador técnico que necesita verificar en segundos qué producto identificó la IA, en qué sede hay stock firme (`fresh` vs `stale`) y cuánto suma exactamente el borrador `DRAFT` en `Decimal`.
- **Verbo principal:** **Verificar y cotizar sin fricción** (*"De una pregunta coloquial a un borrador verificable"*).
- **Personalidad ("Feel"):** **Mesa de operaciones industrial y despacho técnico**. Precisa como una hoja de ingeniería, con fondos casi negros y una ruta jade/menta derivada del logo oficial de XEON. La referencia cromática y sus reglas de uso están en [`docs/DESIGN.md`](../docs/DESIGN.md).
- **Elemento Firma (Signature):** **El Sello de Procedencia y Vigencia (`Provenance & Freshness Ledger`)** — cada cifra monetaria y cada unidad de stock muestra en tipografía monoespaciada (`tabular-nums`) su origen exacto (`SKU`, `catalog_version`, sede, canal `local`/`transfer`/`delivery` y frescura `FRESH`/`STALE`).

---

## 2. Arquitectura de Tokens (Color & Superficies)

La paleta deriva de `logo-oficial-definitivo.png`. La proporción práctica es **70 % superficies oscuras, 20 % contenido y 10 % acentos**; los estados comerciales no se infieren del verde de marca:

```css
:root {
  /* Superficies jade-negro derivadas del logo oficial */
  --bg-canvas:        #04110f; /* Nivel 0: Lienzo base */
  --surface-1:        #09201b; /* Nivel 1: Contenedor de mesa de trabajo */
  --surface-2:        #0d2823; /* Nivel 2: Tarjetas interactivas */
  --surface-3:        #134038; /* Nivel 3: Hover y popovers */
  --surface-inset:    #020a09; /* Nivel -1: Inputs y consolas de datos */

  /* Bordes de baja opacidad (Estructura silenciosa) */
  --border-subtle:    rgba(111, 255, 211, 0.10);
  --border-default:   rgba(111, 255, 211, 0.20);
  --border-strong:    rgba(111, 255, 211, 0.55);
  --focus-ring:       0 0 0 3px rgba(111, 255, 211, 0.65);

  /* Jerarquía de texto de 4 niveles */
  --text-primary:     #eafbf5; /* Nivel 1: Títulos, totales y valores clave */
  --text-secondary:   #b6dcd1; /* Nivel 2: Cuerpo de lectura y descripciones */
  --text-tertiary:    #83b1a3; /* Nivel 3: Etiquetas y cabeceras */
  --text-muted:       #83b1a3; /* Nivel 4: Metadatos; reducir jerarquía con tamaño/peso */

  /* Acento de marca y colores semánticos de negocio */
  --accent-primary:   #00d9a3; /* Jade XEON; no significa stock confirmado */
  --accent-hover:     #6fffd3;
  --accent-ink:       #04110f;

  --status-fresh-bg:  rgba(0, 217, 163, 0.12);
  --status-fresh-fg:  #8be3c9; /* Acompañar con icono, texto, origen y fecha */
  --status-stale-bg:  rgba(246, 191, 119, 0.15);
  --status-stale-fg:  #f6bf77; /* Dato vencido o aclaración requerida */
  --status-error-bg:  rgba(255, 141, 137, 0.15);
  --status-error-fg:  #ff8d89; /* Fuente caída o descuento rechazado */
}
```

---

## 3. Tipografía y Escala Modular (`web-typography`)

- **Familias:**
  - `--font-display`: `'Space Grotesk', system-ui, sans-serif` (Titulares con `letter-spacing: -0.03em` y `text-wrap: balance`).
  - `--font-sans`: `'IBM Plex Sans', system-ui, sans-serif` (Cuerpo y controles, `16px` base, `line-height: 1.6`, ancho máximo `65ch`).
  - `--font-mono`: `'IBM Plex Mono', monospace` (SKUs, precios `Decimal`, UUIDs, vigencias y conteos con `font-variant-numeric: tabular-nums`).
- **Escala (~1.25 Major Third):**
  - `xs`: `12px` (Eyebrows, badges semánticos, metadatos con `letter-spacing: 0.08em`)
  - `sm`: `14px` (Labels de controles, chips de escenario, tablas)
  - `base`: `16px` (Cuerpo de lectura e inputs para evitar auto-zoom en móvil)
  - `lg`: `20px` (Títulos de tarjeta / pestañas)
  - `xl`: `28px` (Encabezado de panel activo)
  - `display`: `clamp(2.25rem, 4vw, 3.5rem)` (Hero principal y cifra total de cotización)

---

## 4. Espaciado, Radios Concéntricos y Microinteracciones

- **Unidad base (`8px` / `4px`):** `4px`, `8px`, `12px`, `16px`, `24px`, `32px`, `48px`.
- **Radios concéntricos (`outerRadius = innerRadius + padding`):**
  - Contenedor Workbench: `20px` (`--radius-xl`)
  - Tarjetas internas / Paneles de resultado: `12px` (`--radius-md`)
  - Botones, inputs y chips: `8px` (`--radius-sm`)
- **Microinteracciones (`microinteractions`):**
  - Curva de entrada/interacción: `cubic-bezier(0.23, 1, 0.32, 1)` en `160ms`.
  - Feedback táctil en botones: `transform: scale(0.98)` en `:active`.
  - Área mínima de toque (WCAG): `44px` de alto en controles primarios.
  - Respeto estricto a `@media (prefers-reduced-motion: reduce)`.

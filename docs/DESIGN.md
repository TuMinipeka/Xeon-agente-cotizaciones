# Identidad visual de XEON

Fuente visual: [`xeon-logo.png`](../assets/brand/xeon-logo.png). El archivo es un raster con gradientes: los valores siguientes son **tokens de interfaz derivados del logo**, no una afirmación de que exista un único color plano oficial dentro de la imagen.

## Dirección

**Precisión verificable, trato humano.** El símbolo oficial combina un fondo casi negro con un recorrido de jade a menta. La interfaz utiliza ese mismo eje cromático. Los datos comerciales deben ser más fáciles de leer que el brillo decorativo; la conexión con un asesor real se distingue mediante texto, retrato/nombre y una acción clara, no mediante un nuevo color de marca.

Usuarios principales: comprador que escribe por WhatsApp y vendedor que verifica SKU, stock, vigencia y borrador. La firma gráfica de XEON es una **ruta segmentada de verificación**, inspirada en las piezas del símbolo: consulta → código/SKU candidato → disponibilidad → borrador → asesor. Cada segmento se activa cuando existe información para respaldarlo; una animación nunca convierte un dato incierto en confirmado.

## Paleta base

| Token | Hex | Uso |
| --- | --- | --- |
| `--xeon-void` | `#04110F` | Fondo de marca y escenas oscuras |
| `--xeon-surface` | `#0D2823` | Paneles, tarjetas y superficies elevadas |
| `--xeon-surface-high` | `#134038` | Hover, panel seleccionado y profundidad |
| `--xeon-jade` | `#00D9A3` | Acento principal, enlaces, acción primaria y ruta activa |
| `--xeon-mint` | `#6FFFD3` | Destello breve, foco visible y detalles del logo |
| `--xeon-text` | `#EAFBF5` | Texto principal sobre fondos oscuros |
| `--xeon-text-secondary` | `#B6DCD1` | Texto secundario sobre superficies oscuras |
| `--xeon-ink` | `#04110F` | Texto dentro de botones jade o menta |

La imagen contiene verdes intermedios y luces. El muestreo aproximado del raster encuentra grupos frecuentes en torno a `#00C090`, `#00D0A0` y `#00E0A0`; `#00D9A3` es el punto de diseño elegido para componentes reproducibles. Usar el archivo del logo sin recolorearlo.

### Proporción y gradientes

- 70 % fondos y superficies oscuros; 20 % texto y estructura; hasta 10 % jade/menta para acciones y señales importantes.
- Fondo de escena: `linear-gradient(135deg, #04110F 0%, #0D2823 65%, #061A16 100%)`.
- Acento de marca: `linear-gradient(110deg, #00B88A 0%, #00D9A3 52%, #6FFFD3 100%)` solo en el símbolo, una línea de avance o una superficie grande sin texto pequeño.
- El texto y los iconos informativos se colocan sobre un **color sólido**. Si cruzan un gradiente, verificar el contraste en su punto más claro u oscuro.
- Evitar el gradiente cian → cobre de la versión anterior. Ámbar y coral quedan reservados para estados de atención y error, no para construir la identidad.

## Semántica y UX

| Estado | Presentación | Regla |
| --- | --- | --- |
| SKU candidato | Etiqueta “Candidato · por confirmar” | Jade de marca no significa certeza. Mostrar código y descripción. |
| Stock vigente (`fresh`) | Icono + “Disponible · verificado” + origen y fecha | No comunicarlo solo con verde. |
| Stock vencido (`stale`) | `#F6BF77` + “Dato vencido” | No prometer disponibilidad. |
| Stock desconocido (`unknown`) | Neutral + “Sin confirmar” | No traducir desconocido como agotado. |
| Error o fuente caída | `#FF8D89` + causa y siguiente paso | Conservar la consulta y permitir reintento. |
| Borrador (`DRAFT`) | “Borrador · requiere revisión” | No mostrarlo como cotización aprobada. |
| Asesor real | Nombre/rol visible + “Contactar asesor” | Mostrar el traspaso humano solo cuando la función exista; en demos, indicar que es una representación. |

Una pantalla o panel tiene un único foco: SKU, disponibilidad, total o contacto. La acción primaria usa jade con texto oscuro; una acción secundaria usa borde y texto. La animación de la ruta muestra progreso o procedencia, sin ocultar cantidades, unidades, sede ni vigencia.

## Accesibilidad verificable

- Contraste calculado con la fórmula de WCAG: `#EAFBF5` sobre `#04110F` = **17,96:1**; `#B6DCD1` sobre `#0D2823` = **10,52:1**; `#04110F` sobre `#00D9A3` = **10,49:1**.
- **No** colocar texto claro sobre jade: `#EAFBF5` sobre `#00D9A3` = **1,71:1**.
- Objetivos WCAG AA: texto normal ≥ 4,5:1; texto grande e indicadores visuales necesarios ≥ 3:1. Foco visible, estados con texto/icono además de color y respeto de `prefers-reduced-motion`.
- Los valores anteriores aplican a estos pares de colores planos; cada composición final, transparencia, imagen y gradiente debe comprobarse de nuevo.

Referencias: [heurísticas de Nielsen](https://www.nngroup.com/articles/ten-usability-heuristics/), [contraste de texto WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [contraste no textual](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) y [uso de color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).

## Aplicación por superficie

- **Logo:** usar el PNG oficial. Mantener una zona oscura limpia alrededor para conservar el brillo y la silueta.
- **XEON CLI y documentación:** usar el logo oficial y los tokens jade/menta; comprobar contraste y legibilidad en terminales con y sin color.
- **Demo y futura consola:** compartir los tokens de esta guía. SKU, precio y stock mantienen etiquetas de procedencia y vigencia; no usar el color de marca como semáforo de disponibilidad.

Esta guía fija la identidad para el shell, la documentación y cualquier material visual futuro. Cada exportación debe revisarse visualmente antes de publicarse.

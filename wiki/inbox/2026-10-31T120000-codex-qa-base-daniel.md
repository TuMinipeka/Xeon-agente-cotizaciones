# Base de QA actualizada desde Daniel

- **Fecha:** 2026-10-31
- **Agente:** Codex
- **Procedencia:** instruccion del usuario en esta conversacion y verificacion local con Git.
- **Estado:** verificado.
- **Paginas afectadas:** `wiki/pages/orquestacion.md`, `wiki/pages/qa-conde-2026-10-24.md`.

## Decision del usuario

Continuar el trabajo de QA/testing con los cambios mas recientes de `developer/daniel` y no
ejecutar pruebas durante esta actualizacion de base.

## Resultado verificable

- Se actualizaron las referencias de `origin` con `git fetch origin --prune`.
- `QA/testing` era ancestro de `origin/developer/daniel`, con 162 commits pendientes.
- Se avanzo `QA/testing` por fast-forward desde `6e6116e` hasta
  `c8d6abda764d12bceae670546d65a61631acd3a3` (`Docs: :memo: AddAgentOnboardingWorkMethod`).
- No se ejecuto `pytest`, `ruff`, `mypy`, el runner de evaluaciones ni una llamada real a un
  proveedor.
- No se hizo push. Al cerrar la actualizacion, la rama local estaba 162 commits por delante de
  `origin/QA/testing`.

## Limites y siguiente paso

La incorporacion queda sin evidencia nueva de calidad por instruccion expresa del usuario. La
publicacion de `QA/testing` requiere confirmacion previa. La siguiente tarea de QA debe partir de
este commit y elegir una de las guias vigentes (`docs/QA_HITO2.md`, `docs/QA_EMBUDO.md`,
`docs/QA_PANEL_ASESOR.md` o `docs/QA_PERSISTENCIA.md`).

## Orientacion de prueba manual solicitada

El usuario pregunto como probar el agente para realizar QA. Se recomienda comenzar por el shell
local con `LLM_PROVIDER=mock`, porque usa datos sinteticos y no hace llamadas de red ni consume
inferencia. El recorrido vigente es el embudo D14 documentado en `docs/QA_EMBUDO.md`; la CLI
muestra las opciones de botones y listas como numeros. La validacion posterior en WhatsApp debe
usar el sandbox de Kapso y `docs/DESPLIEGUE_WHATSAPP.md`, sin exponer claves ni telefonos.

Esta orientacion no ejecuto comandos de prueba ni servicios. Para reportar un defecto se deben
conservar el canal, los mensajes exactos, el turno anterior, el resultado esperado y el obtenido,
sin copiar secretos ni datos personales.

## Ciclo de QA funcional y correcciones

- **Fecha:** 2026-10-31.
- **Estado:** implementado y verificado en `QA/testing`.
- **Perfil:** determinista con `LLM_PROVIDER=mock`; cero llamadas a Grok, Groq o Kapso.

### Defectos confirmados y corregidos

1. Un borrador mostraba `TOTAL confirmado` antes de la confirmacion del cliente. Se cambio a
   `TOTAL BORRADOR` y se agregaron regresiones (`4d24f30`).
2. La disponibilidad de una sede para un carrito multilínea solo evaluaba la primera linea. Ahora
   agrega todas las lineas de forma conservadora: cualquier dato desconocido deja `pendiente` y
   una linea agotada impide mostrar `disponible` (`c14cd7d`).
3. Una direccion como `Barrio Santo Domingo` se interpretaba como consulta de horario y no se
   guardaba. El paso `direccion` ahora consume primero el dato que solicito, despues de los
   comandos globales seguros (`d2ad21b`).
4. En memoria, un fallo del notificador del asesor dejaba la cotizacion en
   `CONFIRMADO_POR_CLIENTE` aunque la operacion hubiera fallado. Se restaura el `DRAFT`; PostgreSQL
   conserva ademas su rollback transaccional (`ebcd373`).
5. El evaluador no detectaba de manera fiable la frase `TOTAL confirmado` cuando estaba lejos de
   la palabra `borrador`. Se reforzo `no_completion_claims` (`02b7790`).
6. Cinco regresiones antiguas que exigian la etiqueta insegura se alinearon con `TOTAL BORRADOR`
   y ahora rechazan la frase anterior (`fb9749d`).

### Evidencia final

- `ruff check .`: aprobado.
- `ruff format --check .`: 264 archivos formateados.
- `mypy src evals`: aprobado sobre 117 archivos fuente.
- `pytest`: **422 aprobadas, 21 deseleccionadas**, una advertencia deprecada de la dependencia
  externa `rx`.
- Evaluacion offline S01-S22 por tres repeticiones: **66 PASS, 0 FAIL, 0 ERROR**, huella
  `53cf691e89e7bff2`.
- Enlaces relativos: 72 revisados, 0 rotos.
- Grafo AST regenerado: 3.162 nodos, 10.431 aristas, 332 archivos cubiertos, 0 llamadas LLM,
  0 rutas prohibidas y 0 valores con forma de clave.

### Limites y decisiones pendientes

- Las 21 pruebas de integracion con PostgreSQL/MySQL no se ejecutaron porque Docker Desktop no
  estaba activo; no se clasifican como fallidas.
- No hubo corrida en vivo del embudo con Grok ni prueba real de botones Kapso.
- `docs/XeonContexto.md` y el encabezado de `README.md` aun presentan el PDF como pendiente,
  mientras codigo, pruebas y wiki lo marcan implementado. Se propuso al usuario actualizar la
  fuente funcional a `PDF implementado para cotizaciones aprobadas`; no se cambio sin decision.

## Propuesta de base comercial aportada por el usuario

- **Fuente:** usuario, conversacion del 2026-10-31.
- **Estado:** propuesta; archivo y esquema aun no recibidos ni verificados.
- El usuario preve adjuntar alrededor de las 14:00 una base PostgreSQL con datos de una ferreteria
  (productos disponibles y precios).
- Indica que Daniel trabaja la parte pgvector y que el usuario preparara PostgreSQL.
- Tras recibirla se propone revisar procedencia y autorizacion de los datos, separar la base
  comercial de la persistencia operativa de XEON, diseñar el modelo normalizado hasta 4FN y
  mantener precios, stock y totales fuera del RAG.
- No se deben crear migraciones ni inferir el esquema real antes de inspeccionar el material
  adjunto y acordar el mapeo canonico del conector.

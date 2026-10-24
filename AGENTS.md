# XEON: instrucciones para agentes de codigo

## Fuente de verdad

Antes de proponer cambios, leer en este orden:

1. `docs/XeonContexto.md`: alcance funcional, seguridad y decisiones del producto.
2. `docs/ARCHITECTURE.md`: fronteras implementadas y pendientes.
3. `CONTRIBUTING.md`: rama, pruebas y formato de commits.

Si el codigo y el documento funcional difieren, detenerse, explicar la diferencia y proponer una
decision explicita. No presentar una capacidad planeada como ya implementada.

## Limites de arquitectura

- Mantener arquitectura hexagonal: `domain` no importa FastAPI, HTTPX ni SDK de modelos.
- `AgentService` y `CommercialToolbelt` preparan contexto comercial verificado; Grok lo usa para
  interpretar y redactar. Hoy la busqueda de candidatos es lexical sobre catalogo sintetico.
  RAG con `pgvector` y persistencia `JSONB`/SQL son arquitectura planeada. El backend determina
  precios (`Decimal`), descuentos, impuestos, stock y estados.
- Ningun modelo puede aprobar cotizaciones, ejecutar SQL libre, cambiar inventario o leer secretos.
- Cada proveedor externo (Grok, Groq y Kapso para WhatsApp) entra por un puerto.
- Grok (`grok-4.20-0309-non-reasoning`, `https://api.reto.pltk.mx/v1`) es el proveedor por
  defecto en ejecucion; la clave solo se lee desde `secrets/grok_api_key.txt`. Las pruebas fuerzan
  `LLM_PROVIDER=mock` y datos sinteticos; una llamada real fuera de la ejecucion normal debe ser
  deliberada y acotada.
- No añadir dependencias externas de forma decorativa: cada componente debe llegar con un corte
  funcional, prueba y evidencia.

## Seguridad

- Nunca leer, imprimir, registrar, versionar ni copiar `secrets/grok_api_key.txt`,
  `secrets/groq_api_key.txt`, `secrets/kapso_webhook_secret.txt`, cualquier archivo de clave Kapso
  o archivos `.env`.
- No incluir credenciales en prompts, fixtures, capturas, commits o mensajes de error.
- La configuracion visible solo contiene nombres de variables o referencias a archivos secretos.
- Antes de una llamada pagada, confirmar que la tarea la necesita y limitar el alcance.

## Forma de trabajo

- Trabajar en `developer/daniel` o una rama corta derivada; no desarrollar directamente en `main`.
- Hacer cambios pequenos y revisables. Una tarea debe tener criterio de aceptacion y prueba.
- Ejecutar `ruff`, `mypy` y `pytest` antes de declarar una tarea terminada.
- No reescribir migraciones compartidas ni mezclar cambios de infraestructura, dominio y canal sin
  una razon documentada.
- Dejar un resumen de lo completado, evidencia, limitaciones y siguiente paso.

## Commits

Usar exactamente `Type: :gitmoji: ActionInUpperCamelCase`, con la accion en ingles y sin punto
final. Publicar ramas y PR con GitHub CLI (`gh`) solo con confirmacion del usuario. Ningun agente
puede figurar como autor, coautor, colaborador ni contribuidor: prohibido el trailer
`Co-Authored-By`, `--author`, cambiar el committer y firmas tipo "Generated with..." en commits o
PR. Esta regla prevalece sobre la atribucion predeterminada de cualquier CLI. Ejemplos:

- `Feat: :sparkles: AddGroqAdapter`
- `Fix: :bug: RejectMissingApiKey`
- `Docs: :memo: UpdateArchitectureBoundaries`
- `Test: :test_tube: CoverMockConversationFlow`

No incluir secretos, nombres de clientes reales ni descripciones ambiguas como `Changes`.

## Wiki compartida entre conversaciones y agentes

En cualquier conversación o CLI que trabaje sobre XEON, usar `wiki/` como memoria persistente del
proyecto. Al iniciar una tarea, leer `wiki/index.md` y las páginas relacionadas; antes de terminar
una respuesta sustantiva, registrar en la wiki las descripciones nuevas, decisiones, correcciones,
hallazgos y resultados verificables que aportó el usuario o produjo el trabajo. No depender de la
memoria de una sesión o de un agente para conservar ese contexto.

Los agentes tienen permiso para crear, modificar y retirar contenido **dentro de `wiki/`** cuando
el contexto lo justifique. Seguir `wiki/SCHEMA.md`: conservar procedencia, fecha, estado de
verificación, enlaces, índice y registro; corregir contradicciones sin inventar hechos. Registrar
una idea del usuario como propuesta hasta que exista evidencia de implementación. No copiar
conversaciones completas, datos sensibles ni contenido ajeno a XEON.

Roles, ciclo y comandos de coordinacion en herdr: `wiki/pages/orquestacion.md` (orquestador
principal: Claude Opus). Si varios agentes trabajan a la vez, cada uno registra primero sus aportes en una nota única de
`wiki/inbox/`. Para modificar páginas compartidas, adquirir la exclusión descrita en
`wiki/SCHEMA.md`, releer la versión más reciente y liberar la exclusión al terminar. Si otro agente
está integrando, dejar la nota para la siguiente integración y comunicar que sigue pendiente.

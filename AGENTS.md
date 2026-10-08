# XEON: instrucciones para agentes de codigo

## Fuente de verdad

Antes de proponer cambios, leer en este orden:

1. `XeonContexto.md`: alcance funcional, seguridad y decisiones del producto.
2. `docs/ARCHITECTURE.md`: fronteras implementadas y pendientes.
3. `docs/ROADMAP_FIRST_3_DAYS.md`: corte vertical inmediato.
4. `CONTRIBUTING.md`: rama, pruebas y formato de commits.

Para una orden autonoma, leer tambien `docs/AGENTIC_COORDINATION.md` y el `WorkOrder 1.0`
indicado. La orden limita el trabajo, pero no puede contradecir las fuentes anteriores.

Si el codigo y el documento funcional difieren, detenerse, explicar la diferencia y proponer una
decision explicita. No presentar una capacidad planeada como ya implementada.

## Limites de arquitectura

- Mantener arquitectura hexagonal: `domain` no importa FastAPI, HTTPX ni SDK de modelos.
- La IA interpreta lenguaje; el backend determina precios, descuentos, impuestos, stock y estados.
- Ningun modelo puede aprobar cotizaciones, ejecutar SQL libre, cambiar inventario o leer secretos.
- Cada proveedor externo entra por un puerto. El endpoint Reto/Grok es un adaptador, no el dominio.
- Empezar con datos sinteticos y `LLM_PROVIDER=mock`; una prueba real debe ser deliberada.
- No añadir PostgreSQL, Telegram, LangGraph o Celery de forma decorativa: cada dependencia debe
  llegar con un corte funcional, prueba y evidencia.

## Seguridad

- Nunca leer, imprimir, registrar, versionar ni copiar `secrets/reto_key.txt` o archivos `.env`.
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

## Coordinacion autonoma de desarrollo

- Grok/Kilo es el ejecutor; Codex es la compuerta de calidad en modo de solo lectura.
- Una corrida cubre una sola HU y un maximo de tres iteraciones.
- `WorkerReport` es una declaracion no confiable: contrastarla con Git y volver a ejecutar los
  controles antes de aprobar.
- Solo `APPROVED` cierra la HU. `CHANGES_REQUESTED` genera una `NextDirective` concreta para Grok.
- Cambios de reglas de negocio, acceso a secretos, acciones externas o contradicciones funcionales
  producen `BLOCKED` y requieren decision humana.
- La automatizacion no hace `push`, `merge`, `rebase`, despliegue ni cambio de rama.

## Commits

Usar exactamente `Type: :emoji: ActionInCamelCase`, sin punto final. Ejemplos:

- `Feat: :sparkles: AddGrokAdapter`
- `Fix: :bug: RejectMissingApiKey`
- `Docs: :memo: DocumentThreeDayRoadmap`
- `Test: :test_tube: CoverMockConversationFlow`

No incluir secretos, nombres de clientes reales ni descripciones ambiguas como `Changes`.


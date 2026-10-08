# Primeros tres dias: XEON ejecutable de extremo a extremo

## Definicion de “extremo a extremo” para este hito

Un usuario de prueba envia texto, XEON identifica o aclara productos usando datos sinteticos, el
backend calcula un borrador, el resultado queda persistido y un operador puede revisarlo. El flujo
se demuestra primero por API/CLI. Telegram se agrega solo si el corte determinista ya pasa.

No significa todavia: datos empresariales reales, aprobación productiva, reserva de inventario,
PDF definitivo, WhatsApp ni disponibilidad empresarial.

## Dia 1 — base reproducible

- Arrancar Python 3.14.8 en Docker y ejecutar la API en modo `mock`.
- Mantener configuración segura por perfiles y prueba de contrato del adaptador Grok.
- Fijar arquitectura, reglas para agentes de codigo y convención de commits.
- Evidencia: `/health`, `/v1/chat`, `ruff`, `mypy`, `pytest` y build Docker.

## Dia 2 — cotizador determinista

- Crear `Product`, `Money`, `Quote`, `QuoteLine` y estados iniciales con `Decimal`.
- Cargar catálogo ficticio versionado; no atribuirlo a una empresa real.
- Implementar búsqueda exacta/alias, cálculo de líneas y borrador sin LLM.
- Persistir con PostgreSQL y Alembic si la base local ya está disponible; en caso contrario usar un
  puerto de repositorio en memoria para no bloquear el corte y dejar la integración como tarea
  explícita.
- Evidencia: casos T01, T02, T03, T06, T08 y T19 del documento funcional.

## Dia 3 — orquestación y demostración

- Exponer búsqueda y creación de borrador como herramientas tipadas; el modelo nunca calcula.
- Conectar Grok con presupuesto y secreto rotado, y conservar una ejecución equivalente en mock.
- Añadir CLI de revisión del borrador y, si el núcleo está estable, Telegram en polling personal.
- Ejecutar: solicitud -> aclaración -> selección confirmada -> cálculo -> borrador -> revisión.
- Registrar latencia, consumo, fallos y limitaciones. Ningún resultado se denomina “aprobado” o
  “emitido” sin el caso de uso humano correspondiente.

## Puerta de salida del tercer dia

El hito pasa cuando otro integrante puede clonar la rama, crear su secreto local, levantar Docker,
ejecutar la demostración documentada y obtener el mismo resultado sintético sin modificar código.
Las llamadas externas se pueden desactivar con `LLM_PROVIDER=mock` y las pruebas normales no
consumen Grok.


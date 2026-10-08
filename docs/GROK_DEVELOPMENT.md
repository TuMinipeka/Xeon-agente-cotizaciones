# Grok para desarrollar XEON, separado del agente XEON

## Dos usos distintos

1. **Grok como agente de codigo:** funciona dentro de Kilo Code, lee el repositorio y propone o
   ejecuta cambios con aprobación. Usa `kilo.jsonc`, `.kilo/agents/xeon-builder.md` y `AGENTS.md`.
2. **Grok dentro de XEON:** la API llama al mismo modelo a través de `LLMPort`. Solo recibe contexto
   conversacional permitido y nunca obtiene herramientas de terminal o edición de código.

No reutilices sesiones, prompts ni permisos entre ambos usos.

## Configuracion segura de Kilo Code

La extensión recomendada es Kilo Code. La configuración del repositorio apunta a un archivo local
ignorado por Git; no contiene la clave.

1. Revoca y rota la clave que fue compartida en texto.
2. Crea `secrets/reto_key.txt` y pega solo la clave nueva. No añadas comillas ni nombre de variable.
3. Abre el repositorio como workspace confiable y reinicia VS Code.
4. Abre Kilo Code, selecciona el modelo `Grok 4.6 (Reto)` y el agente `xeon-builder`.
5. Prueba primero con: `Lee AGENTS.md y explica el siguiente corte sin editar archivos`.
6. Para construir: `Implementa solamente la tarea del Dia 2 sobre dominio y pruebas. Pide permiso
   antes de editar o ejecutar comandos y termina con evidencia`.

Kilo resuelve `{file:./secrets/reto_key.txt}` dentro del proyecto. El agente tiene lectura y
búsqueda permitidas, pero edición y terminal requieren confirmación humana.

## Activar Grok dentro de XEON

En Docker:

```powershell
docker compose --profile core -f compose.yaml -f compose.grok.yaml up --build
```

En local con `uv`, usa `RETO_KEY_FILE` apuntando al archivo secreto y cambia
`LLM_PROVIDER=grok` solo para la sesión. Para una prueba sin coste:

```powershell
docker compose --profile core up --build
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/chat `
  -ContentType 'application/json' -Body '{"message":"hola"}'
```

La respuesta `provider=mock` confirma que no hubo llamada externa. Una respuesta real debe mostrar
`provider=grok`; revisa presupuesto y uso en el proveedor antes de repetir evaluaciones.

## Prompts de continuidad recomendados

- `Lee XeonContexto.md, AGENTS.md y el roadmap. Propón un solo corte vertical con criterios de
  aceptación; todavía no edites.`
- `Implementa el corte aprobado sin tocar secretos. Mantén las reglas comerciales fuera del prompt
  y cubre el comportamiento con pruebas.`
- `Revisa el diff contra el documento funcional. Separa lo implementado de lo planeado y enumera
  riesgos antes de crear un commit.`


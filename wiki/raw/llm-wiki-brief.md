# Encargo LLM Wiki, 2026-10-24

Resumen curado del patrón aportado por el usuario en esta conversación. Se conserva como entrada de diseño de la bóveda; no es una transcripción literal.

- Mantener una wiki persistente, enlazada y actualizada por el agente, en vez de recomponer el conocimiento desde documentos crudos en cada consulta.
- Separar fuentes crudas, wiki generada y esquema operativo. Las fuentes no se modifican durante la ingesta.
- Ingestar fuentes, actualizar síntesis y páginas relacionadas, detectar contradicciones y registrar cada operación.
- Consultar empezando por un índice; convertir respuestas valiosas en páginas reutilizables.
- Revisar enlaces, huérfanos, contradicciones, afirmaciones vencidas y vacíos de investigación.
- Mantener `index.md` como catálogo y `log.md` como historial cronológico con encabezados parseables.
- Obsidian sirve como visor. Búsqueda local, imágenes, Dataview, Marp y otras herramientas son opcionales y se incorporan solo cuando haya necesidad.

Decisión de implementación para XEON: el repositorio ya funciona como vault de Obsidian; `wiki/` aloja las síntesis y las fuentes del proyecto se referencian por ruta y huella en lugar de duplicarse.

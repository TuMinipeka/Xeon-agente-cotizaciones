# Capturas pendientes

Cada agente crea aquí una nota con nombre único antes de integrar nuevo conocimiento en las páginas compartidas. La nota debe indicar origen, fecha, afirmaciones y estado de verificación, junto con las páginas afectadas. Si otro agente posee `wiki/.write-lock/`, la nota queda pendiente. Tras integrar y registrar el cambio en `log.md`, se retira la nota procesada.

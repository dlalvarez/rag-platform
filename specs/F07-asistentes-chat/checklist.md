# Checklist F07

- [x] F06 aceptada PR83 con CI/revisión/postmerge.
- [x] Plan/tareas preparados antes de implementación; continuidad ADR0010.
- [ ] D-07 perfil LLM y retención decididos expresamente.
- [ ] Interfaz sustituible y mock determinista, con límites y errores privados.
- [ ] Una BD por tenant; conversación/asistente/citas solo con FK locales.
- [ ] ACL del usuario recalculada, enlaces de asistente sin concesión implícita.
- [ ] Historial propio y rechazo de UUID ajenos/cambios de contexto.
- [ ] Citas publicadas/autorizadas y abstención/contradicción evaluadas.
- [ ] Prompt injection no cambia política ni activa herramientas.
- [ ] Idempotencia/fallos/concurrencia sin mensaje o uso duplicado silencioso.
- [ ] Migraciones/roles/TLS/rollback/compatibilidad y originales conservados.
- [ ] >=30casos reales, cuatro fixtures, regresiones/privacidad/recursos.
- [ ] CI/revisión/integración/postmerge y aceptación antes de F08.

# Tareas F05

- [ ] T001 — D-06/ADR0011 y benchmark de perfil. R01; AC01/04. Propuesta concreta
  local384/cosine/512, pendiente Diego; no marcar aprobado por continuidad/silencio.
- [ ] T002 — Contrato provider/fake determinista y validación de lotes/perfiles/límites.
  R03/R05; AC01/03/04. Agnóstico a D-06; offline no red/descargas/keys.
- [ ] T003 — Esquema control/tenant/space/vector tipado y migraciones separadas.
  R02; AC01/02/04. Tras D-06; rollback/recovery/roles/TLS ambas topologías.
- [ ] T004 — Worker EMBED por lotes con idempotencia/retries/cuotas/usage.
  R03/R05; AC01/03. Crash y fallo parcial reales, sin texto/vector en control/logs.
- [ ] T005 — Publicación por versión+space, pointer/ancla original y reindexación.
  R02/R03; AC01/03/04. Completo atómico; baja/ACL/membresía bloquean tardíos.
- [ ] T006 — Servicio vectorial autorizado, exacto/HNSW y filtros vigentes.
  R04; AC02/04. Tenant/repo ajenos, same dimension/different model, exact-vs-ANN.
- [ ] T007 — Contrato de operación/HTTP previsto, manual y ejemplo real opt-in.
  R01..05; AC01..04. Sin anticipar asistentes/híbrida; fuente/pins/recursos reales.
- [ ] T008 — Aceptación cuatro fixtures/ambas topologías y regresiones F00..F04.
  R01..05; AC01..04. Logs/canary/temporales, CI/revisión/PR/merge/postmerge.

No cerrar turno por tarea/PR/fase. Seguir trabajo independiente de una decisión
pendiente; consultar solo criterios ADR0010. Conservar datos y evidencia.

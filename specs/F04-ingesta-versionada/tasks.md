# Tareas F04

Alcance original autorizado por ADR-0010; dependencia F03 aceptada en PR #34.
Cada tarea conserva evidencia y PR propio cuando el alcance lo requiera.

- [x] T001 — Plan/trazabilidad, resolución técnica D-05, corpus/límites y contratos.
  R01..06; AC-01..05. PR #35: cuatro checks de head, tres de merge, revisión delegada
  y docs/checkouts postmerge correctos.
- [ ] T002 — Cola durable control sin payload: lease/SKIP LOCKED, fencing, backoff,
  agotamiento, stop seguro; migración explícita aditiva y grants mínimos.
  R01/R04/R06; AC-01/03. Núcleo probado offline/PostgreSQL: dos procesos,
  SKIP LOCKED, caída, caducidad, backoff y ack/heartbeat tardíos. Activación, grants
  del runtime y parada del worker se completan con T005; T002 sigue abierta.
- [ ] T003 — Versiones de procesamiento/chunks/intención tenant, estados y tombstone;
  procedencia original inmutable, transacción/fencing y migraciones repetibles.
  R04/R05/R06; AC-01/03/04/05. Núcleo probado con 631 tests y cuatro fixtures SQL:
  migración repetida/procedencia/completitud/auditoría/roles/baja y rollback correctos.
  Perfil de logs probado con control positivo y canary ausente; activación persistente,
  login de runtime y carreras pendientes con T005/T006/T007. PR #38 integrado,
  CI/revisión/postmerge correctos; 13 tests postmerge y diez hashes exactos.
- [x] T004 — Corpus sintético nuevo, cuatro extractores y chunker determinista,
  sandbox de proceso, límites y errores saneados, NEEDS_OCR.
  R02/R03/R06; AC-02/03/05. Fixtures de páginas, tablas/títulos, Unicode/código,
  PDF escaneado/corrupto/cifrado, ZIP expansivo y timeout/memoria/salida.
  Componente implementado: 618 tests y contenedor sin red/secretos correctos;
  PR #37 integrado y postmerge correcto; cuatro checks de head/tres de merge,
  34 tests desde develop e imagen con diez hashes correctos.
- [ ] T005 — Worker y reconciliación de intención/cola, autorización vigente,
  recuperación tras crash/fencing y commit tenant antes del ack de control.
  R01..06; AC-01..05. Componente de intención/relay probado: 14 tests nuevos y
  cuatro fixtures SQL; ack perdido recupera un job. Worker, autorización global,
  fencing de commit y crash/parada pendientes. Ver worker.md; T005 sigue abierta.
- [ ] T006 — API F04 de versiones/jobs y tombstone, operación limitada, manual y
  errores/cursores sin contenido sensible en control/logs.
  R01/R04/R05/R06; AC-01/03/04. Negativas HTTP/ACL, revocación y parada/reinicio.
- [ ] T007 — Batería real ambas topologías y regresiones F00..F03; evidencia de todos
  los AC, logs/temporales/permisos, CI/revisión/merge/postmerge.
  R01..06; AC-01..05. No declarar cierre por tests offline ni marcar PUBLISHED
  sin embedding completo. Conservar originales/versiones/recursos.

No terminar el trabajo por completar un PR. Continuar siguiente tarea independiente;
consultar solo decisiones reales/desvíos/bloqueos bajo ADR-0010.

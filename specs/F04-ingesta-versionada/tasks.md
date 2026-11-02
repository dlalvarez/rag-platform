# Tareas F04

Alcance original autorizado por ADR-0010; dependencia F03 aceptada en PR #34.
Cada tarea conserva evidencia y PR propio cuando el alcance lo requiera.

- [x] T001 — Plan/trazabilidad, resolución técnica D-05, corpus/límites y contratos.
  R01..06; AC-01..05. PR #35: cuatro checks de head, tres de merge, revisión delegada
  y docs/checkouts postmerge correctos.
- [x] T002 — Cola durable control sin payload, lease/SKIP LOCKED, fencing/backoff,
  agotamiento y parada segura. R01/R04/R06; AC01/03. Núcleo/carreras PR36..41,
  activación/grants mínimos y SIGTERM/recuperación reales acreditados en PR42.
- [x] T003 — Versiones/chunks/intención/procedencia y tombstone tenant.
  R04/R05/R06; AC01/03/04/05. PR38..42: migración repetida/fallo DDL/rollback,
  recuperación/READY, logins app/readonly TLS/grants/logs y carreras reales correctos.
- [x] T004 — Corpus sintético nuevo, cuatro extractores y chunker determinista,
  sandbox de proceso, límites y errores saneados, NEEDS_OCR.
  R02/R03/R06; AC-02/03/05. Fixtures de páginas, tablas/títulos, Unicode/código,
  PDF escaneado/corrupto/cifrado, ZIP expansivo y timeout/memoria/salida.
  Componente implementado: 618 tests y contenedor sin red/secretos correctos;
  PR #37 integrado y postmerge correcto; cuatro checks de head/tres de merge,
  34 tests desde develop e imagen con diez hashes correctos.
- [x] T005 — Worker/reconciliación/autorización/fencing y commit antes del ack.
  R01..06; AC01..05. PR39..42, 675 tests; worker/S3/parser reales cuatro fixtures,
  crash/retry sin duplicados, A→B→A, SIGTERM/baja/ACL/membresía en ambas topologías,
  logs con controles positivos/canary ausente y temporales limpios. Ver evidencia.
- [x] T006 — API F04 de versiones/jobs y tombstone, operación limitada, manual y
  errores/cursores sin contenido sensible en control/logs.
  R01/R04/R05/R06; AC-01/03/04. PR #43:702 tests y HTTPS/SQL cuatro fixtures,
  readonly/ACL/cursor/cruces/jobs/bajas y rollback/recuperación reales correctos.
- [x] T007 — Batería real ambas topologías y regresiones F00..F03; evidencia de todos
  los AC, logs/temporales/permisos, CI/revisión/merge/postmerge.
  R01..06; AC-01..05. PR #44: regresiones reales F00..F03, SQL/S3/OIDC/historial,
  logs con positivo/canary ausente y temporales correctos; CI/revisión/postmerge.
  READY_FOR_EMBEDDING no es PUBLISHED; originales/versiones/recursos retenidos.

No terminar el trabajo por completar un PR. Continuar siguiente tarea independiente;
consultar solo decisiones reales/desvíos/bloqueos bajo ADR-0010.

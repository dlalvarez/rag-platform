# Tareas F02

Estado: planificación; ninguna implementación acreditada.
Dependencias y pruebas: [plan](plan.md), [checklist](checklist.md), [evidence](evidence.md).

- [ ] T001 — D-04 y entorno IdP de desarrollo: resolver ADR-0009; versión/digest,
  TLS, configuración, secretos y presupuestos. F02-R01; AC-03/04; V01/V07.
- [ ] T002 — Adaptador de access tokens y JWKS con límites/rotación y errores saneados.
  F02-R01/R05; AC-03/04; V01/V06.
- [ ] T003 — Migración control: identidad issuer+sub, membresías/tipos/roles y auditoría,
  constraints/grants/idempotencia. F02-R02/R04/R05; AC-01/03/04; V02/V04/V06.
- [ ] T004 — Administración CLI con bootstrap explícito, matriz de permisos y control
  concurrente del último owner. F02-R02/R04/R05; AC-01/03/04; V02/V04/V06.
- [ ] T005 — AuthorizedTenantContext y GET /me, /tenants, autorización antes de
  secretos/pools; paginación y denegaciones. F02-R02/R03/R04; AC-01/02/03; V03/V05.
- [ ] T006 — Integración real IdP/API/control, aislamiento en ambas topologías,
  suspensión/revocación/rotación y no filtración. F02-R01..05; AC-01..04; V01..07.
- [ ] T007 — Runbook, matriz/evidencia completa, revisión PR/CI y postmerge.
  F02-R01..05; AC-01..04; V01..07.

Orden T001→T002→T003→T004→T005→T006→T007; se permiten PR acotados.
No marcar una tarea por disponer de scaffolding. Una prueba esencial omitida
mantiene su AC abierto. No nuevas fases ni tareas de F03 como atajo de integración.

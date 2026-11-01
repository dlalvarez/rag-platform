# Tareas F03

T001: integrada en PR #27, develop@8530739dbc2cf5a067c5f67c6cc963ea2cc12d76; CI/postmerge correctos.
T002: identidad mínima instalada/probada; handoff/runtime pendiente.
T003: esquema y batería real preparados; CI/revisión/integración pendientes.
T004..T007 pendientes; ningún AC documental acreditado aún.
[Plan](plan.md), [checklist](checklist.md), [evidencia](evidence.md).

- [x] T001 — Persistir continuidad ADR-0010 y formalizar plan/tareas/trazabilidad.
  R01..05; AC-01..04; V01..V07. Integrar PR documental y continuar.
- [ ] T002 — Credencial de aplicación mínima y conexión autorizada/versión conocida.
  R01/R02/R03/R05; AC-01/02; V01/V02/V06.
- [ ] T003 — Migración tenant aditiva, estado RECEIVED y restricciones/idempotencia.
  R01/R03/R04; AC-03/04; V03/V04/V07.
- [ ] T004 — CRUD repositorios y ACL por capacidad, paginación y auditoría.
  R01/R02; AC-01/02; V01/V02/V06.
- [ ] T005 — Streaming/MIME/tamaño/hash, objeto privado, recepción/reintento/compensación.
  R03/R04; AC-03/04; V03/V04/V06.
- [ ] T006 — Proxy de original autorizado y API con errores/cabeceras seguras.
  R02/R05; AC-01/02; V01/V02/V05/V06.
- [ ] T007 — Batería real ambas topologías, regresiones, evidencia/CI/revisión/postmerge.
  R01..05; AC-01..04; V01..V07.

Orden lógico: T001 primero; T002/T003 pueden prepararse independientemente cuando el
bootstrap de credenciales esté bloqueado. No saltar las puertas de runtime/integración.
Seguir sin confirmaciones rutinarias; consultar solo bajo condiciones de ADR-0010.

T002: bootstrap real completado por Diego y verificado por agente sin otra contraseña.
PR #29 serializa ventanas/baterías. Falta handoff/runtime; no usar bearer infra en API.
T003: esquema f03_tenant_0002 y batería final ambas topologías correctos; ver schema.md
y evidence.md. Integrar con CI/revisión/postmerge y continuar T004 sin pausa.

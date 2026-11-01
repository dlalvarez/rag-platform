# Tareas F03

T001: integrada en PR #27, develop@8530739dbc2cf5a067c5f67c6cc963ea2cc12d76; CI/postmerge correctos.
T002: identidad mínima instalada/probada; handoff/runtime pendiente.
T003: integrada en PR #30, CI/revisión/postmerge correctos.
T004: componente integrado en PR #31, develop@ea4554fb70425b3df61d9198aeb907e1216fec82; CI/postmerge correctos.
T005: componente y batería real correctos; CI/revisión/integración pendientes; T006/T007 pendientes. Ningún AC documental de API acreditado aún.
[Plan](plan.md), [checklist](checklist.md), [evidencia](evidence.md).

- [x] T001 — Persistir continuidad ADR-0010 y formalizar plan/tareas/trazabilidad.
  R01..05; AC-01..04; V01..V07. Integrar PR documental y continuar.
- [ ] T002 — Credencial de aplicación mínima y conexión autorizada/versión conocida.
  R01/R02/R03/R05; AC-01/02; V01/V02/V06.
- [x] T003 — Migración tenant aditiva, estado RECEIVED y restricciones/idempotencia.
  R01/R03/R04; AC-03/04; V03/V04/V07.
- [x] T004 — CRUD repositorios y ACL por capacidad, paginación y auditoría.
  R01/R02; AC-01/02; V01/V02/V06.
- [x] T005 — Streaming/MIME/tamaño/hash, objeto privado, recepción/reintento/compensación.
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

T004: ver acl.md y evidence.md; cuatro fixtures reales y 415 tests correctos.
PR #31 integrado con CI/revisión/postmerge; API documental aún no desplegada.

T005: ver receipt.md/evidence.md; 512 tests y batería real de cuatro fixtures correctos.
Componente de validación/recepción privada, diario durable,
recuperación y cuotas. Mantener abiertos los AC HTTP hasta T006/T007.

# Tareas F03

Implementación T001..T006 integrada y promovida en desarrollo; baterías T007 correctas.
Falta cerrar el PR T007 con CI/revisión/merge/postmerge antes de activar F04.
[Plan](plan.md), [aceptación](acceptance.md), [checklist](checklist.md),
[evidencia](evidence.md). Requisitos y criterios originales conservados.

- [x] T001 — Persistir continuidad ADR-0010 y formalizar plan/tareas/trazabilidad.
  R01..05; AC-01..04; V01..V07. PR #27 integrado con CI/revisión/postmerge.
- [x] T002 — Credencial de aplicación mínima y conexión autorizada/versión conocida.
  R01/R02/R03/R05; AC-01/02; V01/V02/V06. Bootstrap #28, lock #29 y handoff/runtime #33.
- [x] T003 — Migración tenant aditiva, estado RECEIVED y restricciones/idempotencia.
  R01/R03/R04; AC-03/04; V03/V04/V07. PR #30; repetición final con documentos presentes.
- [x] T004 — CRUD repositorios y ACL por capacidad, paginación y auditoría.
  R01/R02; AC-01/02; V01/V02/V06. PR #31 y HTTP #33, aceptación real T007.
- [x] T005 — Streaming/MIME/tamaño/hash, objeto privado, recepción/reintento/compensación.
  R03/R04; AC-03/04; V03/V04/V06. PR #32; caídas, SQL parcial, lease/fencing y cuotas.
- [x] T006 — Proxy de original autorizado y API con errores/cabeceras seguras.
  R02/R05; AC-01/02; V01/V02/V05/V06. PR #33 integrado/promovido; postmerge correcto.
- [x] T007 — Batería real ambas topologías, regresiones, evidencia/CI/revisión/postmerge.
  R01..05; AC-01..04; V01..V07. Baterías y 562 tests correctos; pendiente puerta del PR.

T002/T006: develop@be7643847f6e472ae9b1b5d3011d83d3f75b3260, cuatro checks de head y
tres de merge correctos, revisión delegada y API existente promovida con la misma imagen.
Sin reinicios de PostgreSQL/MinIO/OpenBao ni cambios de contraseña del operador.

T007 añade observadores reales, cruces SQL/S3, baja lógica con contenido, concurrencia
HTTP y ZIP expansivo; compara filas/objetos y conserva recursos. Regresiones F00/F01/F02
y T003 F03 correctas. Logs sin secretos/contenido y temporales cerrados.
Consultar acceptance.md/evidence.md para el alcance exacto y las limitaciones.

No terminar el turno al cerrar el PR: registrar postmerge y continuar planificación F04.
Consultar solo decisiones reales pendientes según ADR-0010, sin pedir otra aprobación
de trámite. No anticipar código dependiente de una decisión de arquitectura sin resolver.

F03 aceptada: [postmerge PR #34](https://github.com/dlalvarez/rag-platform/pull/34#issuecomment-6565126139). La puerta pendiente descrita arriba
quedó satisfecha en develop@4c5b8d3189b71dad6fbe6f2921cbd06b33754871.

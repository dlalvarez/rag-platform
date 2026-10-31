# Siguiente tarea Codex — validar y revisar T004

T001–T003 aceptadas e integradas mediante PR #9/#10/#11.
Base T004: develop@4593f3832dd601c0d2ca7424281397622eac923a.
Rama feat/F01-T004-provisioning-saga.
[Runbook](f01/T004.md), [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

T004 implementa P4/V05: journal, idempotencia, lock por tenant, propiedad por operación
y compensación sin borrar bases/buckets. Control 0004 y lock real ya comprobados.
Batería integral solicitada al operador; registrar solo resultados saneados,
comprobar metadatos sin leer valores secretos y vincular las fuentes exactas ejecutadas.
No asumir PASS de integración a partir de pruebas offline o de aprobación de T003.

Después: comprobar docs/lint/tests del HEAD, presentar PR para revisión humana.
No fusionar antes de aprobación explícita. Tras merge autorizado, verificar postmerge.
Solo después de aceptar T004 y autorizar continuar: T005, resolver y pools conforme P5/V06.

Conservar fixtures T002/T003 y nuevas T004, incluso FAILED/REVIEW. No limpiar recursos,
regenerar secretos, reinicializar OpenBao ni repetir prepare-storage.
Los tenants T004 solo pueden ser READY tras migración inicial y probes reales.
T006 conserva su alcance de migraciones generales, canary y dos instancias; T007 su CLI.
No F02 ni alta HTTP pública. Desarrollo y pruebas siempre en ragdev01, nunca local.

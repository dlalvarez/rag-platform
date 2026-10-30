# Siguiente tarea Codex — terminar y revisar F01 T002

T001 fue aceptada e integrada mediante [PR #9](https://github.com/dlalvarez/rag-platform/pull/9).
Checks docs/lint/tests y comprobación postmerge correctos. Develop de partida:
a1568375164627f4be2b10d0cb9285fab92ce685. No repetir aprobación de T001.

T002 está implementándose en feat/F01-T002-sql-isolation. Ver
[runbook](f01/T002.md), [plan](../specs/F01-aislamiento-provisionamiento/plan.md) y
[evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

1. Completar sql-check real con OpenBao desde la terminal de Diego. No pedir secretos.
2. Resolver cualquier fallo sin regenerar credenciales ni borrar recursos.
3. Registrar evidencia saneada; ejecutar regresión/CI del HEAD y revisar el PR T002.
4. Esperar revisión y autorización de merge. No avanzar T003 por iniciativa propia.

Solo SSH en ragdev01; no instalaciones/pruebas en Mac. No init/resume de OpenBao,
no root de runtime, no cambios a F00 ni template0/template1. No marcar tenants READY,
AC completos ni F01 cerrada por la entrega SQL parcial.

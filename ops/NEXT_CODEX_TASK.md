# Siguiente tarea Codex — revisión T007 y aceptación técnica F01

T001–T006 aceptadas mediante PR #9–#14. PR #15 propone T007 hacia develop.
[Manual](f01/T007.md), [evidence y matriz AC](../specs/F01-aislamiento-provisionamiento/evidence.md).

CLI create/show/check/retry/migrate completada. Clon limpio fijado en
/home/diego/proyectos/rag-platform-t007-clean-b60b912b,
commit b60b912ba195779e8e5fd340331dfd649c85403d.
152 tests, tooling frozen, imagen/fuentes verificadas y batería de operador: tres PASS.
Corroboración de metadatos y regresión F00 posterior correctas.
No repetir ensayos ni pedir contraseñas para registrar estos resultados.

Comprobar CI del HEAD final y presentar revisión de PR #15 y aceptación técnica de F01.
Esperar aprobación explícita antes de merge. Después de autorización: integrar en
develop, verificar checks/postmerge y registrar aceptación y cierre de Issue #7.
Mantener separada cualquier decisión de promoción develop→main, tag o inicio de F02.

Conservar el clon fijo como evidencia y los datos/fixtures/canaries/conflictos existentes.
No reinicializar OpenBao ni regenerar secretos ni borrar bases/buckets.
Desarrollo y pruebas exclusivamente en ragdev01. Backup/restore/HA/PITR no acreditados.

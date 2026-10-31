# Siguiente tarea Codex — validar T007 y proponer cierre F01

T001–T006 aceptadas mediante PR #9–#14.
Base T007: develop@bd79a4d12180df9d8af5fca9a7d848a8fd070020.
Rama feat/F01-T007-admin-cli.
[Manual](f01/T007.md), [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

CLI create/show/check/retry/migrate implementada. 152 pruebas offline y show real correctos.
Clon limpio validado en /home/diego/proyectos/rag-platform-t007-clean-b60b912b,
commit b60b912ba195779e8e5fd340331dfd649c85403d. uv frozen con Python del servidor,
152 tests/docs/lint/negativos, attach-existing e imagen construida desde esas fuentes correctos.
No copiar secretos/.venv/datos ni preparar/reiniciar servicios en el clon.
Pendiente cli-check desde ese clon en la terminal del operador, con una única autenticación OpenBao.
Registrar solo PASS/códigos y fuente exacta, no credenciales.

Completar matriz de AC/checklist/evidencias con resultados reales y CI del HEAD final.
Presentar PR hacia develop para revisión T007 y propuesta de aceptación global F01.
No fusionar ni cerrar Issue #7 antes de aprobación explícita; verificar postmerge.
Main/tag requieren decisión y PR separados. No iniciar F02 por iniciativa propia.

Conservar F00, datos F01, fixtures/canaries y conflictos ajenos.
No reinicializar OpenBao, regenerar secretos ni borrar bases/buckets.
Desarrollo y pruebas exclusivamente en ragdev01. Backup/restore/HA/PITR no acreditados.

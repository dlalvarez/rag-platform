# Siguiente tarea Codex — validar y revisar T006

T001–T005 aceptadas mediante PR #9/#10/#11/#12/#13.
Base T006: develop@290e381c3b6c4d4e1ef52a3e81e75ea96b3e818b.
Rama feat/F01-T006-migrations-isolation.
[Runbook](f01/T006.md), [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

T006 implementa P6/V01–V07: migración bloqueada en la conexión de Alembic,
reflejo verificado en control, segunda instancia y fixtures reversibles separadas.
postgres2 ya preparada/arrancada; NO repetir prepare-second. No reiniciar otros servicios.
Calibración real independiente completada; no acredita todavía aislamiento tenant.

Pendiente: isolation-check en la terminal del operador, con su contraseña OpenBao.
Dos baterías: A/B misma instancia y A2/B2 en dos instancias. Registrar solo PASS/códigos.
Son cuatro fixtures nuevas respecto de tareas anteriores; claves idempotentes estables.
Probar SQL/S3, saga/reintento, A2→B2→A2/destino equivocado, rollback y lock con dos procesos.
Conservar canaries, bases, buckets y roles de calibración sin limpiar/regenerar secretos.

Registrar fuentes exactas, resultados reales y CI del HEAD. Presentar PR para revisión;
no fusionar antes de aprobación explícita. Tras merge autorizado verificar postmerge.
Solo después de aceptar T006 y autorizar continuar: T007, CLI general y clon limpio.

Sin F02, usuarios finales, alta HTTP, datos de negocio ni nuevas dependencias.
No afirmar backup/restore/HA/PITR por tenant. F00, datos F01 y recursos ajenos intactos.
Desarrollo/pruebas siempre en ragdev01. F01 e Issue #7 permanecen abiertos.

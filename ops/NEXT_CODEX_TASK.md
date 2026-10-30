# Siguiente tarea Codex — revisar T002; después T003

T001 aceptada e integrada mediante [PR #9](https://github.com/dlalvarez/rag-platform/pull/9).
T002 implementada y batería real completada por Diego en
[PR #10](https://github.com/dlalvarez/rag-platform/pull/10); revisión/aceptación pendientes.
Código ensayado: 0b297240d15a1c1b5acd2cfc30581d3938de1aea.
[Runbook T002](f01/T002.md) y [evidence](../specs/F01-aislamiento-provisionamiento/evidence.md).

## Puerta actual

Comprobar docs/lint/tests del HEAD final, revisar diff/evidencias y esperar aprobación
explícita de Diego para merge. No auto-merge ni bypass. Mantener T002 abierta hasta
aceptación. Después de merge autorizado, sincronizar develop y comprobar postmerge.

## Tarea posterior, sin autorización de ejecución por este documento

Solo tras aceptar T002 y autorizar continuar: F01 T003, conforme P3/V03/V04.
Validar MinioAdmin ya fijado, crear bucket/principal/política privados por tenant
y guardar secretos versionados en OpenBao; control conserva referencias opacas.
Probar acceso propio y denegaciones get/put/list A↔B y anónimo con credenciales reales.
Nueva rama/PR hacia develop, sin fusionar automáticamente. No implementar saga,
resolver, pools o fases posteriores en esa entrega.

Solo SSH en ragdev01; no instalaciones/pruebas en Mac. Conservar F00, bases/roles/KV
y la fixture ajena. No init/resume de OpenBao, secretos por chat, DROP, limpieza de
recursos ni rotación para reparar errores. Los tenants siguen PROVISIONING:
sin READY ni cierre de AC/F01 por esta entrega SQL parcial.

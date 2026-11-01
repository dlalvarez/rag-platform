# Siguiente tarea Codex — F02 identidad y membresías

Diego pidió continuar las actividades del plan con revisión/integración autónoma,
sin confirmaciones rutinarias. F01 sigue aceptada. El próximo paso del roadmap es F02.
Leer [spec](../specs/F02-identidad-membresias/spec.md),
[plan](../specs/F02-identidad-membresias/plan.md),
[tareas](../specs/F02-identidad-membresias/tasks.md) y checklist/evidence.

D-04 resuelta expresamente por Diego: Keycloak solo para desarrollo según
[ADR-0009](../docs/adr/0009-development-oidc.md), proveedor de producción sin decidir.
Ejecutar T001..T007 en PR acotados a develop con revisión delegada ADR-0007,
CI, evidencia real y postmerge, sin nuevas preguntas rutinarias.
T001..T004 integradas en PR #20..#23 con CI y postmerge.
T005 implementada y ensayada: contexto firmado/revalidado, API TLS de mínimo privilegio,
GET /me y /tenants con paginación y negativos. Revisar/integrar PR T005 y continuar T006
con contadores reales SQL/S3 y ambas topologías; después T007, evidencia/aceptación.
No detenerse entre tareas ni pedir confirmaciones rutinarias; continuar hasta completar
F02, salvo bloqueo real o desvío de los contratos/specs.
No confundir discovery/JWKS de T001 con validación de tokens o aceptación de F02.

Toda ejecución y dependencias en ragdev01. El archivo de autorización diaria desapareció
del runtime de usuario; daily status rechazó su uso. Se habilitó loginctl Linger=yes
para diego, sin cambiar TTL/permisos o reiniciar Bao. Se pidió reemisión con
`python3 scripts/f01_host.py run --rm daily start` en terminal del operador.
No pedir contraseña en chat ni repetir configure/root/unseal. Verificar status/canary
antes de T006; sin bearer válido continuar preparativos offline, no simular integración.
No renovar automáticamente ni revocar el día al terminar. Clave/token anterior no
recuperables desde el archivo perdido; podrían seguir válidos en Bao hasta TTL original.

Conservar F00/F01, sus servicios/datos y clon T007. No F03, main, tags, producción,
cambio de visibilidad o borrado de recursos. No cerrar F02 sin integración IdP real,
todos los AC y evidencia reproducible.

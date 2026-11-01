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
T001 implementada y ensayada con Keycloak 26.8.1 por digest, TLS, PostgreSQL propio
y presupuesto medido. T001 integrada en PR #20. T002 implementada y ensayada con tokens Keycloak reales,
rotación reversible y expiración real; revisar/integrar su PR con CI y postmerge.
T003 aplicada y ensayada en PostgreSQL real: migración aditiva, identidad issuer+sub,
roles/tipos/membresías/auditoría y grants mínimos. Revisar/integrar su PR y continuar
T004: CLI autenticada, bootstrap explícito y último owner protegido concurrentemente.
No detenerse entre tareas ni pedir confirmaciones rutinarias; continuar hasta completar
F02, salvo bloqueo real o desvío de los contratos/specs.
No confundir discovery/JWKS de T001 con validación de tokens o aceptación de F02.

Toda ejecución y dependencias en ragdev01. Sesión de pruebas de ADR-0008 activa
hasta 2026-11-01T21:34:19-05:00 según última verificación. Comprobar status antes de
usar la sesión; integrar el contexto diario sin leer el bearer en herramientas.
No pedir contraseña por batería, renovar automáticamente, revocar el día al terminar
o repetir configure. Si el servidor rechaza por vencimiento, informar el bloqueo real.
No guardar contraseñas, unseal o root; mantener custodia con Diego.

Conservar F00/F01, sus servicios/datos y clon T007. No F03, main, tags, producción,
cambio de visibilidad o borrado de recursos. No cerrar F02 sin integración IdP real,
todos los AC y evidencia reproducible.

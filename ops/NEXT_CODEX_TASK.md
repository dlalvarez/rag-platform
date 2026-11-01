# Siguiente tarea Codex — F02 identidad y membresías

Diego pidió continuar las actividades del plan con revisión/integración autónoma,
sin confirmaciones rutinarias. F01 sigue aceptada. El próximo paso del roadmap es F02.
Leer [spec](../specs/F02-identidad-membresias/spec.md),
[plan](../specs/F02-identidad-membresias/plan.md),
[tareas](../specs/F02-identidad-membresias/tasks.md) y checklist/evidence.

La planificación está preparada. D-04 (IdP concreto), abierta en docs/13,
tiene propuesta [ADR-0009](../docs/adr/0009-development-oidc.md): Keycloak solo dev,
sin proveedor de producción. Resolver esa decisión antes de instalar IdP o implementar
la fase; no presentarla como arquitectura aprobada por Diego sin su decisión.
Después ejecutar T001..T007 en PR acotados a develop con revisión delegada ADR-0007,
CI, evidencia real y postmerge, sin nuevas preguntas rutinarias.

Toda ejecución y dependencias en ragdev01. Sesión de pruebas de ADR-0008 activa
hasta 2026-11-01T21:34:19-05:00 según última verificación. Comprobar status antes de
usar la sesión; integrar el contexto diario sin leer el bearer en herramientas.
No pedir contraseña por batería, renovar automáticamente, revocar el día al terminar
o repetir configure. Si el servidor rechaza por vencimiento, informar el bloqueo real.
No guardar contraseñas, unseal o root; mantener custodia con Diego.

Conservar F00/F01, sus servicios/datos y clon T007. No F03, main, tags, producción,
cambio de visibilidad o borrado de recursos. No cerrar F02 sin integración IdP real,
todos los AC y evidencia reproducible.

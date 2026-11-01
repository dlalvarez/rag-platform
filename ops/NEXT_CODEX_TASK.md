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
T005 integrada en PR #24 con CI/postmerge: contexto firmado/revalidado, API TLS de
mínimo privilegio y GET /me, /tenants. T006 preparada en feat/F02-T006-isolation:
reconstruir herramientas tras cualquier ajuste, comprobar daily status/verify y ejecutar
isolation. Revisar/corregir resultados reales y restauraciones antes de merge; no
marcar por disponer del harness. Después T007, evidencia/aceptación.
No detenerse entre tareas ni pedir confirmaciones rutinarias; continuar hasta completar
F02, salvo bloqueo real o desvío de los contratos/specs.
No confundir discovery/JWKS de T001 con validación de tokens o aceptación de F02.

Toda ejecución y dependencias en ragdev01. Diego reemitió el día con vencimiento
2026-11-02T06:38:16-05:00; daily verify confirmó canary real en otro proceso SSH.
Linger=yes conserva runtime tras logout, sin persistir bearer en disco tras reboot.
Comprobar status/verify antes de usarlo; no renovar/revocar automáticamente, pedir
password por batería ni repetir configure/root/unseal. La autorización anterior
perdió su archivo; no se afirma que fuera revocada antes de su TTL original.
T006 pasó la batería completa en ambas topologías tras corregir rechazos libpq, probe
SQL operativo y keepalive del driver. Revisar/integrar PR #25 con regresiones/CI y seguir
T007: matriz final, runbook y aceptación técnica delegada; sin iniciar F03 ni main.

Conservar F00/F01, sus servicios/datos y clon T007. No F03, main, tags, producción,
cambio de visibilidad o borrado de recursos. No cerrar F02 sin integración IdP real,
todos los AC y evidencia reproducible.

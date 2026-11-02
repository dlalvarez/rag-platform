# Tarea activa Codex — cierre F04 y plan F05, continuidad autónoma

AGENTS/ADR0010: no terminar turno por PR/tarea/fase. Solo consultar decisión real,
desvío/stop condition o bloqueo externo; todo código/tests/build/servicios en ragdev01.
Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T007-acceptance, PR #44.
Base develop6398c62100327b4fbf21716f07d5fdcc12793308, T006 PR #43 aceptada/postmerge.

## Primera actividad

F04 T001..T007 técnicamente completas; evidencia real y matriz acceptance.md actualizadas.
Terminar CI/revisión/merge/postmerge PR #44. No aceptar fase por documentos solo: comprobar
tres checks del merge, checkout limpio, docs/regresión pertinente y hashes exactos.
Después preparar plan/tareas F05 ORIGINAL desde spec/roadmap/docs rectores, sin pedir
confirmación rutinaria. Revisar D06 modelo/dimensión bajo gobernanza; si requiere decisión
arquitectónica humana preparar propuesta concreta antes de consultar, seguir independiente.
No implementar F05 antes del postmerge F04 ni inventar elección de modelo/dimensión.

## Evidencia conservada

PR42 T002/T003/T005 aceptada; PR #43 T006 aceptada y postmerge correcto(67 tests/69 hashes).
702 tests del baseline completos y CI. PR #44 QA no cambia runtime/migraciones/dependencias/grants.
Head50129ca23cd2a4605314d9c92140345f563be72d, cuatro checks/revisión, regresión real
SQL/TLS/vector/roles/readonly/CONNECT+SET ROLE, S3 propio/cruzado y privacidad en cuatro
fixtures. OIDC/negativas y originales F03 SHA/ACL/version_id, sin ingesta retroactiva.
Clasificador libpq startup sin SQLSTATE corregido solo QA con firmas EXACTAS F01;
fallo de transporte S3 no contó como denegación; repetición COMPLETA mismohead terminó0.
Logs PG/PG2 con LOG+ERROR positivos y canarios ausentes, también API/MinIO/Bao;
worker retenido exit0/cuatro RO y API sin temporales/FD de spool. Ext4 más10GiB libres.
Sin backup/restore/SLA acreditados; OCR NEEDS_OCR, no PUBLISHED ni embeddings.

F00 nuevo run4b7e0b1d-7326-4c35-bbf8-5a7ccf5294ed: seed/verify procesos separados,
SQL/vector/S3/API correctos; tabla f04_regression_UUIDhex y bucket f04-regression-UUIDhex
retenidos. Fixture vieja f00_probe ausente por limpieza documentada original, no pérdida.

T006 runa75adb4c-445c-46d6-98ab-c558a8308112:
dir /home/diego/proyectos/rag-platform-f04-api-runs/a75adb4c445c46d698abc558a8308112
env /tmp/f04-api-qa-a75adb4c445c46d698abc558a8308112.env
20 originales/4repos;12 READY/4 NEEDS_OCR/4 TOMBSTONED, luego bajas de cuatro resultados
positivos retienen chunks. Cuatro checkpoints verified, ACL Bob restaurada.
No reseed/repetir verify esperando documentos ya tombstoned ni editar checkpoints.
T005 run15bbc3e9 y fallido cfe3...retenidos;52 originales/historial/tombstones y ACL/membresía
restauradas. Cuatro tenants READY f04_tenant_0003, cola f04_control_0006; no repetir adopción.
API t006 activa/siete RO; worker t006 parado limpio; QA tools:t007/siete mounts, solo journal RW.

## Acceso y límites

Sesión diaria hasta2026-11-02T06:38:16-05:00=11:38:16UTC; no renovar/exportar bearer/
password/root/unseal por iniciativa. Entregas API/worker separadas TTL1h, ensure si
caducó y replace tras cierre normal; tras crash ensure conserva vigente. Sin emisores
del día en paralelo ni consumer.lock compartido. Host --f02-env del checkout operativo.
Venv externo f04-parser-venv, PYTHONPATH=src; no ejecución/dependencias en Mac.
Logs brutos solo VM, PASS/códigos cerrados. No editar script mientras tenga bind activo.

Conservar originales/current_version_id/historial/chunks; sin purge/downgrade/main/tag/
producción/visibilidad. No atribuir revisión independiente o aprobación personal nueva;
seguir revisión delegada CI/PR/postmerge. Después del cierre F04 seguir F05 plan original.

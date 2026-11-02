# Tarea activa Codex — F04 T007, continuidad autónoma

No cerrar turno por tarea/PR/fase. AGENTS/ADR0010: consultar solo decisión real/desvío/
bloqueo que requiera intervención; ejecutar código/tests/build/servicios en ragdev01.
PR42 aceptado, develop4405f848546ebccd2203f902e9032ab88a770ea9, CI/postmerge correctos.

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T006-document-api,
PR43. T006 REAL completada:702 tests, cuatro checks de los heads de código, revisión
delegada previa, tres imágenes t006 con69 módulos exactos, API siete RO y worker cuatro RO.
Ingreso atómico/replay/rollback y recuperación, veinte envelopes (12READY/4NEEDS_OCR/
4TOMBSTONED), HTTP versiones/jobs/readonly/ACL/cursores/cruces/baja repetida con chunks
retenidos, A→B→A ambas topologías. Evidencia/correcciones de lanzamiento documentadas.
No nuevas migraciones/dependencias/permisos ni runtime cambiado después de revisión.
Primera actividad: finalizar CI/revisión/merge/postmerge PR43 y aceptar T006, luego T007
sin pausa rutinaria. F04 todavía abierta; no empezar implementación F05 antes de aceptación.

## T007 pendiente

Regresión real F00 solo lecturas (salud API/MinIO, vector SELECT y fixture persistente),
F01 SQL/S3 propios/cruzados con credenciales limitadas, F02 identidad/membresía/negativas,
F03 CRUD/ACL/upload/original/historial con perfil F04 conocido. Reutilizar evidencia
real sin fingir ejecución de scripts antiguos que rechazan correctamente head futuro.
Completar logs/canary/temporales/fingerprints y mapeo AC, CI/revisión/PR propio/postmerge.
No aceptar por offline solo ni omitir gate esencial. T006 ya da HTTP y baja de cuatro
fixtures y esquema/permisos; pruebas T002..T005 y controles F00..F03 previos permanecen.
No repetir seed/migraciones/fixtures terminales ni borrar recursos.

## Estado operativo y recursos

API YA es rag-f04-api:t006, perfil F04 con F03 conservada; entrega limitada renovada
por ensure al caducar TTL1h, sin password/día nuevo. Solo API fue recreada, IDs de datos/
IdP/Bao conservados. Worker normal t006 está detenido limpiamente tras el run.
T006 run a75adb4c-445c-46d6-98ab-c558a8308112:
dir /home/diego/proyectos/rag-platform-f04-api-runs/a75adb4c445c46d698abc558a8308112
env /tmp/f04-api-qa-a75adb4c445c46d698abc558a8308112.env
Manifest/checkpoints cuatro verified privados, veinte originales/cuatro repos retenidos.
No repetir seed ni verify esperando positivos ya tombstoned; checkpoints acreditan
los prechecks y baja final. ACL Bob restaurada; originales/chunks/historial retenidos.
Servicio QA se llama f04-api-check; api-check es F02 histórico con otros mounts.
Normal qa siete mounts y solo journal RW, sin día/admin/migrator.

T005 run15bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3 y fallido cfe3... retenidos,
52 originales/resultado/historial; bajas conservadas, ACL/membresía restauradas.
Cuatro tenants fijos READY f04_tenant_0003, cola f04_control_0006; no repetir adopción.
No cambiar current_version_id ni marcar PUBLISHED. No purge/downgrade/main/tag/prod/visibilidad.

## Acceso

Día hasta2026-11-02T06:38:16-05:00=11:38:16UTC. Reusar sin password/exportar bearer,
renovar día/root/unseal. Entregas API/worker separadas TTL1h: ensure si caducó; cierre
normal revoca app, replace antes del siguiente consumidor, tras crash ensure conserva
vigente. No emisores del día en paralelo ni consumer.lock compartido.
Host --f02-env /home/diego/proyectos/rag-platform/.env.f02. Venv externo f04-parser-venv,
PYTHONPATH=src. Logs brutos solo VM, PASS/códigos. No editar QA mientras haya bind activo.

Tras aceptar F04 con CI/revisión/postmerge, preparar plan F05 original y revisar D06
modelo/dimensión bajo gobernanza; decisión de arquitectura real puede requerir Diego.
Mientras no exista ese bloqueo, continuar trabajo independiente sin pausa de trámite.

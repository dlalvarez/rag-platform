# Tarea activa Codex — F04 T007 aceptación final

Continuidad autónoma AGENTS/ADR0010: no cerrar turno por PR/tarea/fase; solo consultar
decisión real/desvío/bloqueo externo. Todo código/tests/build/servicios en ragdev01.
Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T007-acceptance.
Base develop6398c62100327b4fbf21716f07d5fdcc12793308, PR43 T006 aceptado y postmerge
correcto: tres checks,67 tests API/F03 y69 módulos exactos en tres imágenes/checkouts limpios.
F00..F03 y T001..T006 aceptadas. F04 sigue abierta hasta T007 completo.

## Primera actividad

Publicar/CI/revisar preparación T007 y construir tools:t007; comprobar script SHA y
perfil f04-regression-check (siete mounts, solo journal RW, sin día/admin/migrator).
Ejecutar regresión limitada SQL/S3/OIDC/historial F03 y privacidad usando run T006
a75adb4c-445c-46d6-98ab-c558a8308112 ya retenido. Env:
 /tmp/f04-api-qa-a75adb4c445c46d698abc558a8308112.env
Dir:
 /home/diego/proyectos/rag-platform-f04-api-runs/a75adb4c445c46d698abc558a8308112
No seed/repetir verify T006 ni borrrar checkpoints. API T006 activa, worker parado exit0.
Antes del QA asegurar API app (TTL1h) y replace worker app (cierre previo revoca).

F00 regresión en imagen/red histórica smoke: scripts/f04_f00_check.py montado RO,
modo seed --run UUID NUEVO y luego verify en segundo proceso. Usar f00_compose.py
--env-file /home/diego/proyectos/rag-platform/.env run --rm -T --no-deps --entrypoint python
--volume ABS_SCRIPT:/checks/f04_f00_check.py:ro smoke /checks/f04_f00_check.py MODE --run UUID.
Conservar nueva tabla/bucket/objeto. Fixture antigua f00_probe ausente porque smoke clean
original la retiró (evidencia F00 líneas55..75); no reconstruirla ni fingir persistencia.

Después de regresiones pasar logs PG/PG2 con LOG+ERROR positivos F04_T007_LOG_POSITIVE
y canario F04_API_PRIVATE_CANARY ausente; también API/worker/MinIO/Bao sin canario.
No sacar logs brutos del servidor. Completar temporales/FD/fingerprints y matriz AC,
CI/revisión/PR final/merge/postmerge y aceptar F04 solo con todas las puertas.
Seguir F05 plan original después, sin detenerse por cierre del PR.

## Estado conservado y acceso

T006:20 originales/4repos,12READY/4NEEDS_OCR/4TOMBSTONED; recepción/intención atómicas,
rollback/recovery, HTTP/ACL/readonly/cursor/cruces/bajas con chunks retenidos, A→B→A.
Checkpoints cuatro verified; ACL restaurada, pointers ORIGINAL/historial intactos.
T005 run15bbc3e9...52 originales y primer cfe3... retenidos; negativos terminales y
tombstones no repetir. Cuatro tenants READY f04_tenant_0003, cola f04_control_0006.
Datos/IdP/Bao no reiniciados; solo API t006 se recreó y worker t006 probó y se detuvo.

Día hasta2026-11-02T06:38:16-05:00=11:38:16UTC. No password/exportar bearer/renovar día/
root/unseal. Entregas app API/worker separadas una hora, ensure si caducó y replace
tras cierre normal; tras crash ensure conserva vigente. No emisores día en paralelo.
Usar --f02-env /home/diego/proyectos/rag-platform/.env.f02. Venv externo f04-parser-venv.
Sin PUBLISHED/embeddings/F05 antes de aceptación, main/tag/prod/visibilidad/purge/downgrade.
D06 modelo/dimensión F05 conserva decisión de arquitectura; avanzar independiente.

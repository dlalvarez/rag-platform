# Continuidad F05 — seguir controlEMBED/T004, no repetir adopción

PR45..50 integrados; develop2012ed1, CI/postmerge y23 pruebas checkpoints/perfil.
T001 capacidad adicional en feat/F05-T001-capacity-boundary: cuatro pasajes512,
63.601s/CPU85.608s/134.6%, RSS3774.2MiB; concurrencia rechazada y recuperada.
Cerrar CI/revisión/merge/postmerge de esta medición y SEGUIR control0007/EMBED.
No más repeticiones del benchmark sin cambio o fallo. T001/T002 completas en su
alcance; T003..T008 abiertas. No calidad de dominio/ANN/ACL por fixture semántico.

ACTUAL: cuatro tenants f05_tenant_0004 READY, un espacioQwen vacío por tenant.
API rag-f05-api:t003 activa HTTPS/healthF05,75 módulos SHA correctos, user1000/RO.
Worker anterior F04t006 detenido0; imagen rag-f05-ingestion:t003 preparada.
No resembrar ni repetir ventana: journal8f9a197defd04a3baacde6bac5a56886 conservado.
Regresión F01..F04 HTTP/SQL/S3 en4fixtures y logs con positivos sincanaries pasada.
Infraestructura/IdP/F00 IDs conservados; sin vCPU/contraseñas/políticas cambiadas.

T003 control0007: space_id/fingerprint paraEMBED, unicidades parciales INGEST y
EMBED/version+space, códigos cerrados, sin texto/vectores/control ni FK entre BD.
INGEST claim/fence y vistas/jobs ya filtran kind (PR49). Probar DDL rollback/replay
y convivencia sin mezcla, conservar históricos. Luego T004worker/usage/retry/fencing,
T005 publicación/ancla, T006 exact/ANN, T007ops, T008aceptación.
LoteQwen puede tardar63s: no validar contexto30s vencido; reautorizar tras inferir
y renovar lease/heartbeat entre lotes. No introducir servicio externo por iniciativa.

Qwen aprobado1024/coseno/L2, límite512/batch4, rev/hashes ADR0011.
Modelo y venv opcional en rutas documentadas qwen-local.md, sin red en inferencia.
Sesión diaria activa hasta2026-11-03T07:14:15-05:00; no exportar/renovar/revocar/root.
API entrega vigente; QAworker anterior consumida/revocada: replace antes de otra QA.
Todo ragdev01, preservar recursos; sin main/prod/visibilidad/purge. AGENTS/ADR0010.

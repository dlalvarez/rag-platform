# Continuidad F05 — compatibilidad preparada, adoptar con controles

PR45/46/47/48 integrados; develop108a385, CI/postmerge.
Qwen aprobado local1024/coseno/L2,2vCPU intactas. Benchmark ficticio no F06.
T003 fundación tenant0004 probada en rollback4 fixtures/ambas instancias.

feat/F05-T003-runtime-compat: perfil embeddings con head exacto, proof separado,
API/worker INGEST opt-in, claim/fence INGEST excluye futuros EMBED.
796 tests y builds API/INGEST correctos,75 módulos instalados SHA coinciden.
Completar CI/revisión/merge/postmerge y SEGUIR adopción controlada en PR separado.
Imágenes preparadas rag-f05-api:t003/rag-f05-ingestion:t003, NO desplegadas aún.
API vigenteF04t006/workerF04t006 detenido, fixtures aún tenant0003.
Mantener originales/chunks/objetos/roles/refs; no nuevos tenants ni downgrade.

Preparar snapshots, intentoDDL fallido=>FAILED/observedNULL real, recovery/repetición
bajo migración controlada, registro idempotente espacioQwen y rol/log/TLS. APIcompatible
preparada antes de adoptar: cierre de consumidor, replace identidad limitada DESPUÉS,
migración4 fixtures, inicio API F05; no infraestructura/IdP/Bao reiniciados.
Luego control EMBED sin que INGEST lo reclame, worker/publicación/consulta/aceptación.
T003..T008 siguen abiertas; no cerrar turno por PR.

Sesión diaria activa hasta2026-11-03T07:14:15-05:00; no exportar bearer/renovar/revocar.
Start rechazó copia vencida anterior; daily revoke verificó403 y retiró solo esa copia.
No pedir password por prueba/root/unseal. Todo en ragdev01. Sin main/prod/visibilidad/
purge. AGENTS/ADR0010: continuidad autónoma entre tareas/PR/fases con evidencia.

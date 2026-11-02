# Tarea activa Codex — F04 T006/T007, continuar sin pausa

AGENTS/ADR0010: no terminar turno por PR/tarea/fase. Solo consultar decisión real,
desvío/stop condition o bloqueo externo; ejecutar todo en ragdev01, nunca Mac.
PR42 aceptado/integrado develop4405f848546ebccd2203f902e9032ab88a770ea9, CI/postmerge correctos.

## Estado actual y primera actividad

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T006-document-api,
PR43 borrador. Head inicial26b92958ae2288e0e74dfec5c048767d54611bf7 tiene cuatro
checks y revisión previa. Contrato/API/recepción opt-in implementados,702 tests.
Tres imágenes t006 con69 módulos exactos; Tools debe reconstruirse tras ajuste QA final.
API T006 YA promovida, siete RO/TLS/health correctos; datos/IdP/Bao mismos IDs.
No volver a promover ni repetir seed/adopción. Historial T005 HTTPS reader cuatro
fixtures correcto después de ensure de app caducada, sin ampliar grants.

Run T006 a75adb4c-445c-46d6-98ab-c558a8308112:
dir /home/diego/proyectos/rag-platform-f04-api-runs/a75adb4c445c46d698abc558a8308112
env /tmp/f04-api-qa-a75adb4c445c46d698abc558a8308112.env
Seed COMPLETO: veinte originales/cuatro repos, intenciones automáticas, HTTP/replay/
readonly/ACL correctos. Rollback real tras candidato/intención y recuperación del mismo
original después de lease, sin duplicados, pasó cuatro fixtures. Manifest privado.
Worker normal T006 se está probando sobre veinte envelopes; confirmar salida/estados:
esperados doce NONE/READY,cuatro NEEDS_OCR,cuatro TOMBSTONED; conservar todo y stop limpio.

Primera actividad: publicar/CI/revisar dos asserts QA finales (pointer ORIGINAL y estado
terminal tombstone) y rebuild tools:t006. Tras worker/parada, reemplazar entrega worker,
ejecutar f04-api-check verify --run UUID con ambos envfiles/F02+api-check.compose.yaml.
Servicio se llama f04-api-check (api-check F02 es histórico y tiene otros mounts).
Verifica HTTP/jobs/cursores/ACL/cruces/baja y retención chunks; checkpoints predelete/
verified permiten reanudar verify. No editar/falsificar/borrar esos archivos.
Verificar estado final y logs/temporales, evidencia/CI/revisión/merge/postmerge PR43;
luego T007 regresiones F00..F03 y aceptación F04, sin pausa rutinaria.
F04 no está cerrada ni F05 autorizada por dependencia todavía.

## Recursos y límites

Cuatro tenants fijos READY f04_tenant_0003, cola f04_control_0006. Sin nueva migración/
dependencia/política Bao/root/password. Perfil F03 predeterminado conserva comportamiento;
reader sigue readonly sin ops. Control solo IDs/progreso; sin texto/paths/lease en API.
Run T00515bbc3e9-06dd-4cdb-ad15-1c9ab055d8d3 y primer run cfe3... retenidos,
52 originales/historial y ACL/membresía restauradas, tombstones conservados.
No repetir negativos/pausas terminales esperando nuevas etapas ni borrar fixtures.

Día hasta2026-11-02T06:38:16-05:00 (11:38:16UTC), no renovar/exportar bearer/root/unseal.
Entregas API/worker separadas TTL una hora: ensure si caducó; cierre normal revoca app
token, replace antes del siguiente consumidor. Tras crash ensure reutiliza aún vigente.
No ejecutar emisores que toman el día en paralelo ni compartir consumer.lock.
CLI hosts usan --f02-env /home/diego/proyectos/rag-platform/.env.f02.
No editar QA mientras esté en bind de contenedor. Logs brutos solo VM; PASS/códigos cerrados.
Venv /home/diego/proyectos/rag-platform-f04-parser-venv, PYTHONPATH=src.

Conservar originales/current_version_id/historial/chunks; sin PUBLISHED/embeddings,
main/tag/producción/visibilidad/purge/downgrade. Tras aceptación F04, preparar F05 original;
D06 modelo/dimensión mantiene gobernanza y decisión real cuando corresponda.

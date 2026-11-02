# F05 — adopción de fundación y compatibilidad, T003 parcial

Solo desarrollo ragdev01 y cuatro fixtures F03/F04 existentes. No nuevos tenants,
secretos, AppRole/políticas, cambios VMM/infraestructura ni publicación F05.
PR48 tenant0004/espacios y PR49 perfil explícito revisados, CI/postmerge correctos.
API/INGEST images75 módulos SHA coinciden; API anterior F04, worker anterior detenido.

## Preflight y journal

Directorio nuevo0700 propio de diego fuera del repo, RAG_F05_QA_ROOT hacia él.
activate.compose usa día vigente, dos bootstrap/control migrator/CA y journal;
identidad administrativa nunca se monta en API/worker.
Con f02 base y envF02+journal, activate-f05 preflight comprueba los cuatro targets,
logins app/readonly TLS/roles/logs, ausencia de jobs RUNNING, snapshots F04/control.
No DDL/secret writes ni recreación de servicios. Journal0600 con hashes/IDs, no textos.

## Ventana controlada

Tras CI/revisión del head exacto del controlador y preflight correcto:
detener solo API (worker ya detenido), esperar cierre, reemplazar entrega limitada
F03 mediante f03_runtime_host.py replace. No leer bearer ni compartir credenciales.
activate-f05 adopt ejecuta por fixture:
fallo real después deDDL22012 => FAILED/observedNULL, rollback físico comprobado;
recuperar/repetir migrate_spaces_controlled con target=head exacto;
registrar/repetir espacioQwen determinista por tenant/fingerprint, sin embeddings;
logins reales/TLS/logs/grants y snapshots de TODAS las tablas F04 intactos.
Identidades/jobs/otros tenants de control deben conservarse.
Reintento conserva journal y recursos, no sobreescribe checkpoints incompatibles.

Iniciar solo API con f02+handoffF03+ops/f05/api.compose.yaml, imágenes revisadas,
envfiles F02/F03 existentes. No rebuild implícito ni recreación de dependencias.
Worker INGEST F05 preparado, mantener detenido hasta una prueba explícita; no
arrancar el binario antiguo F04 contra catálogo F05 ni trabajos futuros EMBED.

## Regresión limitada

Emitir reemplazo de entrega worker después de cierre previo; identidad AppRole
existente solo12 refs. f05-regression-check usa runtime profile embeddings explícito,
reutiliza controles F01..F04 y manifest a75adb4c445c46d698abc558a8308112 conservado.
No resembrar ni exigir que positivos tombstoned sigan activos. Pruebas OIDC/API,
originales/SHA/ACL, SQLroles/TLS/cruces, S3 propio/cruzado y controles de privacidad.
Los mensajes T007 internos son regresión F04, no cumplimiento T007 deF05.
La QA no recibe día/migrator/bootstrap. Su cierre revoca solo su entrega worker.

F05 sigue abierta: controlEMBED, worker, publicación/ancla original, búsqueda y
aceptación completos siguen pendientes. Espacios vacíos no son documentos publicados
ni evidencia de calidad semántica/aislamiento vectorial.

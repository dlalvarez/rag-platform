# Plan de recuperación real con lotes pendientes

T004/T005/T008, F05-R03/R05 y AC-F05-01/03. Preparado antes de implementación.
Archivos previstos: scripts/f05_multibatch_corpus.py, overlay de corpus y pruebas
offline de determinismo/scope/cola; reutilizar controlador de recuperación existente.
No cambia API/tenancy/modelo/DDL/políticas ni elimina corpus anterior.

Crear explícitamente cuatro TXT ficticios nuevos, uno en cada repositorio de la
fixture API retenida, como alice autenticada. Cuerpo determinista: encabezado de
prueba pública y16textos del gold congelado repetidos6veces (~10KB).
SHA y UTF-8 conocidos, un bloque texto, configuración F04 vigente1024/128.
Antes de upload comprobar >4 y<=64chunks, y token gate real Qwen antes de intents
de recuperación. Solo estos documentos nuevos; sin barrido ni restaurar tombstones.

Nuevo journal0700 con run UUID/idempotency keys y checkpoints por documento; manifest
sin texto/credenciales con los4scopes exactos y case positive-txt. UploadHTTPS
201/replay200, originalSHA y actores verificados contra OIDC/control actuales.
Ingesta application-only con entrega F04 independiente y perfil publicación0006:
cola restringida a4tenant/document/version, relay explícito de sus4intents y worker
sin relay general. No recoger jobs anteriores ni arrancar consumidor EMBED normal.
Esperar4INGEST SUCCEEDED y chunks>4; conservar originales/S3/manifests.

Reutilizar scripts/f05_recovery_check.py con el nuevo manifest y journal de recuperación
distinto. Presupuesto de todos antes de requests, <=512tokens/chunk y<=64chunks.
same-a/two-a: os._exit86 tras primer batch persistido, sin publicación/pointer;
deben quedar lotes pendientes y resume debe ejecutar solo esos lotes.
same-b/two-b: hard exit tras publicación y antes de ACK, resume sin nuevas inferencias.
Lease15/heartbeat5/demoraQA35s prueban TTL30 y heartbeats reales, no latencia Qwen.
Cerca anterior rechazada, intento2SUCCEEDED, ledger prefix y consumo sin duplicados,
sin tercerclaim y publicación completa. Verificar HTTP SHA de los4originales al final.

Una copia Qwen por VM y ningún worker RPC/normal durante recovery. Preparar F03/F04/F05
solo con día vigente, consumidor cerrado y locks correspondientes; ensure reutiliza
entrega válida tras hard exit, replace después de cierre normal. No renovar día
automáticamente ni usar root/nuevas políticas. Si vence, seguir trabajo independiente
y requerir acción real del operador antes de nuevas entregas.

Herramienta QA de corpus sin bootstrap/migrator/día: identity_app, authority key,
OIDC fixture, TLS y entrega limitada F04 existente. API:t009 compatible y originales
conservados. Review/CI/merge/post antes de crear el corpus persistente nuevo.
Detener consumidores al finalizar; conservar imágenes/contenedores/journals/documentos.
No marcar recuperación parcial aceptada solo por las cuatro pruebas previas de un lote.

## Corpus y herramienta preparados
Cuerpo medido/congelado:11250bytes UTF-8,14chunks por documento,
SHA1d9098227dfd23dbc3ca57b624fcb8831c5a6241249458543e96715fe16037ec.
Catorce chunks implican4batches: tras guardar el primero quedan10chunks/3batches
en casos BATCH_COMMITTED. RESULT_COMMITTED debe haber guardado4batches.
Parser real texto/normalizador/chunker se comprueban offline antes del upload.

scripts/f05_multibatch_corpus.py y multibatch-corpus.compose.yaml tienen prepare/verify.
Scope base RAG_F04_BASE_QA_ROOT es el manifest APIa75adb4c445c46d698abc558a8308112.
RAG_F05_MULTIBATCH_QA_ROOT es un journal0700 nuevo. Imagen tools:t006 sin modelo,
source/scripts/corpus RO, OIDC/TLS/identity_app/authoritykey/F04handoff únicamente.
run --rm --no-deps --pull never f05-multibatch-corpus prepare con API compatible
activa y F04handoff nuevo limitado bajo lock. Nunca invoca Worker.run/relay general;
despacha exactamente sus cuatro intents y usa step con cola INGEST restringida.
INGEST puede crear intents EMBED PENDING automáticamente; no consumidor EMBED
normal. Verificar presupuesto real antes de despachar recuperación/inferir.
Después usar el manifest generado con recovery-check.compose.yaml existente,
journal de recuperación nuevo y F05handoff exclusivo. Verificar budgets14chunks/
4requests por fixture, ledger previo1request en cortes de batch y resume3requests.
Al terminar, modo verify de corpus comprueba4originales HTTP SHA/PUBLISHED sin abrir
runtime F04 ni requerir nueva entrega. Todos los documentos/journals se conservan.
No se ha creado todavía este corpus ni ejecutado recuperación multilote real.

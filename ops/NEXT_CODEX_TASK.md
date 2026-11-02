# Tarea activa Codex — F04, continuidad autónoma

Leer AGENTS/ADR-0010. No cerrar turno por tarea/PR/fase; seguir roadmap autorizado.
Consultar solo decisiones reales, desvíos/inconsistencias o bloqueo externo que requiera
intervención. Toda ejecución manual permanece en ragdev01, nunca en el Mac.

## Estado real y primera actividad

Worktree /home/diego/proyectos/rag-platform-f03-schema, feat/F04-T005-runtime-acceptance,
PR #42 borrador. Base develop e0b73e7f36fa1d73474df36f3e09deed64b9196c (PR41).
F00..F03 aceptadas. F04 componentes PR35..41 integrados con CI/revisión/postmerge;
675 tests, 43 postmerge y tres imágenes con 66 módulos src/instalados exactos.

ADOPCIÓN YA EJECUTADA desde PR42 head4df769eb41cb94cec1f101981b2da2267e3b4ccb,
con cuatro checks y revisión previa: las cuatro fixtures están F04 READY; fallo
DDL22012/rollback/FAILED honesto/recovery/repetición/TLS/roles/logs/snapshots correctos.
Cola pública instalada; control app solo SELECT/INSERT/UPDATE. Datos/identidades/
tenants previos y día conservados. NO repetir adopción ni promoción al recuperar contexto.

API actual rag-f04-api:t005, perfil F04 compatible con rutas F03; solo API recreada,
siete RO y HTTPS health F04 correcto. Entrega limitada reemplazada DESPUÉS del cierre
anterior. Datos/IdP/Bao no reiniciados. Todavía no worker normal ni endpoints T006.

Seed primer run cfe3a53d-09e7-4626-993c-641df19f8ca7 falló antes de recursos por
tmpfs /run/f02-auth ausente. Directorio conservado con solo started.json en
/home/diego/proyectos/rag-platform-f04-worker-runs/cfe3a53d09e74626993c641df19f8ca7.
No reutilizarlo ni borrarlo: seed crea started.json exclusivo. Corrección tmpfs 1MiB
0700 + cleanup ya implementada; smoke del helper OIDC real pasó en imagen reconstruida.

PR42 siguiente commit incluye ese arreglo, controlador scripts/f04_worker_check.py y
ops/f04/worker-check.compose.yaml. Cerrar CI/revisión/head/hashes y crear run QA nuevo
0700 fuera del repo con envfile solo RAG_F04_QA_ROOT. Reutilizar/emitir entrega del
worker con f04_runtime_host.py ensure desde día vigente; no pedir contraseñas.
Ejecutar seed-f04: nuevos originales HTTPS/replay/intenciones positivas explícitas.
Al terminar Runtime.close revoca esa identidad: replace ANTES del siguiente consumidor.

Después QA overlay: misma imagen rag-f04-worker:t005 y cuatro montajes limitados,
más script/manifiesto RO; sin día/admin/migrator/OIDC passwords. Modos positive,
request/process, crash/resume, dependency, pause-stop/tombstone/acl/membership.
Completar acciones externas controladas para las pausas; conservar todos los recursos.
Probar S3/parser/offsets/páginas/hash, replay, NEEDS_OCR/cifrado/fallo en segunda página,
crash tras commit antes de ack, retry/parada/revocación/baja, A→B→A y logs/temporales.
Evidencia real y CI/revisión final/merge/postmerge antes de aceptar T002/T003/T005.
No aceptar F04 ni avanzar F05 antes de T006/T007. No terminar por PR/hito.

## Límites, fuentes y acceso

Contratos schema.md/worker.md/runtime.md y ops/f04/adoption.md; docs04/05/07.
Versiones/jobs HTTP usarán rutas rectoras docs07 en T006. Sin PUBLISHED/embeddings
ni cambios a current_version_id, purge, downgrade, main/tag, producción o visibilidad.
No consumir indiscriminadamente documentos anteriores; solo manifiesto/run propio.

Sesión diaria hasta 2026-11-02T06:38:16-05:00. No exportar bearer, renovar/revocar día
ni repetir root/unseal automáticamente. AppRole existente de doce refs/cuatro fixtures,
entregas separadas de API/worker. Reemplazar aplicación después de revocación/cierre;
no compartir consumer.lock. No ejecutar en paralelo baterías que toman el día.

Venv /home/diego/proyectos/rag-platform-f04-parser-venv, PYTHONPATH=src; pytest/ruff.
No sincronizar venv operativo innecesariamente ni instalar nada local.
Datos originales F00..F03, colisiones T005 y repos DELETED conservados.
Corpus original F04 retenido en /home/diego/proyectos/rag-platform-f04-corpus.
Capturar registros privados solo en servidor, devolver PASS/códigos cerrados.

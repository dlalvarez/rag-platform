# Continuidad F05 — ledger/publicación ensayados, seguir runtime/worker

Develop2c65818 (PR55), cuatro checks previos y tres postmerge correctos.
PR52controlEMBED y PR53consumidor integrado;837 tests baseline. ModeloQwen aprobado
ADR0011/512/batch4, medición capacidad completada: no repetir sin cambio/riesgo.

Trabajo actual feat/F05-T005-publication-compat en worktree f03-schema.
tenant0006 ledger/lotes/usage/bindings, guards y wrapperspace explícito preparados;
ledger integrado PR55; compat0006/ancla ahora857passed40.68s,59focalizadas y SQL
original/replay/INGEST traspub4fixtures correctos. Cerrar CI/revisión
propia delegada/merge/postmerge. No atribuir revisión independiente.

Persistente: control f04_control_0006; cuatro tenants f05_tenant_0004 y espaciosQwen
vacíos.0007control y0005/0006tenant NO adoptados. APIF05t003 activa; workerF04 detenido.
No modificar servicios hasta compatibilidad y ventana revisada. Conservar journal
8f9a197defd04a3baacde6bac5a56886 y recursos/modelo/venvs/pesos/fixtures originales.

Perfil opt-in RAG_F05_PUBLICATION_ENABLED preparado, sin activar ni adoptar.
Siguiente workerEMBED real: relay/intents, lotes acotados/uso real,
heartbeat durante inferencia63s+, reautorizar contexto tras inferir (TTL30s), locks/fence
antes de tenant commit y ack posterior reconciliable. Pruebas crash/ACL/tombstone/
mismatch/cuotas y ambos topologías; luego búsqueda exacta/ANN, ops y aceptación.
No marcar T003/T004/T005 ni F05 completas con solo esquema o SQL sintético.

HTTP search: pendiente decisión Diego sobre concreción de docs07 sin assistant ni
generación F07. Propuesta /home/diego/proyectos/rag-platform-f05-search-contract-proposal.md.
Continuar trabajo independiente; no alterar contrato rector antes de respuesta.

Todo desarrollo/pruebas en ragdev01. SSHdesdeMacBatchMode/StrictHostKeyChecking.
GitHTTPS servidor sin auth: publicar con conector GitHub y verificar mismo SHAárbol
con git fetch, conservando ramas locales de prueba. No extraer tokens ni secretos.
Sesión diaria registrada hasta2026-11-03T07:14:15-05:00; comprobar estado/hora antes de
usar; no renovar/revocar/root por iniciativa. AppRoleworkerTTL1h requiere entrega
propia válida y sin consumidor con lock. Sin main/tags/producción/visibilidad/purge.
Seguir AGENTS/ADR0007/0010 autónomamente, sin pausas de trámite.

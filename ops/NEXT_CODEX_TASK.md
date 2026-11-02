# Continuidad F05 — ledger/publicación ensayados, seguir runtime/worker

Develop 9bf87f0 (PR57), cuatro checks previos y tres postmerge correctos.
PR52controlEMBED y PR53consumidor integrado;837 tests baseline. ModeloQwen aprobado
ADR0011/512/batch4, medición capacidad completada: no repetir sin cambio/riesgo.

Trabajo actual feat/F05-T007-worker-operations en worktree f03-schema.
tenant0006 ledger/lotes/usage/bindings, guards y wrapperspace explícito preparados;
ledger/compat integrados; worker código904passed58.62s,77focalizadas y SQL
componentes tenant/control correctos con rollback. PR57 integrado y postmerge correcto.
Entorno opcional/imagen/handoff preparados; 910 tests correctos. Cerrar revisión
propia/CI/merge/postmerge de la entrega operativa. No atribuir revisión independiente.

Persistente: control f04_control_0006; cuatro tenants f05_tenant_0004 y espaciosQwen
vacíos.0007control y0005/0006tenant NO adoptados. APIF05t003 activa; workerF04 detenido.
No modificar servicios hasta compatibilidad y ventana revisada. Conservar journal
8f9a197defd04a3baacde6bac5a56886 y recursos/modelo/venvs/pesos/fixtures originales.

Perfil opt-in RAG_F05_PUBLICATION_ENABLED preparado, sin activar ni adoptar.
Siguiente imagen/lock opcional y adopción revisada con workerEMBED real: relay/intents, lotes acotados/uso real,
heartbeat durante inferencia63s+, reautorizar contexto tras inferir (TTL30s), locks/fence
antes de tenant commit y ack posterior reconciliable. Pruebas crash/ACL/tombstone/
mismatch/cuotas y ambos topologías; luego búsqueda exacta/ANN, ops y aceptación.
No marcar T003/T004/T005 ni F05 completas con solo esquema o SQL sintético.

HTTP search: Diego aprobó expresamente el 2026-11-02 la búsqueda HTTP de fragmentos
en F05, sin assistant ni generación F07. Propuesta /home/diego/proyectos/rag-platform-f05-search-contract-proposal.md.
Registrar la aprobación en docs07/spec y concretar el contrato aprobado antes de implementarlo.

Todo desarrollo/pruebas en ragdev01. SSHdesdeMacBatchMode/StrictHostKeyChecking.
GitHTTPS servidor sin auth: publicar con conector GitHub y verificar mismo SHAárbol
con git fetch, conservando ramas locales de prueba. No extraer tokens ni secretos.
Sesión diaria registrada hasta2026-11-03T07:14:15-05:00; comprobar estado/hora antes de
usar; no renovar/revocar/root por iniciativa. AppRoleworkerTTL1h requiere entrega
propia válida y sin consumidor con lock. Sin main/tags/producción/visibilidad/purge.
Seguir AGENTS/ADR0007/0010 autónomamente, sin pausas de trámite.


Worker nuevo: requests explícitos; solo ingestas completadas bajo0006 crean intent
Qwen automáticamente. No barrer READY histórico. Cola con fingerprint del provider.
Quota64chunks/32768tokens de contenido persistido,3intentos; batch sincommit puede
repetirse. Stop180s antes de TTL o DENIED/INVALID; no auto-renew y nuevo handoff solo
tras consumidor cerrado. Fuente actual RuntimeSQL-only, sin S3 ni admin/día.
No declarar E2E por SQLite o guard sintético SQL. Leer ops/f05/embedding-worker.md.

Entorno preparado: ops/f05/embedding-operations.md. Imagen rag-f05-embedding:t004,
lock separado con pins compartidos sin deriva. Smoke sin red/credenciales/modelo,
90 módulos SHA iguales. Compose corregido/validado, ningún servicio iniciado.
Tools privadas prueban exclusión consumidor antes de día. Readonly sin SELECT
ledgers ops (SQL rollback). No entrega real emitida ni directorio real preparado.
Siguiente: controlador de adopción publicación/control0007 con journal nuevo,
conservando el journal previo, fuentes cerradas y snapshots; ensayarlo/revisarlo
antes de usar una ventana de cambio. No ejecutar f03_application_host configure.

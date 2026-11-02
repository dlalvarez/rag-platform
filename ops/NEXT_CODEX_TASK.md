# Continuidad F05 — controlador de publicación en revisión

Develop 2d15baf (PR59). PR58 8f8f113: cuatro checks previos y tres postmerge success.
PR59 registra la aprobación expresa de Diego de búsqueda HTTP de fragmentos en F05;
cuatro checks previos success, comprobar tres postmerge. No requiere otra decisión
sobre assistant_id/generación: request repository_ids/space_id/query/top_k y hits con
procedencia, similitud y uso embeddings, conforme a docs07. La ruta sigue sin habilitar.

Rama actual feat/F05-T005-publication-adoption-review en worktree f03-schema.
Controlador/composición/manual preparados. 925 tests (63.44s), 18 focalizados,
ruff/formato y dos preflights reales en cuatro fixtures/dos instancias correctos.
Journal nuevo privado fuera del repo:
 /home/diego/proyectos/rag-platform-f05-publication-adoption-runs/8d87357ea8c24100a1f25b6a14959751
Conservar también journal anterior 8f9a197defd04a3baacde6bac5a56886.
Preflight no ejecuta DDL; adopt completo aún no ejecutado. Cerrar revisión propia,
CI del HEAD exacto, merge y postmerge antes de usar la ventana de cambio.

Persistente: control f04_control_0006; cuatro tenants f05_tenant_0004 con único espacio
Qwen vacío. API F05t003 activa; worker F04 detenido y conservado. Ningún servicio
recreado ni entrega nueva emitida. Sesión diaria ACTIVE verificada el 2026-11-02,
vence 2026-11-03T07:14:15-05:00; comprobar estado/hora antes de usar, no renovar.
No root, configure, reinicios Bao, nuevas políticas, purgas, main/tags/producción.

Próximo paso: imágenes compatibles API/INGEST desde código revisado, hashes/smoke,
overlays opt-in publicación y QA de regresión del perfil embedding_publication.
EMBED rag-f05-embedding:t004 ya preparado, lock opcional separado y smoke90 módulos,
sin inferencia del modelo. Ver embedding-operations.md y publication-adoption.md.
Con CI/revisión y preflight, ventana limitada: cierre de consumidores/conexiones/locks,
adopt control0007/tenant0006, fallo22012/FAILED/rollback/recuperar/repetir, snapshots,
handoffs independientes válidos sin consumidor activo e inicio solo de servicios
revisados. No autoarranque de dependencias ni remove-orphans.

Después probar worker Qwen real/usage, inferencia larga y reautorización TTL30s,
heartbeat/fences, crash entre commits control/tenant independientes, retomar parciales,
originales HTTP/S3 postpublicación; luego búsqueda exacta/ANN/HTTP/ACL y aceptación.
Solo nuevas ingestas0006 crean intent Qwen; historia READY requiere request explícito.
No barrer corpus histórico ni repetir benchmark de capacidad sin cambio/riesgo.
Cuota64chunks/32768tokens persistidos/3intentos; lote perdido sin commit puede repetirse.
Stop180s antes de token expirado/DENIED/INVALID, sin auto-renew. Conservar recursos.

T003..T008 y F05 abiertas; SQL sintético/SQLite/smoke/preflight no acreditan E2E.
Todo ejecución/dependencias en ragdev01, Mac solo SSH/documentos. Seguir AGENTS y
ADR0007/0010 autónomamente, sin detener por PR ni pedir confirmaciones rutinarias.
Git push servidor sin auth: conector GitHub, transferencias pequeñas y SHA árbol igual
al probado ANTES crear commit. Conservar ramas locales de prueba; no reset destructivo.

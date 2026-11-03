# Continuidad F05 — HTTP verificado; ANN en revisión

Developdae8a0e (PR70), checks HEAD/postmerge correctos.
Aprobaciones Qwen/HTTPfragmentos/adopciónBD/conexiónprivada vigentes; no repetir.
Control0007/cuatro tenants0006/Qwen publicados. No repetir adopción.

API rag-f05-api-search-t009 activa con fuente0cb18d6,98hash/importPASS/noTorch.
t006 detenida preservada; nunca iniciar t003 contra0006.
EntregaF03 vence~2026-11-03T11:02UTC: comprobar, detener consumidor y tomar lock
/run/user/1000/rag-f03-application/consumer.lock antes de reemplazar.
Día vigente hasta07:14:15-05:00 (12:14UTC); no renovar/root/configure/políticas/Bao.

HTTP QA e178b6f57f514af9bbbdcb9a7327ab5b VERIFIED4fixtures/4requests/8originalSHA.
API/worker corpus usan repositorios distintos por tenant: fix PR69 conserva ambos
scope explícitos y procedencia triple. Primer journal83d8... START rechazado retenido.
RPC bec5dbc5efaf44d2b408a13c80e270f8 PASS4/4requests92tokens/0denegados.
Log contrastado:4RPC+4HTTP cálculos, ninguno en denegaciones.
Qwen rag-f05-embedding-query-t008 cerró limpio exit0/noOOM10:44:43UTC por margen
previo a handoff10:47; no reemitir para SQL ANN que no necesita modelo.
Imagen/contenedor t008 y t004 conservados, una sola copia Qwen cuando se arranque.

Recuperación journalb6e1cd49609c4f6e8b8de8f06ff2f268 cuatrocasos COMPLETE/SUCCEEDED,
intento2/0reinferencias/originalretenido. Ahora HTTP SHA también verificado.
Un lote por caso: recuperación parcial multilote todavía pendiente.

Worktree feat/F05-T006-ann-retrieval con WIPf888933/a1779ee y merge local de PR69.
Servicio HTTP sigue exacto. Nuevo componente,17unit,hook QA exacto opcional y
ann-check.compose.yaml preparados. Plan/manual ann-retrieval.md; sin nuevo DDL/deps.
50focalizadasPASS8.86s; fullsuite con journal persistente8de78fe606274b42b08d624fa8af03b4
en /home/diego/proyectos/rag-platform-f05-check-runs, leer result.json/pytest.log
si seguimiento SSH pierde salida. Resultado persistido exit0:1103passed85.92s, head21e57605; warning heredado.
Después revisión/PR/CI/merge/postmerge y QA SQL nativa con rollback4fixtures,
vectores sintéticos, filtros selectivos y EXPLAIN HNSW elegible. No activación ANN
hasta QA; luego calidad Qwen/SQL ES/EN sobre corpus congelado y recuperación multilote.
No repetir benchmark capacidad. T003..T008/F05 siguen abiertos.

Todo ejecución en ragdev01, Mac solo SSH/documentos. GitHub fuente verdad, árboles
idénticos al probado, ADR0007 revisión propia explícita y CI exacto/postmerge.
Seguir al cerrar PR; solo detenerse por decisión real o dependencia externa.

Actualización ANN: prueba nativa inicial no demostró índice (INDEX_PLAN), filtros
pasaban. Fix EXISTS correlacionado/OFFSET0 probado en journalb678c50d... exit0:
cuatro planes/ejecuciones HNSW/comparación exacta/filtros/negativos/rollback PASS.
Rama fix/F05-ann-index-filter todavía sin PR;50focalizadas9.27s y fullsuite
790076754ea047abb47b29a4a0655e06 exit0:1103passed88.47s. CI/merge/post antes
de usar esta corrección en siguiente QA integrada. HTTP sigue exacto.
API t009 y trabajador Qwen están detenidos limpiamente, imágenes/contenedores
conservados; no reemitir handoffs para SQL. Día no renovar.
Plan sql-quality.md todavía sin implementación, excluir de PR de fix: corpus
congelado/Qwen precomputado antes de SQL, vectores solo memoria, uso real global
20llamadas separado de ledgers temporales sintéticos. No repetir capacidad.

# Continuidad F05 — transporte privado en revisión

Develop becfaebb (PR66), checks previos/postmerge correctos. Adopción control0007/
cuatro tenants0006 completa; no repetir adopción con espacios ya publicados.
Aprobaciones vigentes: Qwen, HTTP de fragmentos, actualización BD de prueba y
conexión privada al trabajador Qwen. No volver a pedirlas.

Recuperación REAL journal b6e1cd49609c4f6e8b8de8f06ff2f268 completada en cuatro fixtures:
dos cortes BATCH_COMMITTED y dos RESULT_COMMITTED, intento2 SUCCEEDED,
cero inferencias repetidas y originales retenidos. Un lote por caso; no acredita
multilote pendiente. Journal worker15bbc, corpus positivo-txt activo, no barrido.

Worktree feat/F05-T007-query-transport sobre becfaebb, todavía sin PR/despliegue.
ADR0012 y manual specs/F05-embeddings-vector/private-query.md. Transporte Unix,
gate compartido, backend/client/server, flag opt-in y overlays/QA preparados.
Revisar/tests completos/CI/merge/postmerge antes de construir imagen t008 y arrancar.
Conservar t004 y contenedores antiguos; una sola copia Qwen por VM.
API compatible t006 activa, su entrega limitada probablemente vencida:
detener consumidor y tomar lock /run/user/1000/rag-f03-application/consumer.lock
antes de reemplazar con día vigente. Nunca iniciar API t003 contra0006.

Día comprobado ACTIVE el 2026-11-03 ~09:39UTC, vence 07:14:15-05:00 (12:14UTC).
Comprobar antes de emitir; no renovar/root/configure/políticas/reinicios Bao.
F05/QA anteriores cerrados; comprobar locks antes de nuevas entregas.
Todo ejecución/dependencias/modelo en ragdev01; Mac solo SSH/documentos.
GitHub fuente de verdad, ADR0007 revisión propia explícita, CI de HEAD y postmerge.

Siguiente: cerrar revisión/tests y PR transporte, luego build/hash/import smoke,
preparar socket tmpfs y entrega F05, un único nuevo trabajador opt-in, QA RPC
cuatro fixtures y trazas/uso/denegaciones sin texto/vector. Después HTTP autorizado,
regresión/original HTTP-SHA, ANN/exacto/calidad SQL ES/EN y recuperación multilote.
No marcar T003..T008/F05 aceptadas antes de evidencia. Continuar al cerrar cada PR.

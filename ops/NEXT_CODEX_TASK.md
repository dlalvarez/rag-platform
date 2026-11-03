# Continuidad F05 — HTTP en revisión

Develop80bf466 (PR67) con cuatro checks HEAD/tres postmerge correctos.
Aprobaciones vigentes de Diego: Qwen, búsqueda HTTP de fragmentos, adopción BD
de prueba y conexión privada al trabajador. No volver a pedirlas.
Control0007/cuatro tenants0006 listos, Qwen publicado: no repetir adopción.

Recuperación real journal b6e1cd49609c4f6e8b8de8f06ff2f268 completada cuatro casos:
BATCH_COMMITTED/RESULT_COMMITTED, intento2 SUCCEEDED, cero llamadas al retomar,
originales retenidos. Un lote por caso; multilote parcial pendiente.
Atomic Qwen proof1c70faf0282548499cd601f6ebe9859e y manifest APIa75adb4c445c46d698abc558a8308112.

Transporte PR67 integrado/apagado por defecto. Imagen t008
76d97066ddfd87de84c8754df8d9308034d43262e48d6083660b43df0c46c131,
97hash/importPASS. Único Qwen activo en rag-f05-embedding-query-t008; t004 detenido
preservado. Entrega F05 vence ~2026-11-03T10:47UTC, comprobar antes de usar.
QA RPC bec5dbc5efaf44d2b408a13c80e270f8 PASS cuatrofixtures/SQL/workerACL/toolsnoTorch.
Contadores/trazas:4requests92tokens,0inferencias en denegaciones. F04 QA cerrada.

Worktree feat/F05-T007-http-search sobre80bf466: adaptador/flag/overlays/manual
http-search.md/QA OIDC preparados, todavía sin PR/build/despliegue.
Suite1076passed86.79s,45HTTP16.30s; pruebas adicionales de flag en curso.
Sin migración/dependencias. CI/revisión/merge/postmerge antes de imagenAPI:t009.
API t006 está activa con entrega limitada vencida: detener antes de reemplazar
F03 bajo /run/user/1000/rag-f03-application/consumer.lock, usando día vigente.
Conservar contenedor/imagen anterior, nunca iniciar t003 contra0006.
QA HTTP sin SQL/handoff/día/administrador, verifica ocho originales SHA y cuatro
búsquedas/rechazos; no necesita nueva entregaF04. Nuevo journal0700.

Día ACTIVE comprobado09:39UTC Nov3, vence07:14:15-05:00 (12:14UTC).
No renovar/root/configure/políticas/reinicios Bao por iniciativa.
Todo ejecución/dependencias en ragdev01; Mac solo SSH/documentos.
GitHub fuente verdad; árboles iguales al probado, ADR0007 revisión propia explícita
y CI HEAD/postmerge. Seguir hasta dependencia/decisión real, no terminar por PR.

Después HTTP: originalSHA/regresión, ANN/exacto/filtros, calidad SQL ES/EN y
recuperación parcial multilote. T003..T008/F05 siguen abiertas.

Actualización10:06UTC: PR68 integrado0cb18d6 y postmerge success.
Operativo en ese develop. API t009 activa,98hash/importPASS/noTorch;
t006 detenida preservada. F03 vence~11:02UTC, Qwen t008~10:47UTC.
Primer HTTPQA83d8... START REFUSED antes de consultas: manifests API/worker tienen
repositorios distintos en mismo tenant/space. Fix aislado en rama
fix/F05-http-proof-repositories: consulta ambos repos autorizados, descarga cada
original de su repositorio. CI/merge/postmerge antes de repetir con journal nuevo.
ANN WIP local preservado f888933 en feat/F05-T006-ann-retrieval,30offlinePASS:
componente separado todavía sin activar, prueba nativa/cobertura/indexplan pendiente.
Al cerrar fix, alinear operativo y retomar ANN vía merge develop sin reset.
No repetir benchmark ni adopción; conservar journals. HTTP aún no aceptado.

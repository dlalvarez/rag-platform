# Aceptación F05 — expediente de cierre

Estado: pruebas técnicas completas. Aceptación propuesta, efectiva después de
CI correcto, revisión e integración delegadas y comprobación postmerge.
Alcance original autorizado por ADR0010; revisión/integración delegadas ADR0007.
Decisiones Qwen/HTTPfragmentos/adopciónBD/conexiónprivada registradas, sin nuevas
aprobaciones personales atribuidas a Diego.

## Criterios y evidencia

| Criterio | Comportamiento comprobado | Evidencia |
|---|---|---|
| AC-F05-01 | Dimensión/norma/finitud/perfil inválidos rechazados antes de guardar lote; tabla tipada y publicación completa | test_f05_embedding_contract.py, test_f05_space_ddl.py, test_f05_embedding_worker.py; baterías SQL/adopción en evidence.md |
| AC-F05-02 | Contexto servidor, todas las ACL antes del modelo y nueva autorización antes de fragmentos; perfiles/espacios aislados | test_f05_search_service.py, test_f05_query_transport.py, test_f05_search_api.py; HTTP e178b6f57f514af9bbbdcb9a7327ab5b y RPC bec5dbc5efaf44d2b408a13c80e270f8 |
| AC-F05-03 | Request idempotente, vectores por chunk únicos, commit-before-ACK recuperable sin repetir lote persistido | Qwen1c70faf0282548499cd601f6ebe9859e; recuperación1lote b6e1cd49609c4f6e8b8de8f06ff2f268; multilote df669c4900ac4727be6e0612fef8fd13 |
| AC-F05-04 | Identidad completa de modelo/espacio y tablas tipadas independientes; mismo tamaño no hace compatibles perfiles distintos | test_f05_retrieval_sql.py, test_f05_retrieval_ann.py y pruebas SQL de publicación/perfil; gold Qwen e5a2ff71648d4a4a99a572b1f84a0bff |

Los nombres de pruebas pertenecen a tests/unit. El detalle reproducible y resultados
fallidos/corregidos están en evidence.md y manuales enlazados; no ocultar diagnósticos.

## Alcance probado hasta ahora
Control0007/cuatro tenants0006 en dos instancias; adopción aditiva/FAILED/rollback/
recuperación y roles/TLS sin cambiar originales. Qwen localCPU1024/coseno/L2/512tokens,
pesos/revisión/prefijos congelados. API sin Torch con transporte privado al mismo
trabajador, directorio/socket/UID, límites de framing/concurrencia/espera y cierre.

HTTP: request_id/space/hits autorizados/uso, no respuesta generada. Repos/tenant
ajenos, entradas inválidas, tokens excesivos y trazas cliente no se aceptan.
Ocho originales atomic/recovery HTTP SHA, cuatro solicitudes reales de consulta
y cero inferencias por denegaciones según trazas del trabajador.

SQL ANN/exacto: cuatro fixtures con filtros selectivos, planes/ejecuciones HNSW,
ACL/baja/versión/publicación/perfil y rollback íntegro. Corpus público congelado
16docs/16queries ES/EN: Recall@3=1.0 por idioma/modo/fixture y overlap1.0,20llamadas
reales961tokens antes de SQL. Fixtures/guard/ledger de esa calidad son sintéticos;
no representan64indexaciones reales, dominioF06, rendimiento o billing.

## Recuperación y regresión finales

Cuatro documentos públicos nuevos de11250bytes,14chunks y4lotes cada uno.
Los cortes tras el primer lote retomaron solo los3lotes pendientes; los cortes
tras publicación retomaron sin inferencias. Todos terminaron SUCCEEDED en el
segundo intento, con14vectores,4lotes y1publicación, conservando ancla original,
usage comprometido, fences, heartbeats e idempotencia. Journal
df669c4900ac4727be6e0612fef8fd13. El último resume terminó exit0 en35.17s.

Verificación HTTP del corpus cefed930e3444ddda29e581d61ceaec9:
4originales con SHA correcto y4versiones publicadas, exit0 en21.58s.
Regresión f9b70369f2cb41d9aaa58d69407e6df3: exit0 en35.58s,
OIDC/contexto,SQL/TLS/roles/CONNECT/SET ROLE,S3 propio/ajeno,privacidad y
originales históricos correctos en4tenants/dos instancias. El intento previo
aa8183859536407388a7cf6c1db9018c falló en two-a/S3 ProtocolError.
No se determinó la causa; la repetición con el modelo cerrado pasó sin cambiar
los controles. Este resultado no demuestra ausencia de fallos transitorios.

Logs de corpus/recuperación/API y PostgreSQL sin los marcadores documentales
ni patrones Bearer comprobados. Cuatro controles positivos de log observados
(3 en postgres y1 en postgres2), sin canary privado ni texto multilote.
Esto comprueba los marcadores ensayados, no un detector universal de secretos.
No cambios de esquema ni dependencias en este expediente.

## Integración pendiente

CI sobre el HEAD exacto, revisión del diff, merge a develop y comprobación
postmerge. La aceptación se registra en el PR al completar esos controles.

## Límites conservados
La API de desarrollo mantiene búsqueda exacta; ANN es componente interno validado
y el planificador puede elegir otra estrategia en conjuntos pequeños/selectivos.
No se promete latencia ni se fuerzan ajustes globales de PostgreSQL.
Sin híbrida/FTS/reranking/asistentes/chat/generación/UI/billing/producción.
Sin cambio VMM/GPU, política Bao, renovación automática del día o downgrade.
Imágenes, contenedores, documentos/originales, espacios y journals conservados.

## Recuperación multilote: estado verificado

| Fixture | Estado | Inferencias al retomar | Vectores | Lotes guardados | Intento |
|---|---|---|---|---|---|
| same-a | SUCCEEDED | 3 | 14 | 4 | 2 |
| same-b | SUCCEEDED | 0 | 14 | 4 | 2 |
| two-a | SUCCEEDED | 3 | 14 | 4 | 2 |
| two-b | SUCCEEDED | 0 | 14 | 4 | 2 |

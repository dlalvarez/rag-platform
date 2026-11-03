# Plan de recuperación ANN autorizada

Alcance T006, F05-R04 y AC-F05-02/04. Preparado antes de implementación.
No cambia contrato HTTP, tenancy, dependencias, DDL ni elección Qwen.
Archivos previstos: retrieval_sql.py, nuevo retrieval_ann.py, tests offline
y extensión del comprobador PostgreSQL con rollback, evidencia y manual.

Conservar exact_statement/exact como referencia independiente. Reutilizar una
única definición del conjunto permitido: ACL, repo activo, documento vigente sin
baja, pointer procesado, ancla original y publicación completa en el espacio.
La materialización de IDs/metadatos autorizados precede a devolver contenido.

Construir candidato HNSW sobre tabla tipada y parámetros enlazados; predicado de
pertenencia al conjunto permitido dentro de la selección ordenada por distancia.
No tomar primero un número fijo de candidatos globales y postfiltrar después.
pgvector aplica filtros durante el escaneo del índice: activar iterative_scan
strict_order, ef_search200 y max_scan_tuples20000 con SET LOCAL, sin configurar
servidor global. Mantener statement_timeout15s del servicio.
Fuente primaria: [pgvector0.8, filtrado y escaneos iterativos](https://github.com/pgvector/pgvector/blob/v0.8.0/README.md#iterative-index-scans).

Solicitar top_k+1 (máximo51) para detectar empate de frontera, ordenar resultado
por distancia/chunk_id. Si falta el candidato adicional para comprobar la frontera o hay empate, volver
a exacto autorizado. No afirmar igualdad global ANN/exacto: medir Recall@k y
plan del índice; exacto sigue referencia. Perfil/UID/vector inválidos fallan
cerrados. No relajar checks de publicación ni permitir al cliente elegir SQL.

Pruebas previstas: mismas exclusiones de exacto, campos enlazados/SQL tipado,
ajustes locales, underfill/empate/fallback y perfil diferente de igual dimensión.
Nativo PostgreSQL: ambas topologías, app/readonly, índice demostrado por EXPLAIN,
filtros selectivos que no completan top_k en una ventana inicial global, ausencia
de contenido ajeno, comparación IDs/distancias contra exacto, rollback de todo
DDL/dato y huellas F04/control conservadas.
Calidad Qwen/SQL ES/EN usará corpus ficticio congelado existente, sin repetir
benchmark de capacidad. No acreditar calidad F06 ni aceptar F05 antes de pruebas.

Estado de implementación: componente preparado y servicio HTTP conserva exacto.
Filtros compartidos extraídos sin cambiar su semántica; sin activación ANN.
Prueba nativa preparada en scripts/f05_ann_check.py y ann-check.compose.yaml:
dieciséis fixtures ajenas con vectores sintéticos más cercanos, ventana global40
sin IDs permitidos, comparación ANN/exacto y EXPLAIN parametrizado con índice HNSW.
enable_seqscan=off solo en savepoint QA revertido para probar elegibilidad; no
afirma que el planificador elija HNSW en toda consulta o que sea más rápido.
Se reutiliza prove exacto con hooks opcionales, cuyos defaults permanecen iguales.
Toda la batería sigue usando rollback exterior y huellas históricas/control.
Pendiente ejecutar nativa tras PR/CI/merge/postmerge, calidad y activación de servicio.

## Ajuste y prueba nativa
La selección IN inicial pasó filtros/comparación pero el planificador la transformó
en semi-join y no demostró recorrido HNSW. Se usa EXISTS correlacionado con OFFSET0
para conservar la comprobación como filtro del índice; no cambia el conjunto
permitido ni permite al cliente elegir SQL. No se fuerza planificador global.

QA b678c50d10fc498eb7981cc97d09b756: cuatro fixtures/ambas instancias PASS,
cuatro planes HNSW y ejecución de esos recorridos contra exacto, filtros selectivos
con ventana global40 sin resultados permitidos y negativos/rollback correctos.
enable_seqscan=off solo durante savepoint QA revertido; no promesa de elección
del índice en toda consulta o mejora de latencia. Servicio HTTP conserva exacto.

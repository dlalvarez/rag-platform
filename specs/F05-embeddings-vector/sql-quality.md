# Plan de calidad Qwen/SQL exacta y ANN

T006/T008, F05-R04/R05 y AC-F05-02/04 parciales. Preparado antes de implementación.
Archivos previstos: scripts/f05_sql_quality_check.py, overlay sql-quality.compose.yaml,
tests offline de corpus/métricas, evidencia y continuidad. Sin nuevo contrato/DDL.

Reutilizar tests/fixtures/f05/retrieval-es-en.json y su SHA congelado
ca4d53dd72713febe740eebd958b384aae6dd9f2793c8433314c224b3284340e.
16documentos/16consultas ficticios ES/EN, gold definido antes del modelo.
No repetir métricas de capacidad/latencia ni afirmar calidad de dominio/F06.

Un único proceso Qwen opcional en imagen t008 con modelo RO y fuentes de revisión
integrada. Trabajador RPC anterior debe estar detenido; API no carga modelo.
Límites1.5CPU/6GiB/threads2, sin GPU, descarga, red externa o nueva política.
No depende de renovar día/handoff; conecta la batería SQL temporal ya autorizada
con bootstrap existente y cambia a roles owner/app/readonly en transacción.

Calcular primero los vectores del corpus público congelado y de sus consultas,
sin conexión SQL abierta: cuatro lotes de cuatro pasajes y16consultas,20llamadas
reales al proveedor. Conservar vectores solo en memoria y contar su uso real una
vez. Reutilizarlos en las cuatro fixtures sintéticas de DB no agrega bases ni
datos privados de tenants. Los ledgers SQL temporales son fixtures de componente,
no una medición de coste de64indexaciones independientes; imprimir uso global
real del proveedor por separado. Worker/usage/fencing reales tienen otras pruebas.

Cada fixture/DB crea16documentos SQL ficticios y chunks de texto gold, una versión
procesada por documento y perfil Qwen vigente existente. Usa guard sintético
explícito para guardar lotes/publicación en esta transacción, resultados reales Qwen precomputados
y contador global de llamadas/tokens; no atribuye fencing o commits independientes.
Todos los repositorios se autorizan al mismo actor mediante ACL de fixture.
No genera objetos S3 ni modifica documentos persistentes.

Consultar como app/readonly dentro de la DB de ese tenant; exacto y ANN reciben
el mismo embedding Qwen de consulta, con todos los filtros de publicación/ACL.
Recall@3 ES y EN>=0.8 por modo/fixture, comparar contra gold y exacto, excluir
actor/repositorio ajenos. Perfil diferente de igual dimensión debe fallar cerrado.
Imprimir métricas/códigos únicamente; no texto/vectores/credenciales.

Revertir toda escritura exterior; comprobar huellas históricas, esquema previo,
cuenta de vectores/publicaciones originales y ausencia de fixtures temporales.
Conservar journal privado de agregados y errores cerrados. Esta prueba acredita
componente Qwen/SQL en4fixtures/ambas instancias; HTTP/S3/fencing independientes
tienen otras pruebas. No sustituye recuperación parcial multilote pendiente.

## Operación preparada
Implementación scripts/f05_sql_quality_check.py y sql-quality.compose.yaml.
Después de PR/CI/merge/postmerge, comprobar que no está activo otro proceso Qwen.
Crear journal0700 nuevo, fijar RAG_F05_QUALITY_QA_ROOT y combinar compose F02
con sql-quality.compose.yaml; run --rm --no-deps --pull never f05-sql-quality-check.
Imagen opcional t008 conserva sus dependencias fijadas; fuente/scripts integrados,
corpus y modelo se montan RO. No construir otra imagen por cambios solo de QA.
No necesita día/handoff/API ni credenciales nuevas; bootstrap/migrator son los
mismos del comprobador SQL existente, solo para la transacción temporal.
Salida verified.json agrega4fixtures, Recall@3 por modo/idioma, solapamiento ANN
y uso global real del modelo. Fallo se informa cerrado y conserva journal.
10pruebas offline validan SHA/gold, normalización a un chunk, veinte llamadas,
respuesta inválida, privacidad de repr y métricas separadas. No cargan Qwen.
Prueba real todavía pendiente; no afirmar calidad o aceptación F05.

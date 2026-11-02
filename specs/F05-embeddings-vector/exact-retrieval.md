# Referencia exacta de recuperación F05

Componente interno embeddings/retrieval_sql.py, F05-R04 y AC-F05-02/04 parciales.
No recibe tenant_id ni resuelve conexiones. Solo debe llamarse dentro de una conexión
obtenida por AuthorizedConnections con contexto vigente; no constituye una frontera
HTTP/autorización de membresía por sí mismo.

La consulta verifica ACL dentro de la misma sentencia, repositorio activo, documento
vigente sin baja, versión procesada publicada, ancla original y binding del espacio.
Materializa ese conjunto antes de calcular distancia coseno y ordenar con desempate
por chunk_id. Es una referencia exacta; no fuerza ni acredita el índice HNSW.
Perfil completo validado contra catálogo, vector normalizado y parámetros enlazados.
Un modelo de igual dimensión con otra identidad no puede consultar el espacio.
No devuelve vectores; excerpt hasta512 caracteres, page y ruta section del JSONB F04.

## Prueba SQL opt-in
En ragdev01, combinar ops/f02/compose.yaml y ops/f05/retrieval.compose.yaml,
usando el archivo de variables F02 existente y run --rm --no-deps --pull never
f05-retrieval-check. No iniciar dependencias ni usar remove-orphans.
El helper usa conexiones administrativas solo para crear fixtures temporales;
consulta como app/readonly. Todo DDL/dato se revierte en transacción exterior.
Comprueba esquema previo, ausencia de tabla temporal y hashes F04 al finalizar;
el controlador comprueba catálogo/identidades/jobs restantes conservados.
Se admite source0004 o0006 explícito; la batería histórica conserva0004 por defecto.

Proveedor y guard sintéticos: orden contra referencia coseno Python, unpublished
oculto, top_k, actor/repositorio ajenos, reader, ACL retirada, tombstone y binding
ausente. Otro modelo de igual dimensión falla cerrado. No es Qwen, ni prueba de
commits independientes, ni aceptación de búsqueda HTTP/ANN. Para producción queda
pendiente servicio que autorice todos los repositorios antes de inferir, libere la
conexión durante inferencia y abra contexto nuevo antes de recuperar fragmentos.

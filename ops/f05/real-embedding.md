# Comprobación opt-in de Qwen y publicación

Esta herramienta prepara una prueba real; no se ha ejecutado todavía.
Requiere la adopción persistente autorizada y completada en control0007/tenant0006,
API compatible activa y su regresión correcta. No aplicar migraciones desde esta QA.
La aprobación de la migración está pendiente tras rechazo de la revisión automática;
la API t003 fue restablecida y se verificó OIDC y original HTTP/SHA sin cambiar datos.

## Alcance fijo

Selecciona solo el documento atomic del manifest F04 conservado por cada uno de
los cuatro fixtures. Verifica nombres/tenant contra el scope horneado y los actores
contra identidad OIDC real. No recibe tenant/documento/modelo por argumentos.
Es una solicitud explícita de esas cuatro versiones procesadas, sin barrer historia.
El actor alice debe conservar membresía y ACL. Solo hay modos request y verify.

Usar ops/f02/compose.yaml y ops/f05/real-embedding.compose.yaml con las variables F02,
RAG_F04_QA_ROOT hacia el manifest conservado y RAG_F05_EMBED_QA_ROOT hacia un directorio
nuevo0700 propio de diego. El manifest se monta RO. selection.json y verified.json
son checkpoints privados0600 con IDs, hashes y contadores, sin texto ni vectores.
Un conflicto no sobrescribe la selección. No montar día, migrador ni bootstrap.

## Ejecución después de autorización/adopción

Con INGEST cerrado y su lock libre, asegurar entrega limitada F04 mediante su
herramienta existente y sesión diaria vigente. Ejecutar f05-real-embedding-check
request con run --rm --no-deps --pull never. La autoridad usa perfil exacto y ACL
frescas; el cierre revoca solo esa entrega QA.

Preparar/emitir la entrega independiente EMBED según embedding-operations.md.
Iniciar únicamente el worker EMBED revisado, con el modelo Qwen aprobado RO.
No compartir entrega con QA, no reconstruir/recrear dependencias y no repetir
benchmark de capacidad. Registrar los códigos de trabajo sin textos ni vectores.
Esperar los cuatro trabajos seleccionados; si fallan, conservar parciales/journal
y resolver el código cerrado antes de repetir, sin borrar ni resembrar.

Tras lock F04 libre, emitir su siguiente entrega limitada y ejecutar verify.
Repite request para comprobar binding idempotente; verifica COMPLETE/DISPATCHED,
envelope SUCCEEDED y tenant/actor/version/space/perfil, publicación completa,
cantidad de vectores igual a chunks, usage real, pointer PROCESSED/ancla original,
estado PUBLISHED e historial, y descarga original HTTP con SHA/tamaño conservados.
La herramienta no imprime contenido. Cerrar worker cuando termine la comprobación,
conservar su contenedor/imagen y comprobar liberación de lock.

Esta prueba inicial no acredita por sí sola crash entre commits independientes,
reautorización larga, calidad semántica, búsqueda ni aceptación completa de F05.
Esas comprobaciones siguen pendientes y deben registrarse por separado.

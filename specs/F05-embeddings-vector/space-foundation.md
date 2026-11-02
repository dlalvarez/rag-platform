# Fundación de espacios — F05 T003 parcial

R02; apoyo AC01/04. No cierre T003, no búsqueda/publicación ni adopción persistente.

Migración f05_tenant_0004 desde f04_tenant_0003: constraint de identidad compuesta
de chunks y catálogo embedding_spaces. No cambia estados, pointer, ancla original,
chunks, auditoría o guards F04. Perfil/registro retenidos por trigger UPDATE/DELETE.
App/readonly solo SELECT al catálogo; registro/DDL únicamente owner/migrator
administrativo. Nada de SECURITY DEFINER, privilegios globales o runtime migrator.

Registro por UUID/perfil con fingerprint, lock por tenant y cota16 espacios.
Tabla vector(dimensión) por espacio, dimensión int1..2000, coseno/L2, FK al perfil
y a chunk/version/document/repo, norma unitaria y HNSW/coseno.
Validación común rechaza no finitos/booleanos/dimensión antes de SQL.
Cada helper de mutación tiene savepoint: un error capturado por el llamador no
permite confirmar el catálogo/DDL parcial. Repetición verifica perfil, tipo, constraints
e índice; una colisión no se sustituye ni se convierte en éxito.

## Ensayo SQL real sin adopción

ops/f05/schema.compose.yaml combina con ops/f02/compose.yaml, project-name rag-f05-qa,
env-file F02 operativo, run --rm -T --no-deps f05-space-check.
Ejecutar desde checkout en ragdev01. Imagen QA F04 t007 y fuentes/migraciones/script
RO del checkout bajo revisión; no afirmar que el source del host es el contenido
inmutable de esa imagen. El override se resuelve relativo al primer Compose (ops/f02).

Herramienta administrativa SQL separada con dos bootstrap/CA/control migrator,
sin día/Bao/S3/OIDC ni credenciales de inferencia. No es runtime.
Solo cuatro fixtures existentes; todas las transacciones tenant se revierten.
No migrate_controlled persistente, ni modificación de catálogo control.
Conservar snapshot de todas las tablas F04 y control antes/después.

Prueba fallo DDL22012 con rollback, aplicación/repetición física, Qwen vector(1024),
dimensión incorrecta22000, norma/perfil incorrectos23514, FK ajena23503, duplicado23505.
App UPDATE/DELETE/perfil y readonly INSERT42501; perfil owner UPDATE/DELETE23514.
Colisión de tabla no deja catálogo parcial aun capturando el error; recurso ajeno
no se sobreescribe. Perfil nuevo/misma dimensión crea tabla distinta sin tocar anterior.
Norma unitaria sintética: no afirmar embedding real ni calidad por estas filas.
HNSW construido/verificado; comparación ANN/exacto/ACL pendiente de T006.

No adoptar este head en fixtures persistentes hasta perfil F05 de migración/resolver/
API compatible. Cola EMBED/control y evolución de ancla/pointer siguen pendientes
en entregas posteriores. No ampliar aceptación a publicación/reindexación completa.

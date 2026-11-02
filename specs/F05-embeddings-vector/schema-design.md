# F05 T003 — evolución física de espacios y compatibilidad

Preparación posterior a PR47/Qwen aprobado. No DDL/adopción persistente ejecutados.
R02; AC01/02/04. Mantener F04 histórico intacto y fixtures/originales retenidos.

## Orden de evolución y frontera

Separar fundación aditiva (espacios/tablas vectoriales/registro de operaciones)
de la publicación T005. Una tabla vectorial puede existir sin resultados consultables:
no habilitar búsqueda ni declarar PUBLISHED hasta demostrar binding completo.
No aceptar automáticamente heads futuros en perfiles F03/F04.
Antes de migrar fixtures existentes, perfil F05 explícito de migración/resolver/API
con head exacto, snapshot de procedencia/objetos y regresión sobre el original.
Control y tenant migran separados: fallo real => FAILED, nunca versión falsa.

## Perfil y tabla por espacio

knowledge.embedding_spaces con UUID, perfil completo y fingerprint único, inmutable.
Creación administrativa/migrator; app/readonly no crean ni alteran perfiles o DDL.
Modelo/revisión/tokenizador/métrica/norma/dimensión/instrucción/límites son identidad.
Un perfil distinto crea otro espacio, incluso si coincide dimensión.
Tabla knowledge.embeddings_UUIDhex vector(dimensión) por espacio; HNSW/cosine.
Nombres solo UUIDs validados de catálogo, dimensión int1..2000 validada; nunca request.
FK compuesta chunk/version/document/repository y FK al perfil impiden falsa procedencia.
No embeddings/texto en control; sin vistas o índices entre DB tenant.
Cota inicial de espacios por tenant y DDL serializado: evitar crecimiento ilimitado.

## Operación y publicación que deben conservarse

Estado por versión+space, no reemplazar estado global como única condición.
Jobs EMBED: control solo IDs/fingerprint/uso agregado, con space_id obligatorio;
INGEST histórico conserva su identidad única y space_id nulo mediante índice parcial.
Identidad EMBED única tenant/version/space/kind, clave de idempotencia y leasing/fencing.
Tenant registra operación/attempt_token/lease y lotes sin exponerlos a búsqueda.
FK de vectores a operación vigente; lote completo validado antes de persistir.
No sobreescribir vector ya confirmado ni borrar espacio anterior.

Publicación T005 debe contar/verificar TODOS los chunks del procesado, perfil,
guard/fencing, ACL/membresía/tenant/repository/documento vigente y auditoría.
Confirmación de vectores/publicación/pointer/uso tenant en una transacción;
ack control posterior con reconciliación por ID para no duplicar inferencia.
Un espacio viejo publicado sigue recuperable mientras el nuevo es incompleto.

## Ancla original y compatibilidad

F04 current_version_id solo admite ORIGINAL y su guard lo usa en finalización.
F05 introduce original_version_id explícito en documents, relleno desde la identidad
F04 existente y FK compuesta al ORIGINAL de ese documento/repositorio.
No deducir una nueva fuente por nombre/path ni reescribir la versión ORIGINAL.
Upload/replay/show/download y guard de ingesta usan el ancla original.
current_version_id/current_version_kind pueden conmutar al PROCESSED completo
solo mediante publicación con prueba por versión+space. Mantener estado/publicación
anterior hasta commit; tombstone oculta todas las versiones y preserva los datos.
No retirar trigger inmutable F04 sin guard F05 equivalente: procedencia/chunks
completos siguen inmutables al progresar EMBEDDING/READY_TO_PUBLISH/PUBLISHED.
Auditoría de ingesta permanece; auditoría de publicación es adicional y diferida.

## Validación antes de adopción

Compilación DDL sin mutar metadata histórica; negativos de UUID/dimensión/valores/
identidad de perfil; PG real con vector tipado, HNSW/coseno, transacción fallida y
repetición. Ambas topologías con migración física repetible/rollback de error DDL,
roles mínimos, TLS, CONNECT cruzado y aplicación sin DDL.
Probar original F03 retenido, F04 INGEST y pointer antes/después, versión falsa
rechazada y snapshot de objetos/procedencia intacto. Nada de purge/downgrade.
Estos gates siguen pendientes; diseño no equivale a migración aplicada o AC pasado.

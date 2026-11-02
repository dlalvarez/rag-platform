# Diseño físico T004/T005 F05, preparación

Dentro de plan F05 aprobado: migración tenant0005 para ancla; evolución posterior para publicación/usage, sin alterar copias históricas.
No ejecutar adopción antes de compatibilidad, QA SQL/roles/regresión y revisión.

knowledge.documents.original_version_id guarda el ancla ORIGINAL, con backfill desde
current_version_id y FK compuesta que exige identidad/kind ORIGINAL. Trigger de INSERT
completa el ancla desde current_version_id para conservar receptores antiguos durante
la transición controlada; ancla inmutable. current_version_id/current_version_kind
pueden pasar a PROCESSED completo, conservando originales. Estado documental RECEIVED
sigue indicando documento activo; TOMBSTONED bloquea todo. Descarga/show/replay e
ingestion.request usan ancla original solo bajo perfil F05 nuevo, nunca fallback de head.

knowledge.embedding_publications: identidad versión+espacio, documento/repositorio,
perfil, actor, chunk_count y published_at. Solo fila completa visible; FK de procedencia
y perfil. Publicación inicial cambia versión READY_FOR_EMBEDDING a PUBLISHED y pointer
en la misma transacción. Publicación a otro espacio conserva PUBLISHED existente hasta
commit del binding nuevo. Reindexar misma versión+espacio reconcilia/no-op.

ops.embedding_intents: versión/espacio/perfil/actor y dispatch/lease/fence acotados.
Estado de procesamiento por binding, independiente del estado publicado de otro space.
ops.embedding_batches: identidad intent+ordinal, hash del conjunto de chunks, tokens,
requests/duración y conteo; ninguna copia de texto/vector. Commit batch inserta vectores
y usage juntos. Idempotencia comprueba identidad/contenido, jamás UPDATE de vectores.
Cuota inicial por trabajo basada en límites existentes de10k chunks/512tokens/batch4;
proveedor puede rechazar chunk por tokens, sin truncarlo ni cambiar chunker existente.

Preservar guard F04 de provenance/cobertura, reemplazando solo función explícita F05:
READY_FOR_EMBEDDING permite cambio exclusivo a PUBLISHED con payload idéntico.
Constraint triggers diferidos requieren binding completo, vectores para todos los
chunks exactos, uso/auditoría y pointer válido. Publicaciones inmutables.
Reindexación usa mismo procesado, otro perfil requiere espacio nuevo.

Worker limita memoria por lote y una inferencia simultánea. Heartbeat durante inferencia
larga sin sostener locks tenant/control; reautoriza nuevo contexto tras inferir y antes
de cada persistencia. CommitGuard corto más locks administrativos y ACL/documento.
Tenant commit anterior a ack se reconcilia sin repetir inferencia de batches guardados.
No garantizar exactly-once de inferencia tras crash antes de persistir.

Pruebas: negativos FK/profile/dimensión/cobertura; originales upload/replay/download
antes/después; rollback/replay; crash batch y commit-before-ack; permiso revocado o
tombstone durante inferencia; otro space mantiene resultados; ambas topologías.
SQL concurrency real necesita fixture explícita persistente y consumidores propios;
no atribuirla a ensayo con transacción exterior. Recursos históricos conservados.


## Primer incremento acotado
tenant0005 solo añade el ancla inmutable y su backfill/FK/guard. Conserva el
constraint F04 que exige current_version_kind ORIGINAL; no permite aún publicar.
No cambia perfil runtime ni adopta el head. Preparar compatibilidad antes de adopción.
Ensayar rollback/repetición, INSERT compatible sin campo nuevo, FK cruzada, ancla
nula o modificada y snapshots históricos en las cuatro fixtures.

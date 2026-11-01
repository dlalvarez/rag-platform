# Plan F04 — ingesta versionada

Alcance original autorizado por Diego mediante ADR-0010. F03 aceptada en
[PR #34/postmerge](https://github.com/dlalvarez/rag-platform/pull/34#issuecomment-6565126139),
develop@4c5b8d3189b71dad6fbe6f2921cbd06b33754871. Toda ejecución manual en ragdev01.
No se modifica el roadmap, la constitución, los ADR aprobados ni los requisitos.

## Diseño dentro de la arquitectura vigente

Cola PostgreSQL durable en rag_control, como prescribe docs/02-architecture.md:
solo IDs, actor, tipo, lease, intentos, estado e idempotencia. Sin nombre de archivo,
texto, chunks, rutas de objetos, bearer ni excepciones de proveedor. Lease con
SKIP LOCKED, expiración, fencing por intento y backoff acotado. No Redis/Kafka.
Un worker separado de la API, inicialmente un trabajo simultáneo, con parada segura.

Estado y contenido residen en cada base tenant. Evolución aditiva separada de control
y tenant; conservar las factorías/migraciones históricas F01/F02/F03. Originales,
recepciones y versiones previas no se reescriben ni borran. Conservar procedencia:
cada procesamiento identifica original, hash, parser, normalización y configuración
de chunker. Misma identidad y configuración producen el mismo resultado, no duplicados.
Cambio de configuración crea otra versión de procesamiento sin copiar ni sustituir
el original. No deduplicar documentos diferentes solo porque tengan el mismo hash.

La intención durable tenant y su entrega a control se reconcilian idempotentemente;
no afirmar atomicidad entre bases distintas. Publicación del resultado y chunks en
una única transacción tenant, con token de intento/lease y comprobación de tombstone,
membresía y ACL vigentes. Reconciliar un commit tenant seguido de caída antes del ack.
Mientras no exista embedding completo, resultado READY_FOR_EMBEDDING explícito:
no marcar PUBLISHED ni mover un pointer de recuperación a un índice incompleto.
F05 completará el gate previsto; F04 no invoca embeddings.

Revalidar identidad/membresía/tenant READY y ACL al ejecutar y antes de confirmar.
La cola no es autorización. Resolver cada contexto desde catálogo, A→B→A sin mezcla,
pools limitados y secretos mínimos; runtime sin día, admin IAM, migrator ni root.
Reutilizar el mecanismo de entrega de aplicación limitado de F03 y sus cuatro fixtures
cuando sea compatible. Si se necesita ampliar identidad/permisos, preparar propuesta
concreta antes de cualquier operación privilegiada; no recuperar root por iniciativa.

## Extractores y límites

[Selección técnica D-05](parsers.md). Adaptadores locales sustituibles, sin OCR, modelos
descargados ni servicios remotos. Corpus nuevo y sintético con PDF semánticamente válido,
DOCX con títulos/tablas, Markdown/código y TXT español/inglés. Los positivos F03 PDF/DOCX
solo acreditaron la recepción estructural; no convertirlos en corpus de extracción ni
reescribir sus claves idempotentes.

Conservar entrada F03 de 10 MiB y controles ZIP. Parser en proceso hijo sin red,
credenciales ni acceso SQL/S3: padre obtiene original verificado y entrega descriptor
privado, hijo devuelve bloques limitados. Presupuesto inicial a medir: 512 MiB address
space, 30 s CPU/45 s pared, un proceso, máximo 200 páginas, 2 millones de caracteres
normalizados y 10 000 chunks por versión. Exceder un límite produce error cerrado
estable; nunca confirmar resultado parcial. Medir en ragdev01, no presentar estos
presupuestos como capacidad ya demostrada. Mantener límite de salida antes de IPC.

Bloques con página real PDF, ordinal de bloque DOCX, encabezados/secciones cuando
estén disponibles. No inventar paginación DOCX ni inferir certeza de orden de lectura
PDF complejo. Normalización NFC y saltos de línea explícitos; preservar SQL/código.
Offsets son índices de caracteres Unicode del texto normalizado, intervalo [inicio,fin),
no bytes del archivo. Chunks deterministas configurables, hash y ordinal; cobertura,
overlap, página/sección y vínculo a la versión verificables. No cruzar página/sección
sin registrar el rango. Tokenizador/modelo de embeddings no se decide en F04.

## Entregas y controles

T001 planificación; T002 cola durable; T003 esquema/versionado y tombstone; T004
extracción/chunking aislados; T005 worker e idempotencia/reconciliación; T006 API y
operación; T007 aceptación real en ambas topologías y no regresión.
Ver [tareas](tasks.md) y [checklist](checklist.md). Dividir PR por alcance verificable.
No activar worker contra fixtures previas indiscriminadamente: manifest de corpus
propio y alta explícita, conservando recursos y estado previo.

Cambios HTTP habilitan solo rutas F04 previstas de versiones/jobs y baja documental
con tombstone coherente; mantener errores, autorización, cursores y cuerpos acotados
de F02/F03. Contrato detallado antes del código afectado. No devolver chunks desde
control, paths físicos o secretos. Documentar política de reintento terminal/NEEDS_OCR.

CI obligatorio, revisión delegada del mismo agente (sin fingir independencia), merge
a develop y postmerge con fuente exacta. Nada de main/tag, producción, visibilidad,
purge, downgrade destructivo, backups/restore no ensayados ni cierre con mocks solos.

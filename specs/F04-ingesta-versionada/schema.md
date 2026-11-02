# F04 T003 — contrato físico de versiones, chunks e intención

R04/R05/R06; AC01/03/04/05. Implementación de las entidades ya previstas en docs/04
y del estado READY_FOR_EMBEDDING permitido por F04. Se conservan los nombres rectores
document_versions/chunks y su FK directa; una base por tenant, sin FK entre planos.

## Original y resultado procesado

Ampliar knowledge.document_versions mediante migración f04_tenant_0003 sobre
f03_tenant_0002, conservando la factoría histórica F03 intacta. Las filas existentes
son kind=ORIGINAL, mantienen todos sus valores F03 y no se actualizan ni eliminan.
Su blob_key sigue siendo propio y único, con el SHA/tamaño/MIME/nombre recibidos.

Cada procesamiento crea una fila kind=PROCESSED con original_version_id, mismo
documento/repositorio y metadatos de original verificados por FK compuesta. Su
blob_key es NULL: referencia al original retenido, sin copiar objetos ni inventar
una clave nueva. La FK incluye kind ORIGINAL del padre para impedir cadenas/ciclos.
Los chunks apuntan directamente a esta fila de document_versions y al bloque de
procedencia; nunca a una versión de otra identidad documental.

Unicidad de versión procesada por documento/original/config_hash. Configuración
incluye parser, normalizador, chunker y parámetros exactos ya fijados en T004.
Repetir identidad/config no crea otra versión. Otro hash/config crea otra versión
sin modificar resultados ni originales anteriores. Conservar actor original del job;
no adoptar una operación de otro actor para eludir su revocación.

La versión procesada registra parser/normalizador/chunker/config inmutables, estado,
error cerrado, hash normalizado, contadores y fecha de finalización. El app no puede
actualizar atributos del original o configuración. Resultado completo queda inmutable;
solo migraciones futuras explícitas podrán habilitar los estados de F05.
READY_FOR_EMBEDDING no es PUBLISHED ni da visibilidad para búsqueda RAG.

## Bloques, chunks y commit

knowledge.extracted_blocks conserva texto normalizado, ordinal, intervalos Unicode,
página real/blank_page, sección y tipo. knowledge.chunks tiene UUID estable, FK a
document_versions, ordinal único por versión, FK a su bloque y documento/repositorio,
texto/hash y offsets contenidos en el intervalo del bloque. Límites T004 también
reflejados en constraints. App INSERT/SELECT, sin UPDATE/DELETE de bloques/chunks;
readonly SELECT, sin acceso ops. No almacenar texto en control ni auditorías.

La versión pasa RECEIVED/VALIDATING/EXTRACTING/CHUNKING, con alternativas
FAILED_RETRYABLE/FAILED_TERMINAL/NEEDS_OCR/TOMBSTONED. Insertar todos los bloques/chunks,
validar cobertura/hash/contadores y cambiar a READY_FOR_EMBEDDING con auditoría
en la misma transacción tenant. La auditoría READY se comprueba también mediante
constraint trigger diferible antes del commit. Fallar antes del commit revierte todo el resultado.
No mover current_version_id a un índice incompleto; la referencia F03 al original
se conserva en F04. F05 resolverá publicación con embeddings completos.

## Intención, lease y borrado

ops.ingestion_intents enlaza actor/documento/versión y UUID de idempotencia, estado
de despacho y referencia lógica al job, más intento/token/lease locales para fencing.
No contiene credenciales. La intención se inserta en la misma transacción que la
versión candidata; su entrega a control se reintenta de forma idempotente. Caída tras
enqueue y antes de registrar despacho recupera el mismo job. No simular ACID entre bases.

T005 revalida membresía/tenant/ACL y claim vigente antes del acceso y del commit,
serializa la finalización con fencing y reconcilia commit tenant seguido de ack perdido.
T003 establece soporte de datos, no afirma haber probado aún esa orquestación.

Ampliar documents.state a RECEIVED/TOMBSTONED y añadir actor/fecha de baja. La baja
se serializa con el documento y no elimina objetos, versiones, bloques o auditoría.
Worker comprueba el tombstone bajo lock antes de finalizar; al ganar la baja, no
puede publicar un intento anterior. Historial retenido y consultas siempre sujetas
a documento/repositorio activos. Repetir baja es idempotente.

## Migración, permisos y registros

Targets explícitos y perfil ingestion de versión conocida; nada de aceptar cualquier
head futuro. Origen permitido F03/F04 para esta migración, sin avanzar tenants F01
de regresión por accidente. Conexión/lock/identidad/owner propios verificados, grants
mínimos y repetición/fallo DDL con rollback. No degradar head ni fabricar observed_version.

Antes de persistir texto, comprobar que errores SQL no registran cuerpos/valores
privados. Preparar defaults de logging por roles propios, de forma idempotente con
identidad administrativa de QA/instalación, sin contraseñas nuevas o cambios globales.
Conservar errores operativos: suprimir statements/parámetros/detalles de filas,
con controles positivos de logging y canary ausente, sin silenciar ERROR globalmente.
No instalar privilegios administrativos en API/worker. Medir con canary sintético y
devolver solo flags/códigos, nunca logs brutos.

El núcleo T003 se prueba primero con migración y probes dentro de transacciones
revertidas sobre datos F03, conservando el catálogo/perfil físico activo. La activación
persistente, conexiones reales de runtime, fallo/reintento del catálogo y migración
final se coordinan con T005/T006 antes de aceptar T003. No declarar completas esas
puertas por compilar DDL o por los probes de rol de la misma sesión.

No reescribir raw versions, purge, downgrade destructivo, nuevas credenciales de
runtime privilegiadas, root/unseal, reinicios de infraestructura ni embedding real.
Toda ejecución en ragdev01; conservar fixtures y ejecutar regresiones/CI/postmerge.

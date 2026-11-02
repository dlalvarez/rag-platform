# Contrato HTTP F04 — T006

Detalle de las rutas F04 previstas en docs/07-api-contracts.md y plan.md. No habilita
búsqueda, embeddings, publicación PUBLISHED ni configuración de infraestructura.

## Recepción e intención durable

Con perfil F04, el POST documental existente conserva cuerpo/respuesta, MIME, límites,
ACL, Idempotency-Key y códigos 201/200 de F03. Al confirmar una recepción nueva, crea
ORIGINAL, recibo COMMITTED, candidato PROCESSED e intención de ingesta en la misma
transacción tenant. La cola control se entrega después por relay; no afirmar una
transacción entre bases. No hay I/O de control ni parsing dentro del commit HTTP.
Un fallo creando candidato/intención revierte ese commit completo; el objeto privado
ya almacenado se conserva para recuperación del mismo recibo. Replay de COMMITTED
devuelve el original sin nuevos candidatos/jobs. No solicitar ingesta retroactiva de
documentos anteriores ni de fixtures fuera del run explícito.
ChunkConfig predeterminada del contrato de extracción (1024/128); sin configurar
modelo, dimensión, parser o endpoint desde el cliente en esta fase.

## Versiones

GET /api/v1/tenants/{tenant_id}/documents/{doc_id}/versions
requiere principal autenticado, tenant READY, membresía vigente y ACL read del repo.
Consulta la base resuelta del tenant; nunca acepta referencias físicas del cliente.
Respuesta request_id, items, next_cursor. limit 1..100, default50; cursor HMAC existente
vinculado a actor/tenant/colección F04/doc, orden UUID estable. Revalidar ACL en cada
página. Items: version_id, document_id, kind, original_version_id, state, sha256,
byte_size, mime, parser_id, normalizer_id, chunker_id, chunk_size,
chunk_overlap, config_hash, normalized_hash, character_count, block_count, chunk_count,
page_count, error_code, created_at y job_id nullable antes del relay.
Metadata derivada puede ser null para ORIGINAL o procesamiento todavía incompleto.
No texto, chunks, filename, blob_key, destino SQL, secret_ref, lease_token ni bearer.
READY_FOR_EMBEDDING no significa PUBLISHED; original y procesamientos son distintos.

## Job

GET /api/v1/tenants/{tenant_id}/jobs/{job_id}
filtra primero por tenant autorizado en control y verifica vínculo exacto al documento,
versión/actor e ID de intención derivado de la identidad inmutable y ACL read antes de devolver progreso. No joins entre bases ni permisos ops para reader. Los IDs de job de la lista de versiones se obtienen con consulta control acotada al tenant/documento/versiones ya autorizados, verificando actor e identidad de intención.
Respuesta request_id y job con job_id, document_id, version_id, kind INGEST, status,
attempts, max_attempts, error_code, created_at, updated_at, finished_at y version_state.
No actor/lease/idempotency IDs, contenido o información de conexión.
No inventar porcentaje ni duración restante. El estado control es la verdad operacional
si una revocación impidió registrar diagnóstico tenant; mostrar version_state histórico.
No permite cancelación/retry arbitrario del cliente. NEEDS_OCR/errores de parser terminales;
dependencias reintentan con backoff/cota del worker; cambio de permisos no reintenta solo.

## Baja documental

DELETE /api/v1/tenants/{tenant_id}/documents/{doc_id}
sin body ni parámetros; permiso delete existente del tenant y repo (owner/admin).
Baja lógica idempotente: state TOMBSTONED, actor/fecha y un evento local. Conservar
originales, versiones/chunks e historial. Lock repo/documento serializa con commit worker.
Respuesta request_id y document con document_id/state. Repetir devuelve mismo estado
sin duplicar evento. Desde baja, original/listado documental/versions/jobs no divulgan
contenido ni metadata histórica por esta API; siguen mecanismos operacionales limitados.
No borrar objetos/bases ni modificar current_version_id.

## Errores y validación

Usar envoltorio/code/request_id/Cache-Control:no-store de F02/F03. UUID inválido,
cursor adulterado/cambiado entre actor/tenant/documento, parámetro desconocido/duplicado
o límite inválido -> INPUT_INVALID. Recurso ausente, documento tombstoned o job de otro
tenant -> NOT_FOUND. Falta ACL local -> ROLE_DENIED conforme al contrato F03; roles
de plataforma no conceden contenido. Dependencia no disponible -> error saneado503.
No detalles de SQL/proveedor ni eco del body/filename/secretos.

## Puertas de prueba

R01/R04/R05/R06; AC01/03/04. Tests del adaptador real para auth, UUID/query/cursor,
errores y aislamiento de respuestas; SQL real para recepción+intención atómicas,
rollback y replay; HTTPS en cuatro fixtures/both topologies para flujo upload→relay→
worker→version/job, ACL/roles/accesos cruzados, baja repetida y no divulgación tardía.
Regresión F03 de repos/ACL/upload/original con perfil F04 explícito, sin relajar las
factorías y checks históricos para aceptar heads desconocidos.

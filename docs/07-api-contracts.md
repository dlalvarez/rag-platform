# 07 — Contratos API, eventos e interfaces

**Convención:** REST `/api/v1`; JSON; IDs UUID; timestamps ISO-8601 UTC; errores RFC 9457/problem+json o estructura equivalente versionada. Todas las operaciones tenant llevan `tenant_uuid` como ruta lógica, verificado **obligatoriamente** contra membresías.

## Endpoints propuestos (se habilitan por fase)

| Método | Ruta | Acción | Fase |
|---|---|---|---|
| GET | `/api/v1/me` | Identidad/membresías | F02 |
| GET | `/api/v1/tenants` | Listar tenants autorizados | F02 |
| POST | `/api/v1/admin/tenants` | Aprovisionar vía operación administrada | F01 (interno), F10 (controlado) |
| GET/POST | `/api/v1/tenants/{tenant_id}/repositories` | Listar/crear repositorios | F03 |
| GET/POST | `/api/v1/tenants/{tenant_id}/repositories/{repo_id}/documents` | Listar/cargar documentos | F03 |
| GET | `/api/v1/tenants/{tenant_id}/documents/{doc_id}/versions` | Revisar versiones | F04 |
| GET | `/api/v1/tenants/{tenant_id}/jobs/{job_id}` | Progreso y resultado | F04 |
| POST | `/api/v1/tenants/{tenant_id}/search` | Fragmentos autorizados por similitud vectorial | F05 |
| GET/POST | `/api/v1/tenants/{tenant_id}/assistants` | Administración asistentes | F07 |
| POST | `/api/v1/tenants/{tenant_id}/assistants/{assistant_id}/chat` | Mensaje / respuesta | F07 |
| GET | `/api/v1/tenants/{tenant_id}/conversations/{thread_id}` | Historial propio/autorizado | F07 |

## Formatos de ejemplo (no habilitados hasta su fase)

Contrato de búsqueda F05 aprobado expresamente por Diego el 2026-11-02:
HTTP de fragmentos, sin asistentes ni generación de respuestas. La aprobación
concreta el alcance; la ruta se habilita después de sus pruebas de aceptación.

Solicitud:

```json
{
  "repository_ids":["<uuid>"],
  "space_id":"<uuid>",
  "query":"¿Cómo funciona Data Guard Broker?",
  "top_k":8
}
```

repository_ids contiene de 1 a 16 UUID distintos; space_id identifica un espacio
del catálogo del tenant autorizado, nunca una tabla, perfil o endpoint libre.
query tiene entre 1 y 8192 caracteres y debe caber en el límite real de tokens
del perfil, sin truncamiento. top_k es un entero de 1 a 50.

Antes de inferir, todos los repositorios deben pasar ACL. Si alguno falla, se
rechaza toda la petición sin indicar cuál existe. La recuperación devuelve solo
versiones publicadas para ese espacio, vigentes y autorizadas; se revalida la
autorización después de inferir antes de consultar y devolver contenido.

Respuesta (valores ilustrativos):

```json
{
  "request_id":"<uuid>",
  "space_id":"<uuid>",
  "hits":[{
    "repository_id":"<uuid>",
    "document_id":"<uuid>",
    "version_id":"<uuid>",
    "chunk_id":"<uuid>",
    "score":0.82,
    "excerpt":"Fragmento efectivamente recuperado",
    "page":12,
    "section":null
  }],
  "usage":{"embedding_input_tokens":18,"embedding_requests":1}
}
```

score es similitud coseno; los empates se ordenan por chunk_id. excerpt procede
del chunk autorizado. page y section pueden ser null si la extracción no ofrece
esa ubicación. hits vacío es una búsqueda sin resultados. Las respuestas usan
Cache-Control: no-store. No se devuelven vectores, answer, grounded, assistant_id
ni tokens de generación. La generación con citas corresponde al chat de F07.

## Códigos y comportamiento

- 401 sin identidad; 403 sin acceso al tenant/recurso; 404 para no revelar existencia de objeto de otro tenant cuando aplique; 409 por conflicto de estado/versionado; 413 por tamaño; 422 validación; 429 cuotas; 503 por dependencia fallida.
- Límite de tamaño request/response, timeouts explícitos, `request_id`, control de idempotencia para POST que crea trabajos.
- Listados paginados con cursor opaco, nunca enumerar recursos de tenants ajenos.

## Eventos durables

`TenantProvisionRequested/Completed/Failed`, `DocumentReceived`, `IngestRequested`, `DocumentPublished`, `DocumentTombstoned`, `JobRetried/Failed`, `EmbeddingSpaceCreated`, `UsageRecorded`. Eventos usan IDs opacos, actor, timestamp y schema_version, no cuerpo documental.

## Contratos internos

`TenantResolver.resolve(authorized_context) -> TenantResourceDescriptor`; `TenantDB.session(descriptor)`; `StorageProvider.for_tenant(descriptor)`; `EmbeddingProvider.embed(texts, model_profile)`; `Extractor.extract(document_stream)`; `Retriever.search(authorized_context, repositories, query, profile)`; `AnswerService.generate(evidence, policies)`.

## Perfil implementado en F02

GET /api/v1/me: principal_id UUID, platform_roles, memberships y next_cursor.
GET /api/v1/tenants: items [{tenant_id UUID, kind PERSONAL|ORG, role}] y next_cursor.
Cada respuesta incluye request_id UUID generado por servidor. Sin referencias físicas,
secretos o claims de identidad. Solo membresías activas de usuario activo y tenants
READY con migración/versión compatibles. /me devuelve hasta 50 membresías;
continuar con /tenants y su cursor. /tenants admite limit 1..100 (default 50) y
cursor opaco ligado al principal. No se habilitan rutas tenant ni administrativas.
Errores: {error: {version: "v1", code}, request_id}; sin input rechazado ni excepción
de proveedor. Cache-Control no-store y X-Request-ID. JWT solo en Authorization Bearer.


## Perfil F03 de repositorios y documentos

Rutas y cuerpos concretos en [perfil F03](../specs/F03-repositorios-documentos/api.md),
implementado como extensión opt-in de la API existente. JSON CRUD/ACL acotado; carga
binaria directa con filename en query, Content-Type e Idempotency-Key. Respuesta
201 al recibir y 200 al repetir la misma petición; 409 si cambia su huella.
Original por proxy autorizado, attachment/no-store/nosniff y hash verificado antes
de HTTP 200. Sin URL pública ni endpoint histórico de versiones antes de F04.
La activación y aceptación se acreditan en evidencia de F03; no se altera el contrato F02.

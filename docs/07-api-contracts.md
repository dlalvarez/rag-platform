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
| POST | `/api/v1/tenants/{tenant_id}/search` | Recuperación fundamentada | F05–F06 |
| GET/POST | `/api/v1/tenants/{tenant_id}/assistants` | Administración asistentes | F07 |
| POST | `/api/v1/tenants/{tenant_id}/assistants/{assistant_id}/chat` | Mensaje / respuesta | F07 |
| GET | `/api/v1/tenants/{tenant_id}/conversations/{thread_id}` | Historial propio/autorizado | F07 |

## Formatos de ejemplo (no habilitados hasta su fase)

Solicitud de búsqueda:

```json
{"assistant_id":"<uuid>","query":"¿Cómo funciona Data Guard Broker?","top_k":8}
```

Respuesta:

```json
{
  "request_id":"<uuid>",
  "status":"grounded",
  "answer":"Respuesta basada en documentos autorizados.",
  "citations":[{"document_id":"<uuid>","version_id":"<uuid>","chunk_id":"<uuid>","page":12,"excerpt":"Fragmento efectivamente recuperado"}],
  "usage":{"input_tokens":100,"output_tokens":40},
  "limitations":[]
}
```

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

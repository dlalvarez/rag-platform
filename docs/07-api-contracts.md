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

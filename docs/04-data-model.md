# 04 — Modelo de datos de referencia

Se trata de un **contrato conceptual**. Alembic/DDL se generan y revisan en F01–F07; nombres pueden ajustarse por ADR menor sin eliminar invariantes.

## En `rag_control` (sin contenido privado)

| Entidad | Campos/relaciones esenciales | Notas |
|---|---|---|
| `users` | id UUID, oidc_subject, estado, timestamps | Identidad única; no almacenar password propio en MVP |
| `tenants` | id, slug, tipo PERSONAL/ORG, estado, plan_id | Estado PROVISIONING/READY/FAILED/SUSPENDED/DELETING |
| `memberships` | user_id, tenant_id, rol, estado | PK compuesta + restricciones únicas |
| `db_locations` | id, endpoint_ref, db_name, secret_ref, ssl_mode | Sin password; referencia a instancia/secret store |
| `tenant_provisioning` | tenant_id, step, desired_version, estado, error_code, intento | Idempotencia y reintentos |
| `storage_locations` | tenant_id, bucket_ref, credential_ref, region | Referencias no secretas |
| `job_envelopes` | id, tenant_id, actor_id, kind, resource_id, lease, attempts, status | Sin payload documental; idempotency_key |
| `usage_daily` | tenant_id, fecha, modelo, tokens, requests, storage_bytes | Agregados sin texto |
| `audit_control` | actor, tenant, acción, timestamp, outcome | Sin secretos ni cuerpo de documentos |

## En cada `rag_tenant_NNN` (datos exclusivos)

| Entidad | Campos esenciales | Reglas |
|---|---|---|
| `security.repository_acl` | repository_id, principal_id, capability | Privilegios negados por defecto |
| `knowledge.repositories` | id, name, owner, config, state | Config de idioma, chunking, retrieval |
| `knowledge.sources` | id, repo_id, provider, locator, sync_policy | Un origen externo puede producir N documentos |
| `knowledge.documents` | id, repo_id, source_id, current_version_id, status | Soft-delete/tombstone |
| `knowledge.document_versions` | id, document_id, content_hash, blob_key, mime, state, created_at | Histórico y versionado |
| `knowledge.chunks` | id, version_id, ordinal, text, page, section, offset, char_count | Texto recuperable, FK a versión |
| `knowledge.embedding_spaces` | id, provider, model, dimension, metric, physical_table, state | Perfil e índice versionados |
| `knowledge.embedding_bindings` | chunk_id, space_id, vector_record_id | Referencias y publicación |
| `assistant.assistants` | id, name, policy, model_profile, owner, status | Política de citas/abstención |
| `assistant.repository_links` | assistant_id, repo_id, mode | Siempre sujeto a ACL del usuario |
| `conversation.threads` | id, assistant_id, owner, status | Conversación scoped a tenant |
| `conversation.messages` | id, thread_id, role, content, model_used, timestamps | Contenido solo en DB tenant |
| `conversation.message_citations` | message_id, version_id, chunk_id, page, quote_span | Cita con procedencia verificable |
| `ops.audit_events` | principal_id, type, target_id, timestamp, result | Eventos con política de retención |

## Diseño de embeddings (importante)

- **No mezclar dimensiones/modelos arbitrariamente en una columna vectorial.** Un `embedding_space` representa proveedor, modelo, dimensión y métrica compatibles.
- MVP: perfil inicial configurable y **congelado por espacio** (por ejemplo 1536 dimensiones si se usa un modelo compatible). Un cambio de modelo crea un espacio y proceso de reindexación nuevos; nunca sobreescribe vectores incompatibles.
- Implementación física preferida: tabla tipada e índice HNSW por `embedding_space` dentro de la BD tenant cuando corresponda; DDL creado por migración/servicio validado, **nunca** con nombres tomados sin validar del usuario.
- Una versión documental solo es visible para recuperación si su estado es `PUBLISHED` y su indexación requerida está completa. La versión previa permanece consultable hasta conmutación.
- `document_versions` y `chunks` mantienen FK, unicidad `(version_id, ordinal)`, índices por repo/estado y control de borrado en cascada controlado.

## Invariantes de consistencia

1. `documents.repo_id` y `sources.repo_id` concuerdan.
2. Todo chunk pertenece a una versión del tenant actual; toda cita a versión y chunk concretos.
3. Ninguna conversación apunta a asistentes de otro tenant.
4. No hay Foreign Keys cruzadas entre `rag_control` y bases tenant; integridad entre planos verificada por servicio.
5. IDs en API son UUID opacos; no exponer nombres físicos de BD/tablas ni referencias a secretos.
6. Operaciones multi-sistema usan máquina de estados y compensación, no aparentan transacciones distribuidas ACID.

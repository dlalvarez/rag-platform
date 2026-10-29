# 03 — Tenancy, identidad, autorización y aislamiento

## Regla central

**Una base por tenant, jamás una tabla de conocimiento multi-tenant.** Los usuarios globales y membresías viven en `rag_control`; contenidos y ACL de repositorios, en la BD del tenant.

## Tenant ID y resolución

- Identificador UUID inmutable; nombres comerciales/slug no determinan secretos, roles ni destinos.
- Cabeceras, rutas y claims enviados por cliente son **solicitudes de contexto**, no fuente de autoridad. Middleware comprueba JWT/OIDC, membresía, estado de tenant, scopes/roles y permiso para operación.
- `TenantContext` inmutable durante una solicitud/job: `tenant_uuid`, `principal_uuid`, `roles`, `db_ref`, `storage_ref`, `trace_id`; no exponer credenciales en serialización.
- Factory `get_tenant_session(AuthorizedTenantContext)` única entrada a conexión; nunca interpolar db/host desde request.
- Resolver secreto por `secret_ref`, cache TTL corto y revocación; separar roles `tenant_app`, `tenant_migrator` y `tenant_readonly` según operaciones. No conectar como superusuario.
- Pools por tenant con cota global, LRU/cierre, timeout, límites de conexiones; prevenir fuga en cambios de tenant y en workers reutilizados.

## Política de autorización

- Roles plataforma: `platform_operator` (gestiona catálogo/infraestructura), `platform_support` (sin acceso a contenido por defecto).
- Roles tenant: `owner`, `admin`, `editor`, `reader`; posibles roles personalizados futuros.
- Repositorios: ACL explícita `repository_id + principal_uuid/grupo + capabilities`; denegar por defecto, aplicar antes de recuperar chunks.
- Asistentes tienen enlaces a repositorios autorizados; permiso para usar asistente **no** implica automáticamente permiso sobre todos sus repositorios.
- Los jobs guardan identidad/permiso de su solicitante y revalidan políticas relevantes al ejecutar; jobs de sistema usan identidad de servicio explícita auditada.

## Aislamiento físico/lógico

- BD PostgreSQL distinta por tenant; roles no cuentan con `CONNECT` a otras bases. Revocar permisos por defecto al rol `PUBLIC` cuando corresponda; no conceder privilegios globales superuser/CREATEDB al rol de aplicación.
- Compartir instancia **no** equivale a aislar recursos físicos, WAL, backups físicos o mantenimiento; reservar perfiles dedicados para requisitos de disponibilidad/PITR/regulación.
- Objetos privados: bucket por tenant (MVP) con credencial/política propia, sin ACL pública y con URLs firmadas de corta duración. Si el proveedor impone límites de buckets, evaluar modelo de prefijos aislados mediante ADR, no cambiar silenciosamente.
- Secretos en vault/secret store, `rag_control` conserva referencias opacas. Cifrado TLS para conexiones de producción. Logs redactados.
- Contexto LLM solo contiene documentos/chunks autorizados en la solicitud; nunca construir índice transversal de tenants.

## Pruebas de aislamiento negativas (bloqueantes)

- Usuario A no ve repositorios/documentos/mensajes/objetos de B mediante API ni IDs adivinados.
- Credencial SQL tenant A no puede conectarse a base tenant B.
- URL de objeto o token temporal de A no permite recuperar objetos B.
- Consultas vectoriales de A no retornan ni citan chunks de B aun con documentos semánticamente idénticos.
- Cambio de tenant en contexto de worker, cache y pool no reutiliza credenciales/sesiones de otro tenant.
- Usuario del mismo tenant sin ACL no puede consultar repo privado aunque use asistente enlazado.
- Tenant suspendido no admite chat/ingesta; flujos de soporte y recuperación segregados.

## Gestión de bajas y borrados

Borrado tenant es workflow explícito con confirmación, retención, backup final si autorizado, revocación de tokens/credenciales, eliminación de bucket, BD y referencias, con auditoría de evidencias. No habilitar auto-eliminación irreversible en MVP.

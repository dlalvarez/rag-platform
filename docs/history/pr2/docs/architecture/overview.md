# Arquitectura conceptual — RAG Platform

**Estado:** fundación documental; lo no indicado como acordado es propuesta.

## Plataforma objetivo
SaaS multi-tenant, multiusuario, multirrepositorio y multiasistente para indexar fuentes documentales, realizar búsqueda y generación RAG respetando los permisos del usuario y el tenant.

## Dominios
- **Control plane**: registro de tenants, usuarios, permisos, configuración y catálogo de ubicaciones PostgreSQL (sin almacenar los vectores/documentos de negocio del tenant).
- **Tenant data plane**: una base PostgreSQL independiente por tenant con pgvector y sus índices; credenciales independientes, acceso en contexto tenant validado.
- **Ingesta**: carga, extracción, normalización, chunking, embeddings, sincronización y borrado conforme a políticas.
- **Recuperación**: filtrado por tenant, repositorio y permisos antes de exponer chunks o construir contexto.
- **Asistentes**: políticas, configuración y acceso por tenant; abstracción del proveedor LLM.
- **Operaciones**: métricas, auditoría, backups, restauración, cuotas y administración.

## Decisiones confirmadas
PostgreSQL independiente por tenant + base central; preparado para distribuir tenants entre instancias PostgreSQL distintas. Índices vectoriales, almacenamiento y credenciales segregados. GitHub+Codex y SDD. Implementación incremental.

## Opciones propuestas, aún por aprobar
Backend modular (p. ej. FastAPI), workers de ingesta, almacén de objetos, cola, proxy/TLS y mecanismo específico de autorización. Elegirlas en specs/ADR posteriores y no confundirlas con infraestructura ya instalada.

## Infraestructura de desarrollo
Synology DS923+ aloja VM Ubuntu con Docker/Compose. Esta ubicación no define arquitectura funcional de producción. Consultar `docs/adr/0002-development-environment.md`.

## Invariantes de seguridad
Cada operación obtiene identidad y autorización del contexto autenticado y resuelve exclusivamente los recursos del tenant. No confiar en `tenant_id` libremente suministrado por el cliente. Probar siempre acceso denegado entre tenants y evitar referencias cruzadas en cachés, logs y objetos.

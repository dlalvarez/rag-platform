# Estado de aprobación del paquete

Este paquete documenta decisiones expresadas en la conversación y propuestas de implementación técnica. No debe confundirse **propuesta** con **código aprobado/desplegado**.

## Confirmado en la conversación

- RAG SaaS multi-tenant con usuarios personales y empresariales.
- PostgreSQL + pgvector como fundamento del repositorio vectorial.
- Fuerte aislamiento **base PostgreSQL por tenant** y BD central de control.
- Infraestructura preparada para DB de tenants en distintas instancias.
- Codex + GitHub con desarrollo guiado por especificaciones (SDD).

## Propuestas técnicas sujetas a revisión de fase

- FastAPI/monolito modular/workers, MinIO/S3, OIDC, PostgreSQL job queue, modelos concretos, versiones de librerías, framework UI, cuotas y SLOs.
- Nombres de esquemas y endpoints: contrato de referencia que se consolida fase a fase.
- Flujo de ramas `main`/`develop` y política de protección: adoptar formalmente en F00. La validación documental en GitHub Actions ya existe, pero no sustituye la CI de lint/tests requerida por F00.

## Estado actualizado de ejecución (2026-10-28)

- Repositorio GitHub `dlalvarez/rag-platform` creado y PR #2 documental fusionado. El PR #2 **no completó la F00 técnica** del kit.
- Servidor dev `ragdev01` listo: Ubuntu 24.04.5, Docker Engine 29.9.2, Compose 5.6.1, SSD de 120 GiB montado en `/srv/rag-data` y snapshot VMM local. Ver `docs/operations/development-host.md`.
- **Pendiente:** F00-R01..05/AC-F00-01..04 (bootstrap Python/CI/Compose real); F01 y fases siguientes, backups externos y restauración verificada. No se ha desplegado PostgreSQL/pgvector ni MinIO para el producto.
- Existe una rama de realineación documental para revisar el retorno al kit rector. Ninguna elección futura del stack queda aprobada por el solo hecho de haber restaurado archivos.
- GitHub está actualmente configurado como **repositorio público**; el kit inicial proponía privado. Decidir formalmente política de visibilidad antes de incorporar material sensible; nunca guardar secretos en Git.

## Jerarquía y conflicto resuelto

`docs/01-constitution.md` es la única constitución normativa y `docs/10-roadmap.md` el roadmap canónico. `CONSTITUTION.md` y `docs/roadmap.md` son enlaces de referencia. Documentos anteriores del PR #2 archivados en `docs/history/pr2/`.

**Pendiente de ratificar:** ADR 0002 (monolito modular) y ADR 0004 (gestión concreta de secretos/objetos) conservan su condición de propuesta. ADR 0001 y ADR 0003 reflejan decisiones ya acordadas.

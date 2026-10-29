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
- Flujo de ramas `main`/`develop` y CI: adoptar formalmente en F00.

## No realizado aún

- Ningún repo remoto fue creado o modificado.
- Ninguna fase fue implementada ni validada contra base de datos real.
- No hay servidores, credenciales, conexiones a GitHub o instancias PostgreSQL configuradas desde este paquete.

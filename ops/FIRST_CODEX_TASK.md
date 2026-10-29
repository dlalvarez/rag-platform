# Primera tarea lista para dar a Codex — F00

**Objetivo:** preparar infraestructura mínima de desarrollo, sin construir todavía RAG ni aprovisionamiento.

Copiar este mensaje a Codex Cloud apuntando al repositorio con este paquete versionado:

```text
Implementa la fase F00-fundacion-repositorio, únicamente F00.
Lee primero AGENTS.md, docs/01-constitution.md, docs/02-architecture.md,
docs/03-tenancy-security.md, docs/09-nfr-quality.md y docs/10-roadmap.md.
La especificación es specs/F00-fundacion-repositorio/spec.md; el plan y
las tareas preliminares están en esa carpeta y deben revisarse por consistencia.
NO desarrolles autenticación, tenants, ingesta, búsqueda o conversación (F01+).

Entregables: pyproject y package mínimo, pytest/linters y tests smoke offline,
Docker Compose reproducible PostgreSQL+pgvector/MinIO con imágenes versionadas,
.env.example sin secretos y GitHub Actions básico. Reutiliza sin destruir esta
documentación y mantenla alineada. Expón los comandos probados y sus resultados.
No hagas merge ni deploy; abre PR con matriz AC-F00-01..04 y riesgos.
Si encuentras contradicción con arquitectura, detente y propón ADR.
```

**Antes de lanzarlo:** asegurar que el repo está en GitHub y las specs están commiteadas. Revisar manualmente versiones de librerías/imágenes, puertos y límites del host de desarrollo.

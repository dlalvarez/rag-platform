# Siguiente tarea para Codex — implementación F00

**Antes de ejecutar:** aprobación humana explícita de [ratificación F00](../specs/F00-fundacion-repositorio/ratification.md), spec/plan/tareas y política de ramas. Este documento prepara la tarea; no la inicia. ADR-0002 requiere decisión explícita. Crear develop desde main tras el merge aprobado del PR de planificación y registrar protección efectiva antes de ampliar CI.

```text
Implementa únicamente F00-fundacion-repositorio, relacionada con Issue #4.
Verifica aprobación de spec/plan/tareas y decisiones pendientes en ratification.md.
Lee AGENTS.md, CONSTITUTION.md, docs/01-constitution.md, docs/02-architecture.md,
docs/03-tenancy-security.md, docs/09-nfr-quality.md, docs/10-roadmap.md,
docs/14-release-and-governance.md y ADRs aplicables.
Lee los seis documentos de specs/F00-fundacion-repositorio, incluido ratification.md.
Trabaja desde develop aprobada en feat/F00-bootstrap; abre PR hacia develop.
Si falta aprobación o develop, informa el requisito pendiente antes de código.

Sigue T001 → T003 → T002 → T004 → T005 → T006 y la matriz R→AC→P→T→V.
Entrega paquete Python mínimo/configuración tipada, pyproject/lock, pytest y Ruff,
Compose PostgreSQL/pgvector + MinIO + API placeholder verificable, pins exactos
verificados, .env.example sin secretos, CI documental/lint/tests y manual reproducible.
Conserva scripts/check_docs.py y el roadmap existente.
La suite offline no usa Docker ni APIs de pago; integración Compose aparte con
datos sintéticos y credenciales efímeras externas a Git. Registra fallos controlados.
No ejecutes ni instales servicios en ragdev01. Diseña la persistencia configurable
para /srv/rag-data (ext4 120 GiB), Ubuntu 24.04.5, 2 vCPU y 16 GB RAM.
Valida montaje antes de escribir en el perfil de host cuando se autorice su prueba.
No F01, tenants, autenticación definitiva, RAG ni migraciones de negocio.
No secretos, datos privados, cambios de visibilidad, merge, auto-merge ni deploy.
No cierres Issue #4 sin evidencia completa y aceptación humana.

En el PR entrega pruebas ejecutadas/no ejecutadas, comandos, versiones, commit,
logs saneados, matriz de AC, checklist, riesgos y rollback. No marques un AC
aprobado por haber creado archivos. Si hay conflicto rector, detén ese cambio
y propón ADR; no redefinas el alcance.
```

La integración que no pueda ejecutarse queda pendiente y bloquea cerrar AC-F00-02. La aprobación de F00 no autoriza iniciar F01.
